import React, { useState, useEffect, useMemo } from 'react';
import { useWatchlist } from '../hooks/useWatchlist';
// apiConfig not needed for WS quotes
import { wsClient, type QuotePayload } from '../utils/wsClient';

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
  const { watchlist, loading, error, addTicker, removeTicker } = useWatchlist();
  const [newTicker, setNewTicker] = useState('');
  const [quotes, setQuotes] = useState<Record<string, QuoteData>>({});
  const [isAdding, setIsAdding] = useState(false);
  const [sortBy, setSortBy] = useState<'ticker' | 'changePct'>('ticker');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const toggleSort = (field: 'ticker' | 'changePct') => {
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
      }
      const aVal = quotes[a.ticker]?.changePercent;
      const bVal = quotes[b.ticker]?.changePercent;
      const aNum = typeof aVal === 'number' ? aVal : Number.NEGATIVE_INFINITY;
      const bNum = typeof bVal === 'number' ? bVal : Number.NEGATIVE_INFINITY;
      const cmp = aNum - bNum;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return items;
  }, [watchlist, quotes, sortBy, sortDir]);

  // Subscribe to quotes via WebSocket, no HTTP polling
  useEffect(() => {
    if (watchlist.length === 0) return;
    const unsubscribers = watchlist.map(item =>
      wsClient.subscribe(item.ticker, (q: QuotePayload) => {
        const sym = q.symbol?.toUpperCase?.() || item.ticker;
        setQuotes(prev => ({ ...prev, [sym]: q as any }));
      })
    );
    return () => {
      unsubscribers.forEach(unsub => unsub());
    };
  }, [watchlist]);

  const handleAddTicker = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTicker.trim()) return;

    setIsAdding(true);
    const success = await addTicker(newTicker);
    if (success) {
      setNewTicker('');
    }
    setIsAdding(false);
  };

  const handleRemoveTicker = async (ticker: string) => {
    await removeTicker(ticker);
  };

  const getPriceColor = (change: number) => {
    if (change > 0) return 'text-green-400';
    if (change < 0) return 'text-red-400';
    return 'text-slate-400';
  };

  return (
    <div className={`${fullHeight ? 'h-full' : ''} flex flex-col bg-gradient-to-br from-slate-800 to-slate-700 border-r border-slate-700 ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-slate-700 bg-gradient-to-br from-slate-800 to-slate-700">
        <div className="flex items-center space-x-2 mb-3">
          <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-blue-400 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-100">Watchlist</h3>
            <p className="text-xs text-slate-400">Track your favorite stocks</p>
          </div>
        </div>

        {/* Add Ticker Form */}
        <form onSubmit={handleAddTicker} className="flex space-x-2">
          <input
            type="text"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            placeholder="Add ticker..."
            className="flex-1 px-2 py-1.5 bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100 placeholder-slate-400 pr-12 text-sm"
            disabled={isAdding}
          />
          <button
            type="submit"
            disabled={isAdding || !newTicker.trim()}
            className="absolute right-2 top-1/2 transform -translate-y-1/2 w-6 h-6 bg-gradient-to-r from-blue-500 to-blue-400 rounded-lg flex items-center justify-center text-white hover:shadow-glow transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isAdding ? (
              <svg className="w-3 h-3 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            ) : (
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            )}
          </button>
        </form>

        {error && (
          <div className="mt-2 text-xs text-red-400 bg-red-950/20 px-2 py-1 rounded border border-red-800/30">
            {error}
          </div>
        )}
      </div>

      {/* Watchlist Content */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="text-center py-8">
            <div className="w-12 h-12 mx-auto mb-3 bg-gradient-to-r from-blue-500 to-blue-400 rounded-full flex items-center justify-center animate-pulse">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
            <p className="text-sm text-slate-400">Loading watchlist...</p>
          </div>
        ) : watchlist.length === 0 ? (
          <div className="text-center py-8">
            <div className="w-12 h-12 mx-auto mb-3 bg-gradient-to-br from-slate-800 to-slate-700 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <h3 className="text-base font-medium text-slate-100 mb-1">No tickers yet</h3>
            <p className="text-slate-400 text-sm">Add your first ticker to get started</p>
          </div>
        ) : (
          <div className="p-3">
            {/* Sorting Header */}
            <div className="flex items-center text-xs font-medium text-slate-400 gap-2 mb-2 pb-2 border-b border-slate-600">
              <button
                onClick={() => toggleSort('ticker')}
                className={`w-16 text-left hover:text-slate-100 transition-colors duration-200 ${
                  sortBy === 'ticker' ? 'text-slate-100' : ''
                }`}
              >
                Ticker
              </button>
              <button
                onClick={() => toggleSort('changePct')}
                className="w-16 text-right hover:text-slate-100 transition-colors duration-200"
              >
                Price
              </button>
              <button
                onClick={() => toggleSort('changePct')}
                className={`w-16 text-right hover:text-slate-100 transition-colors duration-200 ${
                  sortBy === 'changePct' ? 'text-slate-100' : ''
                }`}
              >
                Change %
              </button>
            </div>

            {/* Watchlist Items */}
            <div className="space-y-1">
              {sortedWatchlist.map((item) => {
                const quote = quotes[item.ticker];
                const colorClass = quote ? getPriceColor(quote.change) : 'text-slate-400';
                
                return (
                  <div
                    key={item.ticker}
                    className="group flex items-center justify-between p-2 hover:bg-slate-700/50 rounded-lg transition-colors duration-200"
                  >
                    <span className="w-16 font-bold text-slate-100 truncate group-hover:text-blue-400 transition-colors duration-200">
                      {item.ticker}
                    </span>
                    
                    {quote ? (
                      <>
                        <span className="w-16 text-right text-slate-100">
                          ${quote.price.toFixed(2)}
                        </span>
                        <span className={`w-16 text-right ${colorClass}`}>
                          {quote.change > 0 ? '+' : ''}{quote.change.toFixed(2)}%
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="w-16 text-right text-slate-400">
                          --
                        </span>
                        <span className="w-16 text-right text-slate-400">
                          --
                        </span>
                      </>
                    )}
                    
                    <button
                      onClick={() => handleRemoveTicker(item.ticker)}
                      className="ml-auto p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-950/20 rounded-lg transition-all duration-200 opacity-0 group-hover:opacity-100"
                      title="Remove ticker"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
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
