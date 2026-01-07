'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

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

interface RepromptDialogProps {
  storyId: string;
  originalText: string;
  onClose: () => void;
  onSuccess: (modifiedText: string) => void;
}

export function RepromptDialog({ storyId, originalText, onClose, onSuccess }: RepromptDialogProps) {
  const [instruction, setInstruction] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const quickPrompts = [
    { label: 'Make it shorter', value: 'make this story shorter while keeping the main plot' },
    { label: 'More exciting', value: 'make this story more exciting and action-packed' },
    { label: 'Happier ending', value: 'change the ending to be more happy and uplifting' },
    { label: 'More detailed', value: 'add more vivid details and descriptions to this story' },
    { label: 'Simpler language', value: 'simplify the language to make it easier for younger children to understand' },
  ];

  const handleQuickPrompt = (value: string) => {
    setInstruction(value);
  };

  const handleSubmit = async () => {
    if (!instruction.trim()) {
      setError('Please enter an instruction or select a quick prompt');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      console.log('📤 Sending reprompt request:', {
        story_id: storyId,
        instruction: instruction.trim(),
        text_length: originalText.length,
      });

      const response = await fetch(`${API_URL}/api/v1/story/reprompt`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({
          story_id: storyId,
          original_text: originalText,
          instruction: instruction.trim(),
        }),
      });

      console.log('📥 Response status:', response.status);

      if (!response.ok) {
        const errorData = await response.json();
        console.error('❌ API Error:', errorData);
        throw new Error(errorData.detail || 'Failed to reprompt story');
      }

      const data = await response.json();
      console.log('✅ Reprompt success:', {
        modified_text_length: data.modified_text?.length,
        word_count: data.word_count,
      });

      if (!data.modified_text) {
        throw new Error('No modified text received from API');
      }

      onSuccess(data.modified_text);
    } catch (err) {
      console.error('❌ Reprompt error:', err);
      setError(err instanceof Error ? err.message : 'Failed to reprompt story');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <CardTitle>✨ Re-prompt Story with AI</CardTitle>
          <CardDescription>
            Tell the AI how you'd like to modify your story. Be specific about what you want to change.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Quick Prompts */}
          <div>
            <label className="text-sm font-medium mb-2 block">Quick prompts:</label>
            <div className="flex flex-wrap gap-2">
              {quickPrompts.map((prompt) => (
                <Button
                  key={prompt.label}
                  variant="outline"
                  size="sm"
                  onClick={() => handleQuickPrompt(prompt.value)}
                  disabled={isLoading}
                >
                  {prompt.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Custom Instruction */}
          <div>
            <label htmlFor="instruction" className="text-sm font-medium mb-2 block">
              Your instruction:
            </label>
            <textarea
              id="instruction"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="E.g., 'add a plot twist at the end' or 'make the main character a unicorn instead of a dragon'"
              className="w-full min-h-[120px] p-3 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isLoading}
            />
            <p className="text-xs text-gray-500 mt-1">
              Be specific about what you want to change. The AI will maintain the story's quality and style.
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 justify-end">
            <Button variant="outline" onClick={onClose} disabled={isLoading}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSubmit}
              disabled={isLoading || !instruction.trim()}
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Generating...
                </span>
              ) : (
                'Re-prompt Story'
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
