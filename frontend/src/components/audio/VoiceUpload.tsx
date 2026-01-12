'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Button } from '@/components/ui/button';
import { uploadVoiceSample, getDefaultVoice } from '@/lib/api/client';
import { useAuth } from '@/lib/auth/authContext';

interface VoiceUploadProps {
  onVoiceUploaded?: (voiceId: string, sampleUrl: string) => void;
  showDefaultOption?: boolean;
}

export function VoiceUpload({ onVoiceUploaded, showDefaultOption = true }: VoiceUploadProps) {
  const { isAuthenticated } = useAuth();
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [usingDefault, setUsingDefault] = useState(false);

  // Voice metadata
  const [voiceName, setVoiceName] = useState('');
  const [voiceDescription, setVoiceDescription] = useState('');
  const [exaggeration, setExaggeration] = useState(0.3);
  const [isDefault, setIsDefault] = useState(false);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      const file = acceptedFiles[0];
      setUploadedFile(file);
      setError(null);
      setSuccess(null);
      setUsingDefault(false);

      // Auto-fill voice name from filename if not set
      if (!voiceName) {
        setVoiceName(file.name.replace(/\.[^/.]+$/, ''));
      }
    },
    [voiceName]
  );

  const handleUpload = async () => {
    if (!uploadedFile) return;

    if (!isAuthenticated) {
      setError('You must be logged in to upload voices');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    setError(null);
    setSuccess(null);

    // Simulate progress for better UX
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 90) return 90; // Hold at 90% until upload completes
        return prev + 10;
      });
    }, 200);

    try {
      const result = await uploadVoiceSample(
        uploadedFile,
        voiceName || uploadedFile.name.replace(/\.[^/.]+$/, ''),
        voiceDescription,
        exaggeration,
        isDefault
      );

      clearInterval(progressInterval);
      setUploadProgress(100);

      setSuccess(
        `Voice uploaded successfully! ${result.embeddings_cached ? '✓ Cached for fast use' : ''}`
      );

      onVoiceUploaded?.(result.voice_id, result.sample_url);

      // Reset form
      setTimeout(() => {
        setUploadedFile(null);
        setVoiceName('');
        setVoiceDescription('');
        setExaggeration(0.3);
        setIsDefault(false);
        setSuccess(null);
        setUploadProgress(0);
      }, 3000);
    } catch (err) {
      clearInterval(progressInterval);
      setUploadProgress(0);
      setError(err instanceof Error ? err.message : 'Failed to upload voice sample');
    } finally {
      setIsUploading(false);
    }
  };

  const handleUseDefaultVoice = async () => {
    setUploadedFile(null);
    setError(null);
    setSuccess(null);
    setUsingDefault(true);

    try {
      // Fetch default voice info
      const defaultVoice = await getDefaultVoice();
      onVoiceUploaded?.(defaultVoice.voice_id, defaultVoice.sample_url);
      setSuccess('Using default voice');
    } catch (err) {
      setError('Failed to load default voice');
      setUsingDefault(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/wav': ['.wav'],
      'audio/mpeg': ['.mp3'],
      'audio/flac': ['.flac'],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024, // 50MB
    disabled: !isAuthenticated,
  });

  if (!isAuthenticated) {
    return (
      <div className="p-6 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
        <p className="text-sm text-yellow-800 dark:text-yellow-200">
          Please log in to upload custom voices. You can use the default voice without logging in.
        </p>
        {showDefaultOption && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleUseDefaultVoice}
            className="mt-3"
          >
            Use Default Voice
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragActive
            ? 'border-purple-500 bg-purple-50 dark:bg-purple-950'
            : 'border-gray-300 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600'
          }
          ${isUploading ? 'opacity-50 pointer-events-none' : ''}
        `}
      >
        <input {...getInputProps()} />
        <div className="space-y-4">
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
          {isDragActive ? (
            <p className="text-purple-600 dark:text-purple-400">Drop the audio file here</p>
          ) : (
            <>
              <p className="text-gray-600 dark:text-gray-400">
                Drag & drop an audio file here, or click to browse
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-500">
                Supports WAV, MP3, FLAC (max 50MB)
              </p>
              <p className="text-xs text-purple-600 dark:text-purple-400 mt-2">
                ⏱️ Voices longer than 15s will be automatically cropped
              </p>
            </>
          )}
        </div>
      </div>

      {uploadedFile && !isUploading && (
        <div className="space-y-4 p-4 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <svg className="h-5 w-5 text-purple-600 dark:text-purple-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <div>
                <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
                  {uploadedFile.name}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">
                  {(uploadedFile.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setUploadedFile(null);
                setVoiceName('');
                setVoiceDescription('');
              }}
            >
              Remove
            </Button>
          </div>

          {/* Voice Metadata Form */}
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Voice Name
              </label>
              <input
                type="text"
                value={voiceName}
                onChange={(e) => setVoiceName(e.target.value)}
                placeholder="My Voice"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Description (optional)
              </label>
              <input
                type="text"
                value={voiceDescription}
                onChange={(e) => setVoiceDescription(e.target.value)}
                placeholder="My natural speaking voice"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Emotion Exaggeration: {exaggeration.toFixed(2)}
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={exaggeration}
                onChange={(e) => setExaggeration(parseFloat(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500 dark:text-gray-500 mt-1">
                <span>Subtle (0.0)</span>
                <span>Balanced (0.3)</span>
                <span>Expressive (1.0)</span>
              </div>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="setDefault"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
                className="h-4 w-4 text-purple-600 focus:ring-purple-500 border-gray-300 rounded"
              />
              <label htmlFor="setDefault" className="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                Set as my default voice
              </label>
            </div>
          </div>

          {/* Progress Bar */}
          {isUploading && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
                <span>Uploading voice sample...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-purple-600 to-pink-600 h-2.5 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              {uploadProgress < 90 && (
                <p className="text-xs text-gray-500 dark:text-gray-500">
                  Processing audio file...
                </p>
              )}
              {uploadProgress >= 90 && uploadProgress < 100 && (
                <p className="text-xs text-gray-500 dark:text-gray-500">
                  Saving voice profile...
                </p>
              )}
            </div>
          )}

          <Button
            onClick={handleUpload}
            disabled={isUploading}
            className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
          >
            {isUploading ? 'Uploading & Caching Voice...' : 'Upload Voice'}
          </Button>
        </div>
      )}

      {usingDefault && !uploadedFile && (
        <div className="flex items-center justify-between p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <div className="flex items-center space-x-3">
            <svg className="h-5 w-5 text-blue-600 dark:text-blue-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <div>
              <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                Using default voice
              </p>
              <p className="text-xs text-blue-600 dark:text-blue-400">
                System default voice sample
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setUsingDefault(false)}
          >
            Remove
          </Button>
        </div>
      )}

      {success && (
        <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
          <p className="text-sm text-green-800 dark:text-green-200">{success}</p>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {showDefaultOption && !usingDefault && !uploadedFile && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={handleUseDefaultVoice}>
            Use Default Voice
          </Button>
        </div>
      )}
    </div>
  );
}
