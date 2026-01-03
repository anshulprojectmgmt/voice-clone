"use client";

import { useState } from 'react';
import { VoiceUpload } from '@/components/audio/VoiceUpload';
import { VoiceLibrary } from '@/components/voice/VoiceLibrary';
import { useAuth } from '@/lib/auth/authContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function VoicesPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>('');
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  const handleVoiceUploaded = (voiceId: string) => {
    // Refresh the voice library
    setRefreshKey(prev => prev + 1);
    setSelectedVoiceId(voiceId);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin h-12 w-12 border-4 border-purple-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            Voice Management
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Upload and manage your voice samples. Voices are cached for 10-20x faster synthesis!
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Upload Section */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-6 flex items-center gap-2">
              <svg className="h-6 w-6 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              Upload New Voice
            </h2>
            <VoiceUpload
              onVoiceUploaded={handleVoiceUploaded}
              showDefaultOption={false}
            />

            {/* Info Boxes */}
            <div className="mt-6 space-y-3">
              <div className="p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
                <h3 className="text-sm font-medium text-purple-900 dark:text-purple-100 flex items-center gap-2 mb-2">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Voice Caching Optimization
                </h3>
                <ul className="text-xs text-purple-800 dark:text-purple-200 space-y-1">
                  <li>• Voices are pre-computed and cached on upload (takes 400-1100ms once)</li>
                  <li>• Future use loads from cache in &lt;50ms (10-20x faster!)</li>
                  <li>• Set a default voice for quick access</li>
                  <li>• Supports WAV, MP3, and FLAC formats</li>
                </ul>
              </div>

              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                <h3 className="text-sm font-medium text-blue-900 dark:text-blue-100 flex items-center gap-2 mb-2">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Duration Requirements
                </h3>
                <ul className="text-xs text-blue-800 dark:text-blue-200 space-y-1">
                  <li>• <strong>Minimum:</strong> 3 seconds of clear speech</li>
                  <li>• <strong>Recommended:</strong> 5-10 seconds for best quality</li>
                  <li>• <strong>Maximum:</strong> 15 seconds (auto-cropped to prevent timeouts)</li>
                  <li>• Longer voices are automatically trimmed - no quality loss!</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Library Section */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-6 flex items-center gap-2">
              <svg className="h-6 w-6 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
              My Voice Library
            </h2>
            <VoiceLibrary
              key={refreshKey}
              selectedVoiceId={selectedVoiceId}
              onVoiceSelected={setSelectedVoiceId}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
