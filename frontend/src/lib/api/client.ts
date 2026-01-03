const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Helper to get auth headers from localStorage
function getAuthHeaders(): HeadersInit {
  const tokensStr = localStorage.getItem('auth_tokens');
  if (!tokensStr) return {};

  try {
    const tokens = JSON.parse(tokensStr);
    return {
      'Authorization': `Bearer ${tokens.access_token}`,
    };
  } catch {
    return {};
  }
}

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
      ...getAuthHeaders(), // ADDED: Include auth token
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to generate story');
  }

  return response.json();
}

export async function updateStory(storyId: string, text: string) {
  const response = await fetch(`${API_URL}/api/v1/story/${storyId}/edit`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(), // ADDED: Include auth token
    },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to update story');
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
      ...getAuthHeaders(), // ADDED: Include auth token
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to improve story');
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
  const response = await fetch(`${API_URL}/api/v1/tts/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(), // ADDED: Include auth token (optional for TTS)
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Server error: ${response.status}`);
  }

  return response.json();
}

export async function getTaskStatus(taskId: string) {
  const response = await fetch(`${API_URL}/api/v1/tts/status/${taskId}`);

  if (!response.ok) {
    throw new Error('Failed to get task status');
  }

  return response.json();
}

export async function uploadVoiceSample(
  file: File,
  name?: string,
  description?: string,
  exaggeration: number = 0.3,
  isDefault: boolean = false
) {
  const formData = new FormData();
  formData.append('file', file);
  if (name) formData.append('name', name);
  if (description) formData.append('description', description);
  formData.append('exaggeration', exaggeration.toString());
  formData.append('is_default', isDefault.toString());

  const response = await fetch(`${API_URL}/api/v1/voice/upload`, {
    method: 'POST',
    headers: {
      ...getAuthHeaders(), // ADDED: Include auth token (REQUIRED)
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to upload voice sample');
  }

  return response.json();
}

export async function getVoiceLibrary() {
  const response = await fetch(`${API_URL}/api/v1/voice/library`, {
    headers: {
      ...getAuthHeaders(), // ADDED: Include auth token (REQUIRED)
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to get voice library');
  }

  return response.json();
}

export async function getDefaultVoice() {
  const response = await fetch(`${API_URL}/api/v1/voice/default`, {
    headers: {
      ...getAuthHeaders(), // ADDED: Include auth token (optional)
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to get default voice');
  }

  return response.json();
}

export async function setDefaultVoice(voiceId: string) {
  const response = await fetch(`${API_URL}/api/v1/voice/set-default/${voiceId}`, {
    method: 'POST',
    headers: {
      ...getAuthHeaders(), // ADDED: Include auth token (REQUIRED)
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to set default voice');
  }

  return response.json();
}

export async function deleteVoice(voiceId: string) {
  const response = await fetch(`${API_URL}/api/v1/voice/${voiceId}`, {
    method: 'DELETE',
    headers: {
      ...getAuthHeaders(), // ADDED: Include auth token (REQUIRED)
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to delete voice');
  }

  return response.json();
}
