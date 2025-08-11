import { useState, useEffect, useCallback } from 'react';
import { watchlistApi, type WatchlistItem } from '../utils/api';

const WATCHLIST_STORAGE_KEY = 'stkguru_watchlist';

export const useWatchlist = () => {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load watchlist from localStorage on mount
  useEffect(() => {
    const savedWatchlist = localStorage.getItem(WATCHLIST_STORAGE_KEY);
    if (savedWatchlist) {
      try {
        const parsed = JSON.parse(savedWatchlist);
        setWatchlist(parsed);
      } catch (e) {
        console.error('Failed to parse saved watchlist:', e);
      }
    }
  }, []);

  // Sync with backend
  useEffect(() => {
    const syncWithBackend = async () => {
      setLoading(true);
      try {
        const backendWatchlist = await watchlistApi.getWatchlist();
        setWatchlist(backendWatchlist);
        // Update localStorage with backend data
        localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(backendWatchlist));
        setError(null);
      } catch (e) {
        setError('Failed to sync with backend');
        console.error('Backend sync failed:', e);
      } finally {
        setLoading(false);
      }
    };

    syncWithBackend();
  }, []);

  // Save to localStorage whenever watchlist changes
  useEffect(() => {
    localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(watchlist));
  }, [watchlist]);

  const addTicker = useCallback(async (ticker: string) => {
    const normalizedTicker = ticker.trim().toUpperCase();
    
    if (!normalizedTicker) {
      setError('Ticker cannot be empty');
      return false;
    }

    if (watchlist.some(item => item.ticker === normalizedTicker)) {
      setError(`${normalizedTicker} is already in watchlist`);
      return false;
    }

    setLoading(true);
    try {
      const response = await watchlistApi.addToWatchlist(normalizedTicker);
      
      if (response.status === 'success') {
        const newItem: WatchlistItem = {
          ticker: normalizedTicker,
          added_at: new Date().toISOString(),
        };
        setWatchlist(prev => [...prev, newItem]);
        setError(null);
        return true;
      } else {
        setError(response.message || 'Failed to add ticker');
        return false;
      }
    } catch (e) {
      setError('Failed to add ticker');
      return false;
    } finally {
      setLoading(false);
    }
  }, [watchlist]);

  const removeTicker = useCallback(async (ticker: string) => {
    setLoading(true);
    try {
      const response = await watchlistApi.removeFromWatchlist(ticker);
      
      if (response.status === 'success') {
        setWatchlist(prev => prev.filter(item => item.ticker !== ticker));
        setError(null);
        return true;
      } else {
        setError(response.message || 'Failed to remove ticker');
        return false;
      }
    } catch (e) {
      setError('Failed to remove ticker');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    watchlist,
    loading,
    error,
    addTicker,
    removeTicker,
    clearError,
  };
};
