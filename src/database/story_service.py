"""
Story Service - Business logic for story database operations
"""
from typing import List, Optional, Dict
import uuid
import json
from datetime import datetime
from .connection import get_db, get_cursor, USE_POSTGRES
from .models import Story


# Theme color mapping
THEME_COLORS = {
    "adventure": "#FF6B6B",
    "fantasy": "#A78BFA",
    "mystery": "#374151",
    "sci-fi": "#60A5FA",
    "horror": "#1F2937",
    "romance": "#F472B6",
}


def get_placeholder():
    """Get SQL parameter placeholder based on database type"""
    return "%s" if USE_POSTGRES else "?"


class StoryService:
    """Service for story database operations"""

    @staticmethod
    def generate_title(text: str, theme: str) -> str:
        """Generate a title from story text and theme"""
        # Take first sentence or first 50 chars
        first_line = text.split('\n')[0].strip()
        if len(first_line) > 50:
            title = first_line[:47] + '...'
        else:
            title = first_line

        # Fallback to theme-based title
        if not title or len(title) < 10:
            title = f"{theme.capitalize()} Story"

        return title

    @staticmethod
    def generate_preview(text: str, max_length: int = 150) -> str:
        """Generate preview text (first 150 chars)"""
        if len(text) <= max_length:
            return text
        return text[:max_length].rsplit(' ', 1)[0] + '...'

    @staticmethod
    def get_theme_color(theme: str) -> str:
        """Get color for theme"""
        return THEME_COLORS.get(theme.lower(), "#6B7280")

    @staticmethod
    def create_story(
        text: str,
        theme: str,
        style: str,
        tone: str,
        length: str,
        word_count: int,
        story_id: Optional[str] = None,
        audio_url: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Story:
        """
        Create and save a new story to database

        Args:
            text: Story text
            theme: Story theme
            style: Story style
            tone: Story tone
            length: Story length
            word_count: Number of words
            story_id: Optional custom ID (generates UUID if not provided)
            audio_url: Optional audio file URL
            metadata: Optional metadata dict

        Returns:
            Created Story object
        """
        # Generate values
        if story_id is None:
            story_id = str(uuid.uuid4())

        title = StoryService.generate_title(text, theme)
        preview_text = StoryService.generate_preview(text)
        thumbnail_color = StoryService.get_theme_color(theme)
        now = datetime.now().isoformat()

        # Insert into database
        ph = get_placeholder()
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(f"""
                INSERT INTO stories (
                    id, title, text, theme, style, tone, length,
                    word_count, thumbnail_color, preview_text,
                    created_at, updated_at, audio_url, metadata
                ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """, (
                story_id, title, text, theme, style, tone, length,
                word_count, thumbnail_color, preview_text,
                now, now, audio_url, json.dumps(metadata) if metadata else None
            ))
            conn.commit()

        # Return created story
        return Story(
            id=story_id,
            title=title,
            text=text,
            theme=theme,
            style=style,
            tone=tone,
            length=length,
            word_count=word_count,
            thumbnail_color=thumbnail_color,
            preview_text=preview_text,
            created_at=now,
            updated_at=now,
            audio_url=audio_url,
            metadata=metadata
        )

    @staticmethod
    def get_story(story_id: str) -> Optional[Story]:
        """Get story by ID"""
        try:
            ph = get_placeholder()
            with get_db() as conn:
                cursor = get_cursor(conn)
                cursor.execute(f"SELECT * FROM stories WHERE id = {ph}", (story_id,))
                row = cursor.fetchone()

            if row:
                logger.debug(f"Story found in database: {story_id}")
                return Story.from_db_row(row)
            else:
                logger.debug(f"Story not found in database: {story_id}")
                return None
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}", exc_info=True)
            return None

    @staticmethod
    def list_stories(
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "created_at",
        order: str = "DESC"
    ) -> Dict:
        """
        List stories with pagination

        Args:
            limit: Number of stories per page
            offset: Number of stories to skip
            sort_by: Column to sort by
            order: Sort order (ASC or DESC)

        Returns:
            Dictionary with stories list and total count
        """
        ph = get_placeholder()
        with get_db() as conn:
            cursor = get_cursor(conn)

            # Get total count
            cursor.execute("SELECT COUNT(*) as count FROM stories")
            total = cursor.fetchone()['count']

            # Get stories (DISTINCT to prevent duplicates)
            query = f"""
                SELECT DISTINCT * FROM stories
                ORDER BY {sort_by} {order}
                LIMIT {ph} OFFSET {ph}
            """
            cursor.execute(query, (limit, offset))
            rows = cursor.fetchall()

            stories = [Story.from_db_row(row) for row in rows]

        return {
            "stories": [s.to_dict() for s in stories],
            "total": total,
            "limit": limit,
            "offset": offset
        }

    @staticmethod
    def update_story(
        story_id: str,
        text: Optional[str] = None,
        audio_url: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[Story]:
        """
        Update story fields

        Args:
            story_id: Story ID to update
            text: New text (optional)
            audio_url: New audio URL (optional)
            metadata: New metadata (optional)

        Returns:
            Updated Story object or None if not found
        """
        # Get existing story
        story = StoryService.get_story(story_id)
        if not story:
            return None

        # Build update query
        updates = []
        params = []
        ph = get_placeholder()

        if text is not None:
            updates.append(f"text = {ph}")
            params.append(text)
            updates.append(f"word_count = {ph}")
            params.append(len(text.split()))
            updates.append(f"preview_text = {ph}")
            params.append(StoryService.generate_preview(text))

        if audio_url is not None:
            updates.append(f"audio_url = {ph}")
            params.append(audio_url)

        if metadata is not None:
            updates.append(f"metadata = {ph}")
            params.append(json.dumps(metadata))

        updates.append(f"updated_at = {ph}")
        params.append(datetime.now().isoformat())

        params.append(story_id)

        query = f"UPDATE stories SET {', '.join(updates)} WHERE id = {ph}"
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(query, params)
            conn.commit()

        # Return updated story
        return StoryService.get_story(story_id)

    @staticmethod
    def delete_story(story_id: str) -> bool:
        """
        Delete story by ID

        Args:
            story_id: Story ID to delete

        Returns:
            True if deleted, False if not found
        """
        ph = get_placeholder()
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(f"DELETE FROM stories WHERE id = {ph}", (story_id,))
            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted
