'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { StoryForm } from '@/components/story/StoryForm';
import { useAuth } from '@/lib/auth/authContext';

export default function CreateStoryPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Redirect to register page if not authenticated
    if (!isLoading && !isAuthenticated) {
      console.log('User not authenticated, redirecting to register page');
      router.push('/register');
    }
  }, [isAuthenticated, isLoading, router]);

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="h-12 w-12 border-4 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  // Don't render the form if not authenticated (will redirect)
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Story Generator</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Create amazing stories powered by AI
          </p>
        </div>
        <StoryForm />
      </div>
    </div>
  );
}
