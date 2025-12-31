const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function generateStory(data: {
  theme: string;
  style: string;
  tone: string;
  length: string;
  additionalDetails?: string;
}) {
  const response = await fetch(`${API_URL}/api/v1/story/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to generate story');
  }

  return response.json();
}

export async function updateStory(storyId: string, text: string) {
  const response = await fetch(`${API_URL}/api/v1/story/${storyId}/edit`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    throw new Error('Failed to update story');
  }

  return response.json();
}

export async function improveStoryWithAI(data: {
  text: string;
  improvementType: string;
  customInstruction?: string;
}) {
  const response = await fetch(`${API_URL}/api/v1/story/ai-improve`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to improve story');
  }

  return response.json();
}

export async function generateAudio(data: {
  storyId: string;
  text: string;
  voiceSample?: string;
  speed: number;
  exaggeration: number;
  temperature: number;
  cfgWeight: number;
}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000); // 60 second timeout

  try {
    const response = await fetch(`${API_URL}/api/v1/tts/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server error: ${response.status}`);
    }

    return response.json();
  } catch (err) {
    clearTimeout(timeout);
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Request timeout - the server took too long to respond');
    }
    throw err;
  }
}

export async function getTaskStatus(taskId: string) {
  const response = await fetch(`${API_URL}/api/v1/tts/status/${taskId}`);

  if (!response.ok) {
    throw new Error('Failed to get task status');
  }

  return response.json();
}

export async function uploadVoiceSample(file: File) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_URL}/api/v1/voice/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Failed to upload voice sample');
  }

  return response.json();
}

export async function getVoiceLibrary() {
  const response = await fetch(`${API_URL}/api/v1/voice/library`);

  if (!response.ok) {
    throw new Error('Failed to get voice library');
  }

  return response.json();
}
