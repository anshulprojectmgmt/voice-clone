/**
 * Keep-Alive Hook for Render Inactivity Prevention
 *
 * Polls the backend every 30 seconds to prevent Render from shutting down
 * due to inactivity during long-running operations (e.g., TTS generation).
 *
 * Usage:
 *   const { startPolling, stopPolling } = useKeepAlive();
 *
 *   // When starting long operation:
 *   startPolling();
 *
 *   // When operation completes:
 *   stopPolling();
 */

import { useEffect, useRef } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const POLL_INTERVAL = 30000; // 30 seconds (well under Render's 50s timeout)

export function useKeepAlive() {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const isPollingRef = useRef(false);

  const ping = async () => {
    try {
      await fetch(`${API_URL}/ping`, {
        method: 'GET',
        // Don't throw on error - just log it
      });
      console.log('[KeepAlive] Ping successful');
    } catch (error) {
      console.error('[KeepAlive] Ping failed:', error);
    }
  };

  const startPolling = () => {
    if (isPollingRef.current) {
      console.log('[KeepAlive] Already polling');
      return;
    }

    console.log('[KeepAlive] Starting polling to prevent Render timeout...');
    isPollingRef.current = true;

    // Send first ping immediately
    ping();

    // Then poll every 30 seconds
    intervalRef.current = setInterval(ping, POLL_INTERVAL);
  };

  const stopPolling = () => {
    if (!isPollingRef.current) {
      return;
    }

    console.log('[KeepAlive] Stopping polling');
    isPollingRef.current = false;

    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, []);

  return { startPolling, stopPolling, isPolling: isPollingRef.current };
}
