import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useWatchlist } from '../hooks/useWatchlist';
// apiConfig not needed for WS quotes
import { wsClient, type QuotePayload } from '../utils/wsClient';
import LoadingSpinner from './LoadingSpinner';

interface QuoteData {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  timestamp: string;
}

export interface WatchlistProps {
  className?: string;
  fullHeight?: boolean; // if true, fills viewport height
}

const Watchlist: React.FC<WatchlistProps> = ({ className = '', fullHeight = true }) => {
  const { watchlist, loading, addTicker, removeTicker } = useWatchlist();
  const [newTicker, setNewTicker] = useState('');
  const [quotes, setQuotes] = useState<Record<string, QuoteData>>({});
  const [sortBy, setSortBy] = useState<'ticker' | 'price' | 'changePct' | 'volume'>('ticker');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [forceUpdate, setForceUpdate] = useState(0); // Force re-render when quotes change
  
  // Use ref to track current watchlist without causing dependency cycles
  const watchlistRef = useRef<typeof watchlist>([]);
  const subscriptionsRef = useRef<Map<string, () => void>>(new Map());
  
  // Update ref whenever watchlist changes
  useEffect(() => {
    watchlistRef.current = watchlist;
  }, [watchlist]);

  const toggleSort = (field: 'ticker' | 'price' | 'changePct' | 'volume') => {
    if (sortBy === field) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortDir(field === 'ticker' ? 'asc' : 'desc');
    }
  };

  const sortedWatchlist = useMemo(() => {
    const items = [...watchlist];
    items.sort((a, b) => {
      if (sortBy === 'ticker') {
        const cmp = a.ticker.localeCompare(b.ticker);
        return sortDir === 'asc' ? cmp : -cmp;
      } else if (sortBy === 'price') {
        const aVal = quotes[a.ticker]?.price;
        const bVal = quotes[b.ticker]?.price;
        const aNum = typeof aVal === 'number' ? aVal : Number.NEGATIVE_INFINITY;
        const bNum = typeof bVal === 'number' ? bVal : Number.NEGATIVE_INFINITY;
        const cmp = aNum - bNum;
        return sortDir === 'asc' ? cmp : -cmp;
      } else if (sortBy === 'volume') {
        const aVal = quotes[a.ticker]?.volume;
        const bVal = quotes[b.ticker]?.volume;
        const aNum = typeof aVal === 'number' ? aVal : Number.NEGATIVE_INFINITY;
        const bNum = typeof bVal === 'number' ? bVal : Number.NEGATIVE_INFINITY;
        const cmp = aNum - bNum;
        return sortDir === 'asc' ? cmp : -cmp;
      } else {
        // changePct sorting - use the changePercent field
        const aVal = quotes[a.ticker]?.changePercent;
        const bVal = quotes[b.ticker]?.changePercent;
        const aNum = typeof aVal === 'number' ? aVal : Number.NEGATIVE_INFINITY;
        const bNum = typeof bVal === 'number' ? bVal : Number.NEGATIVE_INFINITY;
        const cmp = aNum - bNum;
        return sortDir === 'asc' ? cmp : -cmp;
      }
    });
    return items;
  }, [watchlist, quotes, sortBy, sortDir, forceUpdate]); // Add forceUpdate dependency

  // Subscribe to quotes via WebSocket using room management
  useEffect(() => {
    console.log('🔄 Watchlist: Initial subscription effect triggered');
    if (watchlist.length === 0) {
      console.log('⚠️ Watchlist: No tickers in watchlist, skipping initial subscriptions');
      return;
    }
    
    console.log(`🔌 Watchlist: Setting up subscriptions for ${watchlist.length} tickers:`, watchlist.map(item => item.ticker));
    
    // Create a map of current tickers to avoid duplicate subscriptions
    const currentTickers = new Set(watchlist.map(item => item.ticker.toUpperCase()));
    
    // Unsubscribe from tickers that are no longer in the watchlist
    for (const [ticker, unsubscribe] of subscriptionsRef.current.entries()) {
      if (!currentTickers.has(ticker)) {
        console.log(`🚪 Watchlist: Unsubscribing from ${ticker} - no longer in watchlist`);
        unsubscribe();
        subscriptionsRef.current.delete(ticker);
      }
    }
    
    // Subscribe to new tickers using room management
    watchlist.forEach(item => {
      const ticker = item.ticker.toUpperCase();
      
      // Skip if already subscribed
      if (subscriptionsRef.current.has(ticker)) {
        console.log(`✅ Watchlist: Already subscribed to ${ticker}, skipping`);
        return;
      }
      
      console.log(`🔌 Watchlist: Creating new subscription for ${ticker}`);
      const unsubscribe = wsClient.subscribe(ticker, (q: QuotePayload) => {
        console.log(`📊 Watchlist: Quote received for ${ticker}:`, q);
        setQuotes(prevQuotes => {
          const newQuotes = { ...prevQuotes, [ticker]: q as any };
          return newQuotes;
        });
        
        // Force a re-render to ensure UI updates
        setForceUpdate(prev => prev + 1);
      });
      
      // Store the unsubscribe function
      subscriptionsRef.current.set(ticker, unsubscribe);
      console.log(`💾 Watchlist: Stored unsubscribe function for ${ticker}`);
    });
    
    console.log(`🏁 Watchlist: Initial subscription setup completed. Total subscriptions: ${subscriptionsRef.current.size}`);
    
    // Cleanup function - only run on component unmount
    return () => {
      console.log('🧹 Watchlist: Component unmounting, cleaning up subscriptions');
      subscriptionsRef.current.forEach((unsubscribe) => {
        unsubscribe();
      });
      subscriptionsRef.current.clear();
    };
  }, []); // Only run once on mount

  // Sync subscriptions when WebSocket connection is ready
  useEffect(() => {
    const checkAndSyncSubscriptions = () => {
      console.log(`🔄 Watchlist: Checking WebSocket connection status: ${wsClient.getStatus()}`);
      
      if (wsClient.getStatus() === 'connected' && watchlist.length > 0) {
        console.log(`🔌 Watchlist: WebSocket connected, checking subscription sync...`);
        
        const currentTickers = new Set(watchlist.map(item => item.ticker.toUpperCase()));
        const currentSubscriptions = new Set(subscriptionsRef.current.keys());
        
        console.log(`📊 Watchlist: Current tickers:`, Array.from(currentTickers));
        console.log(`🔌 Watchlist: Current subscriptions:`, Array.from(currentSubscriptions));
        
        // Check for missing subscriptions
        const missingSubscriptions = Array.from(currentTickers).filter(ticker => !currentSubscriptions.has(ticker));
        if (missingSubscriptions.length > 0) {
          console.log(`⚠️ Watchlist: Missing subscriptions for:`, missingSubscriptions);
          console.log(`🔄 Watchlist: Triggering subscription sync...`);
          
          // Force a re-run of the subscription effect
          setForceUpdate(prev => prev + 1);
        } else {
          console.log(`✅ Watchlist: All subscriptions are properly synced`);
        }
      }
    };

    // Check immediately
    checkAndSyncSubscriptions();
    
    // Set up interval to check periodically
    const syncInterval = setInterval(checkAndSyncSubscriptions, 2000); // Check every 2 seconds
    
    return () => clearInterval(syncInterval);
  }, [watchlist, forceUpdate]); // Depend on watchlist and forceUpdate

  // Listen for WebSocket connection state changes
  useEffect(() => {
    console.log('🔄 Watchlist: Setting up WebSocket connection state listener');
    
    // Subscribe to room state change events from WebSocket client (includes connection status)
    const unsubscribeRoomStateChange = wsClient.onRoomStateChange(() => {
      console.log('🔄 Watchlist: WebSocket state change detected, triggering update');
      // Force a re-render to update connection status indicators
      setForceUpdate(prev => prev + 1);
    });

    return () => {
      console.log('🔄 Watchlist: Cleaning up WebSocket connection state listener');
      unsubscribeRoomStateChange();
    };
  }, []); // Only run once on mount

  // Handle watchlist changes without clearing subscriptions
  useEffect(() => {
    console.log(`🔄 Watchlist: Change effect triggered - watchlist length: ${watchlist.length}`);
    console.log(`📊 Watchlist: Current watchlist:`, watchlist.map(item => item.ticker));
    console.log(`🔌 Watchlist: Current subscriptions:`, Array.from(subscriptionsRef.current.keys()));
    
    // Get current tickers (even if empty)
    const currentTickers = new Set(watchlist.map(item => item.ticker.toUpperCase()));
    console.log(`🎯 Watchlist: Current tickers set:`, Array.from(currentTickers));
    
    // Unsubscribe from removed tickers (this should always run)
    console.log(`🔍 Watchlist: Checking for tickers to unsubscribe...`);
    for (const [ticker, unsubscribe] of subscriptionsRef.current.entries()) {
      console.log(`🔍 Watchlist: Checking subscription for ${ticker}...`);
      if (!currentTickers.has(ticker)) {
        console.log(`🚪 Watchlist: Unsubscribing from ${ticker} - no longer in watchlist`);
        console.log(`🔌 Watchlist: Calling unsubscribe function for ${ticker}...`);
        try {
          unsubscribe();
          console.log(`✅ Watchlist: Unsubscribe function completed for ${ticker}`);
        } catch (error) {
          console.error(`❌ Watchlist: Error calling unsubscribe for ${ticker}:`, error);
        }
        subscriptionsRef.current.delete(ticker);
        console.log(`🗑️ Watchlist: Removed ${ticker} from subscriptionsRef`);
      } else {
        console.log(`✅ Watchlist: Keeping subscription for ${ticker} - still in watchlist`);
      }
    }
    
    // Only subscribe to new tickers if watchlist is not empty
    if (watchlist.length > 0) {
      console.log(`🔌 Watchlist: Checking for new tickers to subscribe...`);
      watchlist.forEach(item => {
        const ticker = item.ticker.toUpperCase();
        
        if (subscriptionsRef.current.has(ticker)) {
          console.log(`✅ Watchlist: Already subscribed to ${ticker}, skipping`);
          return;
        }
        
        console.log(`🔌 Watchlist: Creating new subscription for ${ticker}...`);
        const unsubscribe = wsClient.subscribe(ticker, (q: QuotePayload) => {
          console.log(`📊 Watchlist: Quote received for ${ticker}:`, q);
          setQuotes(prevQuotes => {
            const newQuotes = { ...prevQuotes, [ticker]: q as any };
            return newQuotes;
          });
          
          setForceUpdate(prev => prev + 1);
        });
        
        // Store the unsubscribe function
        subscriptionsRef.current.set(ticker, unsubscribe);
        console.log(`💾 Watchlist: Stored unsubscribe function for ${ticker}`);
      });
    } else {
      console.log(`⚠️ Watchlist: Watchlist is empty, skipping new subscriptions but cleanup was done above`);
    }
    
    console.log(`🏁 Watchlist: Change effect completed`);
    console.log(`🔌 Watchlist: Final subscriptions:`, Array.from(subscriptionsRef.current.keys()));
  }, [watchlist]); // This effect handles watchlist changes

  const handleAddTicker = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTicker.trim()) return;

    const success = await addTicker(newTicker);
    if (success) {
      setNewTicker('');
    }
  };

  const handleRemoveTicker = async (ticker: string) => {
    await removeTicker(ticker);
  };

  const getPriceColor = (changePercent: number) => {
    if (changePercent > 0) return 'text-green-400';
    if (changePercent < 0) return 'text-red-400';
    return 'text-slate-400';
  };

  // Format volume with abbreviations
  const formatVolume = (volume: number) => {
    if (volume >= 1_000_000_000) return `${(volume / 1_000_000_000).toFixed(1)}B`;
    if (volume >= 1_000_000) return `${(volume / 1_000_000).toFixed(1)}M`;
    if (volume >= 1_000) return `${(volume / 1_000).toFixed(1)}K`;
    return volume.toString();
  };

  return (
    <div className={`${fullHeight ? 'h-full' : ''} flex flex-col bg-gradient-to-br from-slate-800 to-slate-700 border-r border-slate-700 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-1 border-b border-slate-700 bg-gradient-to-br from-slate-800 to-slate-700">
        <div className="flex items-center gap-1">
          <div className="w-5 h-5 bg-gradient-to-r from-blue-500 to-blue-400 rounded-lg flex items-center justify-center">
            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <h2 className="text-xs font-semibold text-slate-100">Watchlist</h2>
          {/* WebSocket Connection Status */}
          <div className={`ml-2 w-2 h-2 rounded-full ${
            wsClient.getStatus() === 'connected' ? 'bg-green-400' : 
            wsClient.getStatus() === 'connecting' ? 'bg-yellow-400' : 
            wsClient.getStatus() === 'disconnecting' ? 'bg-orange-400' : 'bg-red-400'
          }`} 
               title={`WebSocket: ${wsClient.getStatus()}`} />
          {/* Connection Status Text */}
          <div className="ml-1 text-xs text-slate-400">
            {wsClient.getStatus() === 'connected' ? (
              <span>connected</span>
            ) : wsClient.getStatus() === 'connecting' ? (
              <span className="text-yellow-400">connecting...</span>
            ) : wsClient.getStatus() === 'disconnecting' ? (
              <span className="text-orange-400">disconnecting...</span>
            ) : (
              <span className="text-red-400">disconnected</span>
            )}
          </div>
        </div>
        <div className="text-xs text-slate-400">
          {Object.keys(quotes).length > 0 ? (
            <span>{Object.keys(quotes).length} symbols</span>
          ) : (
            <span>No quotes</span>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {/* Add Ticker Form */}
        <div className="p-1 border-b border-slate-700 bg-slate-800/50">
          <form onSubmit={handleAddTicker} className="flex gap-1">
            <input
              type="text"
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
              placeholder="Add ticker..."
              className="flex-1 px-2 py-0.5 text-xs bg-slate-700 border border-slate-600 rounded focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400/50 text-slate-100 placeholder-slate-400"
            />
            <button
              type="submit"
              className="px-2 py-0.5 text-xs bg-gradient-to-r from-blue-500 to-blue-400 text-white rounded hover:from-blue-600 hover:to-blue-500 transition-all duration-200 font-medium"
            >
              Add
            </button>
          </form>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <LoadingSpinner />
            <p className="text-sm text-slate-400 mt-2">Loading watchlist...</p>
          </div>
        )}

        {/* Empty State */}
        {!loading && watchlist.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="w-16 h-16 bg-gradient-to-br from-slate-800 to-slate-700 rounded-full flex items-center justify-center mb-3">
              <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            </div>
            <p className="text-sm text-slate-400 mb-2">No tickers in watchlist</p>
            <p className="text-xs text-slate-500">Add some tickers to start tracking</p>
          </div>
        )}

        {/* Watchlist Content */}
        {!loading && watchlist.length > 0 && (
            <div className="p-1">
            {/* Sorting Header */}
            <div className="flex items-center text-xs font-medium text-slate-400 mb-1 pb-1 border-b border-slate-600">
              <div className="w-1/5 text-left">
                <button
                  onClick={() => toggleSort('ticker')}
                  className={`hover:text-slate-100 transition-colors duration-200 cursor-pointer ${
                    sortBy === 'ticker' ? 'text-slate-100' : ''
                  }`}
                  title="Sort by ticker"
                >
                  Ticker
                  {sortBy === 'ticker' && (
                    <svg className={`w-3 h-3 inline ml-1 transition-transform duration-200 ${sortDir === 'desc' ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                    </svg>
                  )}
                </button>
              </div>
              <div className="w-1/4 text-left">
                <button
                  onClick={() => toggleSort('price')}
                  className={`hover:text-slate-100 transition-colors duration-200 cursor-pointer ${
                    sortBy === 'price' ? 'text-slate-100' : ''
                  }`}
                  title="Sort by price"
                >
                  Price
                  {sortBy === 'price' && (
                    <svg className={`w-3 h-3 inline ml-1 transition-transform duration-200 ${sortDir === 'desc' ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                    </svg>
                  )}
                </button>
              </div>
              <div className="w-1/5 text-left">
                <button
                  onClick={() => toggleSort('changePct')}
                  className={`hover:text-slate-100 transition-colors duration-200 cursor-pointer ${
                    sortBy === 'changePct' ? 'text-slate-100' : ''
                  }`}
                  title="Sort by change percentage"
                >
                  Chg%
                  {sortBy === 'changePct' && (
                    <svg className={`w-3 h-3 inline ml-1 transition-transform duration-200 ${sortDir === 'desc' ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                    </svg>
                  )}
                </button>
              </div>
              <div className="w-1/6 text-left ml-2">
                <button
                  onClick={() => toggleSort('volume')}
                  className={`hover:text-slate-100 transition-colors duration-200 cursor-pointer ${
                    sortBy === 'volume' ? 'text-slate-100' : ''
                  }`}
                  title="Sort by volume"
                >
                  Volume
                  {sortBy === 'volume' && (
                    <svg className={`w-3 h-3 inline ml-1 transition-transform duration-200 ${sortDir === 'desc' ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                    </svg>
                  )}
                </button>
              </div>
              <div className="w-1/12"></div> {/* Spacer for remove button */}
            </div>

            {/* Watchlist Items */}
            <div className="space-y-0" key={`watchlist-${forceUpdate}`}>
              {sortedWatchlist.map((item, index) => {
                const quote = quotes[item.ticker];
                const colorClass = quote ? getPriceColor(quote.changePercent) : 'text-slate-400';
                
                return (
                  <div
                    key={`${item.ticker}-${forceUpdate}-${quote?.timestamp || 'no-quote'}`}
                    className={`flex items-center p-1 hover:bg-slate-700/50 transition-colors duration-200 ${
                      index % 2 === 0 ? 'bg-slate-700/20' : ''
                    }`}
                  >
                    <div className="w-1/5 font-bold text-slate-100 truncate group-hover:text-blue-400 transition-colors duration-200">
                      {item.ticker}
                    </div>
                    
                    {quote ? (
                      <>
                        <div className="w-1/4 text-slate-100 font-medium transition-all duration-200">
                          <span className={`${forceUpdate > 0 ? 'animate-pulse' : ''}`}>
                            {quote.price.toFixed(2)}
                          </span>
                        </div>
                        <div className={`w-1/5 font-medium ${colorClass} transition-all duration-200`}>
                          <span className={`${forceUpdate > 0 ? 'animate-pulse' : ''}`}>
                            {quote.changePercent > 0 ? '+' : ''}{quote.changePercent.toFixed(2)}%
                          </span>
                        </div>
                        <div className="w-1/6 text-slate-400 text-xs ml-2 transition-all duration-200">
                          <span className={`${forceUpdate > 0 ? 'animate-pulse' : ''}`}>
                            {formatVolume(quote.volume)}
                          </span>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="w-1/4 text-slate-400">
                          --
                        </div>
                        <div className="w-1/5 text-slate-400">
                          --
                        </div>
                        <div className="w-1/6 text-slate-400 ml-2">
                          --
                        </div>
                      </>
                    )}
                    
                    <div className="w-1/12 flex justify-end">
                      <button
                        onClick={() => handleRemoveTicker(item.ticker)}
                        className="p-1 text-slate-400 hover:text-red-400 hover:bg-red-950/20 rounded transition-colors duration-200"
                        title="Remove ticker"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Watchlist;
