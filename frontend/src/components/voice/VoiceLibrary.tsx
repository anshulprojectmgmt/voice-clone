"use client";

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { getVoiceLibrary, deleteVoice, setDefaultVoice } from '@/lib/api/client';
import { useAuth } from '@/lib/auth/authContext';

interface Voice {
  voice_id: string;
  name: string;
  uploaded_at: string;
  sample_url: string;
  duration: number;
}

interface VoiceLibraryProps {
  onVoiceSelected?: (voiceId: string) => void;
  selectedVoiceId?: string;
}

export function VoiceLibrary({ onVoiceSelected, selectedVoiceId }: VoiceLibraryProps) {
  const { isAuthenticated } = useAuth();
  const [voices, setVoices] = useState<Voice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingVoiceId, setDeletingVoiceId] = useState<string | null>(null);
  const [settingDefaultId, setSettingDefaultId] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) {
      loadVoices();
    } else {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  const loadVoices = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await getVoiceLibrary();
      setVoices(result.voices || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load voice library');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (voiceId: string, voiceName: string) => {
    if (!confirm(`Are you sure you want to delete "${voiceName}"?`)) {
      return;
    }

    setDeletingVoiceId(voiceId);
    setError(null);

    try {
      await deleteVoice(voiceId);
      setVoices(voices.filter(v => v.voice_id !== voiceId));

      // If this was the selected voice, clear selection
      if (selectedVoiceId === voiceId && onVoiceSelected) {
        onVoiceSelected('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete voice');
    } finally {
      setDeletingVoiceId(null);
    }
  };

  const handleSetDefault = async (voiceId: string, voiceName: string) => {
    setSettingDefaultId(voiceId);
    setError(null);

    try {
      await setDefaultVoice(voiceId);
      alert(`"${voiceName}" has been set as your default voice`);
      await loadVoices(); // Reload to get updated default status
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set default voice');
    } finally {
      setSettingDefaultId(null);
    }
  };

  const handleSelect = (voiceId: string) => {
    if (onVoiceSelected) {
      onVoiceSelected(voiceId);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="p-6 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
        <p className="text-sm text-yellow-800 dark:text-yellow-200">
          Please log in to view your voice library.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-4 border-purple-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading voices...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
        <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        <Button
          variant="outline"
          size="sm"
          onClick={loadVoices}
          className="mt-3"
        >
          Try Again
        </Button>
      </div>
    );
  }

  if (voices.length === 0) {
    return (
      <div className="text-center p-12">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">
          No voices yet
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Upload your first voice sample to get started
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">
          My Voices ({voices.length})
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={loadVoices}
        >
          Refresh
        </Button>
      </div>

      <div className="space-y-2">
        {voices.map((voice) => (
          <div
            key={voice.voice_id}
            className={`
              p-4 border rounded-lg transition-all cursor-pointer
              ${selectedVoiceId === voice.voice_id
                ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
              }
            `}
            onClick={() => handleSelect(voice.voice_id)}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                    {voice.name}
                  </h4>
                  {selectedVoiceId === voice.voice_id && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                      Selected
                    </span>
                  )}
                </div>
                <div className="mt-1 flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                  <span className="flex items-center gap-1">
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {voice.duration?.toFixed(1)}s
                  </span>
                  <span className="flex items-center gap-1">
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {new Date(voice.uploaded_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 ml-4" onClick={(e) => e.stopPropagation()}>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSetDefault(voice.voice_id, voice.name)}
                  disabled={settingDefaultId === voice.voice_id}
                  className="text-xs"
                  title="Set as default voice"
                >
                  {settingDefaultId === voice.voice_id ? (
                    <div className="h-3 w-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                    </svg>
                  )}
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(voice.voice_id, voice.name)}
                  disabled={deletingVoiceId === voice.voice_id}
                  className="text-xs text-red-600 hover:text-red-700 hover:bg-red-50"
                  title="Delete voice"
                >
                  {deletingVoiceId === voice.voice_id ? (
                    <div className="h-3 w-3 border-2 border-red-400 border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  )}
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
