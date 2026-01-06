'use client';

import { Button } from '@/components/ui/button';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth/authContext';

export function EmptyState() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  const handleCreateStory = () => {
    // Redirect to register page if not authenticated
    if (!isAuthenticated) {
      console.log('User not authenticated, redirecting to register page');
      router.push('/register');
    } else {
      router.push('/story/create');
    }
  };

  return (
    <div className="flex flex-col items-center justify-center py-20 px-4">
      <div className="text-center max-w-md space-y-6">
        {/* Icon */}
        <div className="flex justify-center">
          <div className="w-24 h-24 bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-900/30 dark:to-purple-900/30 rounded-full flex items-center justify-center">
            <svg
              className="w-12 h-12 text-blue-600 dark:text-blue-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
          </div>
        </div>

        {/* Text */}
        <div className="space-y-2">
          <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            No stories yet
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            {isAuthenticated
              ? 'Start creating amazing stories with AI! Your generated stories will appear here.'
              : 'Sign up to start creating amazing stories with AI!'}
          </p>
        </div>

        {/* Action Button */}
        <Button
          variant="primary"
          size="lg"
          onClick={handleCreateStory}
          className="gap-2"
          disabled={isLoading}
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
          {isAuthenticated ? 'Create Your First Story' : 'Sign Up to Get Started'}
        </Button>
      </div>
    </div>
  );
}
