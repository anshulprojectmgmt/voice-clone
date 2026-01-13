'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Story } from '@/types/story';
import { RepromptDialog } from './RepromptDialog';

interface StoryDisplayProps {
  story: Story;
  onEdit?: () => void;
  onGenerateAudio?: () => void;
  onReprompt?: (modifiedText: string) => void;
}

export function StoryDisplay({ story, onEdit, onGenerateAudio, onReprompt }: StoryDisplayProps) {
  const [showRepromptDialog, setShowRepromptDialog] = useState(false);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const readingTime = Math.ceil(story.wordCount / 200);

  const handleRepromptSuccess = (modifiedText: string) => {
    setShowRepromptDialog(false);
    if (onReprompt) {
      onReprompt(modifiedText);
    }
  };

  return (
    <Card variant="bordered">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div className="flex-1">
            <CardTitle>Your Story</CardTitle>
            <CardDescription className="mt-2">
              <span className="inline-block mr-4">
                <strong>Theme:</strong> {story.theme}
              </span>
              <span className="inline-block mr-4">
                <strong>Style:</strong> {story.style}
              </span>
              <span className="inline-block mr-4">
                <strong>Tone:</strong> {story.tone}
              </span>
            </CardDescription>
            <div className="mt-2 flex gap-4 text-sm text-gray-600 dark:text-gray-400">
              <span>{story.wordCount} words</span>
              <span>~{readingTime} min read</span>
              <span>Created {formatDate(story.createdAt)}</span>
            </div>
          </div>
          <div className="flex gap-2">
            {onEdit && (
              <Button variant="outline" size="sm" onClick={onEdit}>
                Edit
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => setShowRepromptDialog(true)}>
              ✨ Re-prompt
            </Button>
            {onGenerateAudio && (
              <Button variant="primary" size="sm" onClick={onGenerateAudio}>
                Generate Audio
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0">
        <div className="prose prose-gray dark:prose-invert max-w-none">
          <div className="whitespace-pre-wrap leading-relaxed text-gray-900 dark:text-gray-100 break-words">
            {story.text}
          </div>
        </div>
      </CardContent>

      {showRepromptDialog && (
        <RepromptDialog
          storyId={story.id}
          originalText={story.text}
          onClose={() => setShowRepromptDialog(false)}
          onSuccess={handleRepromptSuccess}
        />
      )}
    </Card>
  );
}
