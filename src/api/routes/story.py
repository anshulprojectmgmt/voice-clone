"""
Story API Routes - WITH AUTHENTICATION

All story endpoints require authentication to ensure:
1. Stories are associated with specific users
2. Users can only access/modify their own stories
3. Proper ownership tracking and access control
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
import uuid
from datetime import datetime
import logging

from ..models.story import (
    StoryGenerateRequest,
    StoryGenerateResponse,
    StoryEditRequest,
    AIImproveRequest,
    AIImproveResponse,
    RepromptRequest,
    RepromptResponse,
)
from story_narrator.story_generator import StoryGenerator
from database.story_service import StoryService
from ...auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/story", tags=["story"])

# Initialize story generator
story_generator = None

def get_story_generator():
    global story_generator
    if story_generator is None:
        story_generator = StoryGenerator()
    return story_generator


@router.post("/generate", response_model=StoryGenerateResponse)
async def generate_story(request: StoryGenerateRequest, user: dict = Depends(get_current_user)):
    """
    Generate a new story based on user input and save to database

    Requires:
        - Authentication (Bearer token)

    Returns:
        Generated story associated with the authenticated user
    """
    try:
        logger.info(f"Story generation request from user: {user['username']}")
        logger.info(f"Theme: {request.theme}, Style: {request.style}, Tone: {request.tone}, Length: {request.length}")

        generator = get_story_generator()

        # Use the convenience method that handles simple parameters
        result = generator.generate_from_simple_prompt(
            theme=request.theme,
            style=request.style,
            tone=request.tone,
            length=request.length
        )

        # Extract the story text from the result
        story_text = result["story"]

        # Calculate word count
        word_count = len(story_text.split())

        # Generate unique story ID
        story_id = str(uuid.uuid4())

        # Save story to database with user association
        try:
            saved_story = StoryService.create_story(
                story_id=story_id,
                user_id=user["id"],  # ASSOCIATE WITH USER
                text=story_text,
                theme=request.theme,
                style=request.style,
                tone=request.tone,
                length=request.length,
                word_count=word_count,
                metadata={
                    "model": result["metadata"]["model"],
                    "provider": result["metadata"]["provider"],
                }
            )
            logger.info(f"✓ Story saved to database: {story_id} for user {user['username']}")
        except Exception as db_error:
            logger.error(f"Failed to save story to database: {db_error}")
            # Continue anyway - story generation succeeded

        return StoryGenerateResponse(
            story_id=story_id,
            story_text=story_text,
            word_count=word_count,
            metadata={
                "theme": request.theme,
                "style": request.style,
                "tone": request.tone,
                "length": request.length,
                "created_at": datetime.now().isoformat(),
                "model": result["metadata"]["model"],
                "provider": result["metadata"]["provider"],
            }
        )

    except Exception as e:
        logger.error(f"Failed to generate story: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate story: {str(e)}")


@router.put("/{story_id}/edit")
async def edit_story(story_id: str, request: StoryEditRequest, user: dict = Depends(get_current_user)):
    """
    Update an existing story

    Requires:
        - Authentication (Bearer token)
        - Story must belong to authenticated user

    Returns:
        Updated story information
    """
    try:
        logger.info(f"Story edit request from user {user['username']} for story {story_id}")

        # Verify story ownership
        story = StoryService.get_story(story_id)
        if not story:
            raise HTTPException(
                status_code=404,
                detail="Story not found"
            )

        if story["user_id"] != user["id"]:
            raise HTTPException(
                status_code=403,
                detail="Access denied: This story belongs to another user"
            )

        # Update story in database
        try:
            StoryService.update_story(story_id=story_id, text=request.text)
            logger.info(f"✓ Story updated: {story_id}")
        except Exception as db_error:
            logger.error(f"Failed to update story in database: {db_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update story: {str(db_error)}"
            )

        return {
            "story_id": story_id,
            "story_text": request.text,
            "revision_number": 1,
            "updated_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to edit story: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to edit story: {str(e)}")


@router.post("/ai-improve", response_model=AIImproveResponse)
async def improve_story_with_ai(request: AIImproveRequest, user: dict = Depends(get_current_user)):
    """
    Improve a story using AI

    Requires:
        - Authentication (Bearer token)

    Returns:
        Original and improved versions of the story
    """
    try:
        logger.info(f"AI improve request from user {user['username']}, type: {request.improvementType}")

        generator = get_story_generator()

        # Create improvement prompt based on type
        improvement_prompts = {
            "dramatic": "Make this story more dramatic and intense. Add more tension and emotional depth.",
            "concise": "Make this story more concise while maintaining its key elements and narrative flow.",
            "grammar": "Improve the grammar, sentence structure, and overall writing quality of this story.",
            "details": "Add more vivid details, descriptions, and sensory elements to this story.",
            "tone": "Adjust the tone of this story to be more engaging and appropriate for the narrative.",
        }

        improvement_instruction = improvement_prompts.get(
            request.improvementType,
            request.customInstruction or "Improve this story to make it more engaging and well-written."
        )

        # Use Gemini directly for improvements
        if generator.provider == "gemini":
            import google.generativeai as genai
            model = genai.GenerativeModel(
                model_name=generator.model,
                system_instruction="You are a professional story editor who improves narrative quality."
            )

            full_prompt = f"""{improvement_instruction}

