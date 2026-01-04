"""
Stories API Routes - Dashboard & Story Management
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field
import logging
import uuid

from database.story_service import StoryService
from database.connection import init_db
from story_narrator.story_generator import StoryGenerator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/stories", tags=["stories"])


class CreateSimilarRequest(BaseModel):
    """Request model for creating similar story"""
    modification_prompt: str = Field(..., min_length=5, description="How to modify the story")


class CreateSimilarResponse(BaseModel):
    """Response model for creating similar story"""
    story_id: str
    story_text: str
    word_count: int
    original_story_id: str
    modifications_applied: str

# Initialize database on startup
try:
    init_db()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")


@router.get("")
async def list_stories(
    limit: int = Query(20, ge=1, le=100, description="Number of stories per page"),
    offset: int = Query(0, ge=0, description="Number of stories to skip"),
    sort_by: str = Query("created_at", description="Column to sort by"),
    order: str = Query("DESC", pattern="^(ASC|DESC)$", description="Sort order")
):
    """
    Get list of all stories with pagination

    Returns:
        - stories: List of story objects (without full text)
        - total: Total number of stories
        - limit: Stories per page
        - offset: Current offset
    """
    try:
        result = StoryService.list_stories(
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            order=order
        )

        # Remove full text from list view (only send in detail view)
        for story in result["stories"]:
            # Keep preview, remove full text for performance
            story["text_preview"] = story.pop("preview_text", "")
            story.pop("text", None)  # Remove full text

        return result

    except Exception as e:
        logger.error(f"Failed to list stories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list stories: {str(e)}")


@router.get("/{story_id}")
async def get_story(story_id: str):
    """
    Get single story by ID with full text

    Args:
        story_id: Story UUID

    Returns:
        Full story object including text
    """
    try:
        story = StoryService.get_story(story_id)

        if not story:
            raise HTTPException(status_code=404, detail="Story not found")

        return story.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get story {story_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get story: {str(e)}")


@router.delete("/{story_id}")
async def delete_story(story_id: str):
    """
    Delete story by ID

    Args:
        story_id: Story UUID

    Returns:
        Success message with deleted story ID
    """
    try:
        deleted = StoryService.delete_story(story_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Story not found")

        return {
            "message": "Story deleted successfully",
            "id": story_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete story {story_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete story: {str(e)}")


@router.patch("/{story_id}/audio")
async def update_story_audio(story_id: str, audio_url: str):
    """
    Update story with audio URL after audio generation

    Args:
        story_id: Story UUID
        audio_url: URL to generated audio file

    Returns:
        Updated story object
    """
    try:
        updated_story = StoryService.update_story(
            story_id=story_id,
            audio_url=audio_url
        )

        if not updated_story:
            raise HTTPException(status_code=404, detail="Story not found")

        return updated_story.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update story audio {story_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update audio: {str(e)}")


@router.post("/{story_id}/create-similar", response_model=CreateSimilarResponse)
async def create_similar_story(story_id: str, request: CreateSimilarRequest):
    """
    Create a similar story based on an existing story with AI modifications

    Args:
        story_id: Original story UUID
        request: Modification prompt (e.g., "change setting to space", "make it shorter")

    Returns:
        New story with modifications applied
    """
    try:
        # Get original story
        original_story = StoryService.get_story(story_id)
        if not original_story:
            raise HTTPException(status_code=404, detail="Original story not found")

        # Initialize story generator
        generator = StoryGenerator()

        if generator.provider == "gemini":
            import google.generativeai as genai

            # Configure safety settings
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            model = genai.GenerativeModel(
                model_name=generator.model,
                system_instruction="You are a professional story writer who creates variations of existing stories while maintaining quality and coherence.",
                safety_settings=safety_settings
            )

            # Build prompt for similar story with modifications
            similar_prompt = f"""Create a new story similar to the original but with specific modifications.

**Original Story Details:**
- Theme: {original_story.theme}
- Style: {original_story.style}
- Tone: {original_story.tone}
- Length: {original_story.length}

**Original Story:**
{original_story.text}

**Requested Modifications:**
{request.modification_prompt}

**Instructions:**
1. Create a NEW story (not just edit the original)
2. Keep the same theme ({original_story.theme}), style ({original_story.style}), and tone ({original_story.tone})
3. Apply the requested modifications
4. Maintain similar length (~{original_story.word_count} words)
5. Keep language simple and appropriate for children (10 years old)
6. Use short sentences and common words
7. Ensure the story is complete with beginning, middle, and end
8. Return ONLY the new story text, nothing else

**New Story:**"""

            # Generate similar story
            response = model.generate_content(
                similar_prompt,
                generation_config={
                    "temperature": 0.8,
                    "max_output_tokens": 3000,
                }
            )

            new_story_text = response.text.strip()

        else:
            raise HTTPException(
                status_code=501,
                detail=f"Create similar not yet implemented for provider: {generator.provider}"
            )

        # Calculate word count
        word_count = len(new_story_text.split())

        # Save new story to database
        new_story_id = str(uuid.uuid4())
        saved_story = StoryService.create_story(
            story_id=new_story_id,
            text=new_story_text,
            theme=original_story.theme,
            style=original_story.style,
            tone=original_story.tone,
            length=original_story.length,
            word_count=word_count,
            metadata={
                "original_story_id": story_id,
                "created_from": "similar",
                "modification_prompt": request.modification_prompt,
                "model": generator.model,
                "provider": generator.provider,
            }
        )

        logger.info(f"Created similar story {new_story_id} from {story_id}")

        return CreateSimilarResponse(
            story_id=new_story_id,
            story_text=new_story_text,
            word_count=word_count,
            original_story_id=story_id,
            modifications_applied=request.modification_prompt
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create similar story: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create similar story: {str(e)}")
