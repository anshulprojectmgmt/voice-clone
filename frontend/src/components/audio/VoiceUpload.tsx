'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Button } from '@/components/ui/button';
import { uploadVoiceSample } from '@/lib/api/client';

interface VoiceUploadProps {
  onVoiceUploaded?: (voiceId: string, sampleUrl: string) => void;
}

export function VoiceUpload({ onVoiceUploaded }: VoiceUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [usingDefault, setUsingDefault] = useState(false);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      const file = acceptedFiles[0];
      setUploadedFile(file);
      setError(null);
      setIsUploading(true);
      setUsingDefault(false);

      try {
        const result = await uploadVoiceSample(file);
        onVoiceUploaded?.(result.voice_id, result.sample_url);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to upload voice sample');
      } finally {
        setIsUploading(false);
      }
    },
    [onVoiceUploaded]
  );

  const handleUseDefaultVoice = () => {
    setUploadedFile(null);
    setError(null);
    setUsingDefault(true);
    onVoiceUploaded?.('default', '/output/voice_samples/default.wav');
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
  });

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragActive
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-950'
            : 'border-gray-300 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600'
          }
          ${isUploading ? 'opacity-50 pointer-events-none' : ''}
        `}
      >
        <input {...getInputProps()} />
        <div className="space-y-4">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            stroke="currentColor"
            fill="none"
            viewBox="0 0 48 48"
            aria-hidden="true"
          >
            <path
              d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {isDragActive ? (
            <p className="text-blue-600 dark:text-blue-400">Drop the audio file here</p>
          ) : (
            <>
              <p className="text-gray-600 dark:text-gray-400">
                Drag & drop an audio file here, or click to browse
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-500">
                Supports WAV, MP3, FLAC (max 50MB)
              </p>
            </>
          )}
          {isUploading && (
            <p className="text-blue-600 dark:text-blue-400">Uploading...</p>
          )}
        </div>
      </div>

      {uploadedFile && !isUploading && (
        <div className="flex items-center justify-between p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
          <div className="flex items-center space-x-3">
            <svg className="h-5 w-5 text-green-600 dark:text-green-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <div>
              <p className="text-sm font-medium text-green-800 dark:text-green-200">
                {uploadedFile.name}
              </p>
              <p className="text-xs text-green-600 dark:text-green-400">
                {(uploadedFile.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setUploadedFile(null)}
          >
            Remove
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

      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {!usingDefault && !uploadedFile && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={handleUseDefaultVoice}>
            Use Default Voice
          </Button>
        </div>
      )}
    </div>
  );
}
