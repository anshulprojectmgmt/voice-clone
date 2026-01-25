"use client";

import { useState, useEffect, useRef } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { VoiceUpload } from "./VoiceUpload";
import { AudioPlayer } from "./AudioPlayer";
import { generateAudio, getTaskStatus } from "@/lib/api/client";
import { useAudioStore } from "@/lib/stores/audioStore";
import { useKeepAlive } from "@/lib/hooks/useKeepAlive";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AudioSettingsProps {
  storyText: string;
  storyId: string;
}

export function AudioSettings({ storyText, storyId }: AudioSettingsProps) {
  const { settings, updateSettings } = useAudioStore();
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState("");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [voice_id, setVoiceId] = useState<string | null>(null);
  const [voiceLabel, setVoiceLabel] = useState<string>("No voice selected");

  const [showAdvanced, setShowAdvanced] = useState(false);
  const pollingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Keep-alive polling to prevent Render timeout during long TTS operations
  const { startPolling, stopPolling } = useKeepAlive();

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingTimeoutRef.current) {
        clearTimeout(pollingTimeoutRef.current);
      }
    };
  }, []);

  const handleVoiceUploaded = (id: string, sampleUrl: string) => {
    setVoiceId(id);
    setVoiceLabel(`Voice selected: ${id.slice(0, 8)}...`);
  };

  // const handleGenerateAudio = async () => {
  //   setIsGenerating(true);
  //   setError(null);

  //   try {
  //     const result = await generateAudio({
  //       text: storyText,
  //       voice_id: voice_id!, // IMPORTANT
  //       temperature: settings.temperature,
  //       cfgWeight: settings.cfgWeight,
  //     });

  //     const fullAudioUrl = result.audio_url.startsWith("http")
  //       ? result.audio_url
  //       : `${API_URL}${result.audio_url}`;

  //     setAudioUrl(fullAudioUrl);
  //   } catch (err) {
  //     setError(err instanceof Error ? err.message : "Failed to generate audio");
  //   } finally {
  //     setIsGenerating(false);
  //   }
  // };

  const handleGenerateAudio = async () => {
    setIsGenerating(true);
    setError(null);
    setProgress(0);
    setProgressMessage("Starting audio generation…");
    setAudioUrl(null);

    // Start keep-alive polling (Render safety)
    startPolling();

    try {
      if (!voice_id) {
        setError("Please select or upload a voice first");
        setIsGenerating(false);
        stopPolling();
        return;
      }

      // 1️⃣ Start TTS job
      const result = await generateAudio({
        voice_id,
        text: storyText,
        temperature: settings.temperature,
        cfgWeight: settings.cfgWeight,
      });

      const taskId = result.task_id;

      // 2️⃣ Poll job status
      const pollStatus = async () => {
        try {
          const status = await getTaskStatus(taskId);

          setProgress(status.progress ?? 0);
          setProgressMessage(
            status.status === "processing"
              ? "Generating audio…"
              : status.status === "completed"
                ? "Finalizing audio…"
                : "Queued…",
          );

          if (status.status === "completed") {
            if (pollingTimeoutRef.current) {
              clearTimeout(pollingTimeoutRef.current);
              pollingTimeoutRef.current = null;
            }

            stopPolling();

            const fullAudioUrl = status.audio_url?.startsWith("http")
              ? status.audio_url
              : `${API_URL}${status.audio_url}`;

            setAudioUrl(fullAudioUrl);
            setIsGenerating(false);
            setProgress(100);
            setProgressMessage("Done");
            return;
          }

          if (status.status === "failed") {
            throw new Error(status.error || "Audio generation failed");
          }

          // Continue polling
          pollingTimeoutRef.current = setTimeout(pollStatus, 1500);
        } catch (err) {
          if (pollingTimeoutRef.current) {
            clearTimeout(pollingTimeoutRef.current);
            pollingTimeoutRef.current = null;
          }

          stopPolling();
          setError(
            err instanceof Error ? err.message : "Failed to check TTS status",
          );
          setIsGenerating(false);
        }
      };

      pollStatus();
    } catch (err) {
      stopPolling();
      setError(err instanceof Error ? err.message : "Failed to generate audio");
      setIsGenerating(false);
    }
  };

  const handleCancelGeneration = () => {
    // Clear polling timeout
    if (pollingTimeoutRef.current) {
      clearTimeout(pollingTimeoutRef.current);
      pollingTimeoutRef.current = null;
    }

    setIsGenerating(false);
    setProgress(0);
    setProgressMessage("");
  };

  const speedPresets = [0.75, 1.0, 1.25, 1.5];

  return (
    <div className="space-y-6">
      <Card variant="bordered">
        <CardHeader>
          <CardTitle>Voice Sample</CardTitle>
          <CardDescription>
            Upload a voice sample to clone, or use the default voice
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <VoiceUpload onVoiceUploaded={handleVoiceUploaded} />

          <div className="text-sm text-green-600 dark:text-green-400">
            {voiceLabel}
          </div>
        </CardContent>
      </Card>

      <Card variant="bordered">
        <CardHeader>
          <CardTitle>Audio Settings</CardTitle>
          <CardDescription>
            Customize the audio generation parameters
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Speed Control */}
          <div>
            <Slider
              label="Speed"
              min={0.5}
              max={2.0}
              step={0.05}
              value={settings.speed}
              onChange={(e) =>
                updateSettings({ speed: parseFloat(e.target.value) })
              }
              formatValue={(val) => `${val.toFixed(2)}x`}
            />
            <div className="flex gap-2 mt-3">
              {speedPresets.map((preset) => (
                <Button
                  key={preset}
                  variant={settings.speed === preset ? "primary" : "outline"}
                  size="sm"
                  onClick={() => updateSettings({ speed: preset })}
                >
                  {preset}x
                </Button>
              ))}
            </div>
          </div>

          {/* Advanced Settings Toggle */}
          <div>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
            >
              <svg
                className={`w-4 h-4 mr-2 transition-transform ${showAdvanced ? "rotate-90" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
              Advanced Settings
            </button>
          </div>

          {/* Advanced Settings */}
          {showAdvanced && (
            <div className="space-y-6 pt-4 border-t border-gray-200 dark:border-gray-700">
              <Slider
                label="Exaggeration"
                min={0.0}
                max={1.0}
                step={0.05}
                value={settings.exaggeration}
                onChange={(e) =>
                  updateSettings({ exaggeration: parseFloat(e.target.value) })
                }
              />
              <Slider
                label="Temperature"
                min={0.0}
                max={2.5}
                step={0.05}
                value={settings.temperature}
                onChange={(e) =>
                  updateSettings({ temperature: parseFloat(e.target.value) })
                }
              />
              <Slider
                label="CFG Weight"
                min={0.0}
                max={3.0}
                step={0.05}
                value={settings.cfgWeight}
                onChange={(e) =>
                  updateSettings({ cfgWeight: parseFloat(e.target.value) })
                }
              />
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
            </div>
          )}

          {/* Generate Button or Progress */}
          {!isGenerating && !audioUrl && (
            <Button
              variant="primary"
              size="lg"
              onClick={handleGenerateAudio}
              className="w-full"
            >
              Generate Audio
            </Button>
          )}

          {isGenerating && (
            <div className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>{progressMessage}</span>
                  <span>{progress}%</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
                  <div
                    className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelGeneration}
                className="w-full"
              >
                Cancel Generation
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {audioUrl && <AudioPlayer audioUrl={audioUrl} storyText={storyText} />}
    </div>
  );
}
