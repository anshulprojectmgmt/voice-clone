import { create } from 'zustand';
import { AudioSettings, AudioGenerationTask, VoiceSample } from '@/types/audio';

interface AudioStore {
  settings: AudioSettings;
  audioUrl: string | null;
  currentTask: AudioGenerationTask | null;
  voiceSamples: VoiceSample[];
  selectedVoice: VoiceSample | null;

  updateSettings: (settings: Partial<AudioSettings>) => void;
  setAudioUrl: (url: string | null) => void;
  setCurrentTask: (task: AudioGenerationTask | null) => void;
  updateTaskProgress: (progress: number, currentStep: string) => void;
  setVoiceSamples: (samples: VoiceSample[]) => void;
  selectVoice: (voice: VoiceSample | null) => void;
  reset: () => void;
}

export const useAudioStore = create<AudioStore>((set) => ({
  settings: {
    speed: 1.0,
    exaggeration: 0.5,
    temperature: 0.8,
    cfgWeight: 0.5,
  },
  audioUrl: null,
  currentTask: null,
  voiceSamples: [],
  selectedVoice: null,

  updateSettings: (newSettings) =>
    set((state) => ({
      settings: { ...state.settings, ...newSettings },
    })),

  setAudioUrl: (url) => set({ audioUrl: url }),

  setCurrentTask: (task) => set({ currentTask: task }),

  updateTaskProgress: (progress, currentStep) =>
    set((state) => ({
      currentTask: state.currentTask
        ? { ...state.currentTask, progress, currentStep }
        : null,
    })),

  setVoiceSamples: (samples) => set({ voiceSamples: samples }),

  selectVoice: (voice) => set({ selectedVoice: voice }),

  reset: () => set({
    audioUrl: null,
    currentTask: null,
    selectedVoice: null,
  }),
}));