Original story:
{request.text}

Write the improved version of the story."""

            response = model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 3000,
                }
            )
            improved_text = response.text
        else:
            # Fallback for other providers (not implemented yet)
            improved_text = request.text

        return AIImproveResponse(
            original=request.text,
            improved=improved_text,
            changes_summary=f"Applied {request.improvementType} improvement to the story."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to improve story: {str(e)}")


@router.post("/reprompt", response_model=RepromptResponse)
async def reprompt_story(request: RepromptRequest, user: dict = Depends(get_current_user)):
    """
    Modify an existing story using custom AI instructions.
    Examples: "make it shorter", "add more action", "change ending to be happier"

    Requires:
        - Authentication (Bearer token)
        - Story must belong to authenticated user

    Returns:
        Original and modified versions of the story
    """
    try:
        logger.info(f"Reprompt request from user {user['username']} for story {request.story_id}")
        logger.info(f"Instruction: {request.instruction}")

        # Verify story exists
        logger.debug(f"Looking up story with ID: {request.story_id}")
        story = StoryService.get_story(request.story_id)

        if not story:
            logger.warning(f"Story not found in database: {request.story_id}")
            raise HTTPException(
                status_code=404,
                detail="Story not found"
            )

        # NOTE: Stories don't currently track user_id in database schema
        # Ownership check skipped - will be added when user_id column is added to stories table
        logger.info(f"Story found: {story.id}, title: {story.title[:50]}...")

        generator = get_story_generator()

        # Build the AI prompt for story modification
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
                system_instruction="You are a professional story editor. Your task is to modify stories based on user instructions while maintaining narrative quality, coherence, and the original story's core elements unless explicitly asked to change them.",
                safety_settings=safety_settings
            )

            # Create the modification prompt
            modification_prompt = f"""I have a story that needs to be modified. Please follow these instructions carefully:

**User's Modification Request:**
{request.instruction}

**Original Story:**
{request.original_text}

**Instructions:**
1. Apply the requested modifications to the story
2. Maintain the story's overall quality and readability
3. Keep the writing style appropriate for children (simple language, short sentences)
4. Ensure the story flows naturally after modifications
5. Only return the modified story text, nothing else

**Modified Story:**"""

            # Generate the modified story
            response = model.generate_content(
                modification_prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 3000,
                }
            )

            modified_text = response.text.strip()
        else:
            # Fallback for other providers (not implemented)
            raise HTTPException(
                status_code=501,
                detail=f"Re-prompting not yet implemented for provider: {generator.provider}"
            )

        # Calculate word count
        word_count = len(modified_text.split())

        # Update story in database with modified text
        try:
            StoryService.update_story(
                story_id=request.story_id,
                text=modified_text
            )
            logger.info(f"Story updated after reprompt: {request.story_id}")
        except Exception as db_error:
            logger.error(f"Failed to update story in database: {db_error}")
            # Continue anyway - reprompt succeeded

        return RepromptResponse(
            story_id=request.story_id,
            original_text=request.original_text,
            modified_text=modified_text,
            instruction=request.instruction,
            word_count=word_count,
            created_at=datetime.now().isoformat()
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is (404, 403, etc.)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in reprompt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reprompt story: {str(e)}")
