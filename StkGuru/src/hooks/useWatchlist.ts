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
    } else {
      // Add default tickers if no saved watchlist
      const defaultTickers = [
        { ticker: 'SPY', added_at: new Date().toISOString() },
        { ticker: 'QQQ', added_at: new Date().toISOString() },
        { ticker: 'AAPL', added_at: new Date().toISOString() },
        { ticker: 'NVDA', added_at: new Date().toISOString() },
        { ticker: 'TSLA', added_at: new Date().toISOString() }
      ];
      console.log('Adding default tickers to watchlist:', defaultTickers.map(item => item.ticker));
      setWatchlist(defaultTickers);
      localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(defaultTickers));
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
    console.log(`🔄 removeTicker called for: ${ticker}`);
    console.log(`📊 Current watchlist before removal:`, watchlist.map(item => item.ticker));
    
    setLoading(true);
    try {
      console.log(`🌐 Calling backend API to remove ${ticker}...`);
      const response = await watchlistApi.removeFromWatchlist(ticker);
      console.log(`📡 Backend response:`, response);
      
      if (response.status === 'success') {
        console.log(`✅ Backend success, updating frontend state...`);
        setWatchlist(prev => {
          const newWatchlist = prev.filter(item => item.ticker !== ticker);
          console.log(`🔄 setWatchlist called - old count: ${prev.length}, new count: ${newWatchlist.length}`);
          console.log(`📊 New watchlist:`, newWatchlist.map(item => item.ticker));
          return newWatchlist;
        });
        setError(null);
        console.log(`✅ removeTicker completed successfully for ${ticker}`);
        return true;
      } else {
        console.log(`❌ Backend failed:`, response.message);
        setError(response.message || 'Failed to remove ticker');
        return false;
      }
    } catch (e) {
      console.error(`💥 Error in removeTicker for ${ticker}:`, e);
      setError('Failed to remove ticker');
      return false;
    } finally {
      setLoading(false);
    }
  }, [watchlist]);

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
