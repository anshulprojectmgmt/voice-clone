import { create } from 'zustand';
import { Story, StoryRevision } from '@/types/story';

interface StoryStore {
  currentStory: Story | null;
  isEditing: boolean;
  isDirty: boolean;
  revisions: StoryRevision[];

  setStory: (story: Story) => void;
  updateStoryText: (text: string) => void;
  setEditing: (editing: boolean) => void;
  addRevision: (revision: StoryRevision) => void;
  revertToRevision: (revisionId: string) => void;
  reset: () => void;
}

export const useStoryStore = create<StoryStore>((set) => ({
  currentStory: null,
  isEditing: false,
  isDirty: false,
  revisions: [],

  setStory: (story) => set({ currentStory: story, isDirty: false }),

  updateStoryText: (text) =>
    set((state) => ({
      currentStory: state.currentStory
        ? {
            ...state.currentStory,
            text,
            wordCount: text.split(/\s+/).filter(word => word.length > 0).length,
            updatedAt: new Date().toISOString()
          }
        : null,
      isDirty: true,
    })),

  setEditing: (editing) => set({ isEditing: editing }),

  addRevision: (revision) =>
    set((state) => ({
      revisions: [revision, ...state.revisions],
    })),

  revertToRevision: (revisionId) =>
    set((state) => {
      const revision = state.revisions.find((r) => r.id === revisionId);
      if (revision && state.currentStory) {
        return {
          currentStory: { ...state.currentStory, text: revision.text },
          isDirty: true,
        };
      }
      return state;
    }),

  reset: () => set({ currentStory: null, isEditing: false, isDirty: false, revisions: [] }),
}));
