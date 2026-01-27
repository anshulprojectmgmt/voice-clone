"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Button } from "@/components/ui/button";
import { uploadVoiceSample, getDefaultVoice } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/authContext";

type UploadStage = "idle" | "uploading" | "processing" | "saving" | "done";

interface VoiceUploadProps {
  onVoiceUploaded?: (voiceId: string, sampleUrl: string) => void;
  showDefaultOption?: boolean;
}

export function VoiceUpload({
  onVoiceUploaded,
  showDefaultOption = true,
}: VoiceUploadProps) {
  const { isAuthenticated } = useAuth();

  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [stage, setStage] = useState<UploadStage>("idle");

  const [voiceName, setVoiceName] = useState("");
  const [voiceDescription, setVoiceDescription] = useState("");
  const [exaggeration, setExaggeration] = useState(0.3);
  const [isDefault, setIsDefault] = useState(false);

  const [voiceId, setVoiceId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [usingDefault, setUsingDefault] = useState(false);

  // -----------------------------
  // FILE DROP
  // -----------------------------
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (!acceptedFiles.length) return;

      const file = acceptedFiles[0];
      setUploadedFile(file);
      setVoiceId(null);
      setError(null);
      setSuccess(null);
      setUsingDefault(false);

      if (!voiceName) {
        setVoiceName(file.name.replace(/\.[^/.]+$/, ""));
      }
    },
    [voiceName],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "audio/wav": [".wav"],
      "audio/mpeg": [".mp3"],
      "audio/flac": [".flac"],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
    disabled: !isAuthenticated || isUploading,
  });

  // -----------------------------
  // UPLOAD HANDLER
  // -----------------------------
  const handleUpload = async () => {
    if (!uploadedFile) return;
    if (!isAuthenticated) {
      setError("You must be logged in to upload voices");
      return;
    }

    setIsUploading(true);
    setStage("uploading");
    setUploadProgress(10);
    setError(null);
    setSuccess(null);
    setVoiceId(null);

    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => (prev < 85 ? prev + 5 : prev));
    }, 300);

    try {
      setStage("processing");
      setUploadProgress(60);

      const result = await uploadVoiceSample(
        uploadedFile,
        voiceName || uploadedFile.name.replace(/\.[^/.]+$/, ""),
        voiceDescription,
        exaggeration,
        isDefault,
      );

      clearInterval(progressInterval);

      setStage("saving");
      setUploadProgress(90);

      setVoiceId(result.voice_id);
      onVoiceUploaded?.(result.voice_id, result.sample_url);

      setStage("done");
      setUploadProgress(100);
      setSuccess("Voice uploaded successfully");

      setTimeout(() => {
        setUploadedFile(null);
        setVoiceName("");
        setVoiceDescription("");
        setExaggeration(0.3);
        setIsDefault(false);
        setUploadProgress(0);
        setStage("idle");
      }, 3000);
    } catch (err) {
      clearInterval(progressInterval);
      setUploadProgress(0);
      setStage("idle");
      setError(err instanceof Error ? err.message : "Failed to upload voice");
    } finally {
      setIsUploading(false);
    }
  };

  // -----------------------------
  // DEFAULT VOICE
  // -----------------------------
  const handleUseDefaultVoice = async () => {
    setUsingDefault(true);
    setError(null);
    setSuccess(null);
    setVoiceId(null);

    try {
      const voice = await getDefaultVoice();
      onVoiceUploaded?.(voice.voice_id, voice.sample_url);
      setVoiceId(voice.voice_id);
      setSuccess("Using default voice");
    } catch {
      setError("Failed to load default voice");
      setUsingDefault(false);
    }
  };

  // -----------------------------
  // UI
  // -----------------------------
  if (!isAuthenticated) {
    return (
      <div className="p-4 border rounded bg-yellow-50">
        <p>Please log in to upload custom voices.</p>
        {showDefaultOption && (
          <Button className="mt-3" onClick={handleUseDefaultVoice}>
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
        className={`border-2 border-dashed rounded p-6 text-center cursor-pointer
          ${isDragActive ? "border-purple-500 bg-purple-50" : "border-gray-300"}
          ${isUploading ? "opacity-50 pointer-events-none" : ""}
        `}
      >
        <input {...getInputProps()} />
        <p>Drag & drop audio file or click to browse</p>
        <p className="text-xs text-gray-500">WAV / MP3 / FLAC — max 50MB</p>
      </div>

      {uploadedFile && (
        <div className="space-y-3">
          <input
            value={voiceName}
            onChange={(e) => setVoiceName(e.target.value)}
            placeholder="Voice name"
            className="w-full p-2 border rounded"
          />

          <input
            value={voiceDescription}
            onChange={(e) => setVoiceDescription(e.target.value)}
            placeholder="Description (optional)"
            className="w-full p-2 border rounded"
          />

          <label className="block text-sm">
            Exaggeration: {exaggeration.toFixed(2)}
          </label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={exaggeration}
            onChange={(e) => setExaggeration(Number(e.target.value))}
          />

          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
            />
            <span>Set as default voice</span>
          </label>

          {isUploading && (
            <div>
              <div className="flex justify-between text-sm">
                <span>
                  {stage === "uploading" && "Uploading to cloud…"}
                  {stage === "processing" && "Processing voice…"}
                  {stage === "saving" && "Saving profile…"}
                  {stage === "done" && "Completed"}
                </span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded">
                <div
                  className="h-2 bg-purple-600 rounded transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          <Button onClick={handleUpload} disabled={isUploading}>
            {isUploading ? "Uploading…" : "Upload Voice"}
          </Button>
        </div>
      )}

      {voiceId && (
        <div className="p-3 bg-purple-500 border rounded">
          <p className="text-sm font-medium">Voice ID</p>
          <code className="block mt-1 text-xs">{voiceId}</code>
        </div>
      )}

      {success && <p className="text-green-600">{success}</p>}
      {error && <p className="text-red-600">{error}</p>}

      {showDefaultOption && !uploadedFile && !usingDefault && (
        <Button variant="outline" onClick={handleUseDefaultVoice}>
          Use Default Voice
        </Button>
      )}
    </div>
  );
}
