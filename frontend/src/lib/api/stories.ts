/**
 * Stories API Client
 * Handles all API calls for story management and dashboard
 */

const API_BASE = 'http://localhost:8000/api/v1';

export interface Story {
  id: string;
  title: string;
  text?: string;
  text_preview?: string;
  theme: string;
  style: string;
  tone: string;
  length: string;
  word_count: number;
  thumbnail_color: string;
  preview_text: string;
  created_at: string;
  updated_at: string;
  audio_url?: string;
  metadata?: any;
}

export interface StoriesListResponse {
  stories: Story[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreateSimilarRequest {
  modification_prompt: string;
}

export interface CreateSimilarResponse {
  story_id: string;
  story_text: string;
  word_count: number;
  original_story_id: string;
  modifications_applied: string;
}

/**
 * Fetch all stories with pagination
 */
export async function fetchStories(
  limit: number = 20,
  offset: number = 0
): Promise<StoriesListResponse> {
  const response = await fetch(
    `${API_BASE}/stories?limit=${limit}&offset=${offset}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch stories: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch single story by ID
 */
export async function fetchStory(storyId: string): Promise<Story> {
  const response = await fetch(`${API_BASE}/stories/${storyId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch story: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Delete story by ID
 */
export async function deleteStory(storyId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/stories/${storyId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to delete story: ${response.statusText}`);
  }
}

/**
 * Create similar story with AI modifications
 */
export async function createSimilarStory(
  storyId: string,
  modificationPrompt: string
): Promise<CreateSimilarResponse> {
  const response = await fetch(
    `${API_BASE}/stories/${storyId}/create-similar`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        modification_prompt: modificationPrompt,
      }),
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create similar story');
  }

  return response.json();
}
