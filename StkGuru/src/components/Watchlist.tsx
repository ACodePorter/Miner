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
  title?: string;
}

const Watchlist: React.FC<WatchlistProps> = ({ className = '', fullHeight = true, title = 'Watchlist' }) => {
  const { watchlist, loading, error, addTicker, removeTicker, clearError } = useWatchlist();
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
    if (change > 0) return 'text-green-600';
    if (change < 0) return 'text-red-600';
    return 'text-gray-600';
  };

  const getChangeIcon = (change: number) => {
    if (change > 0) return '↗';
    if (change < 0) return '↘';
    return '→';
  };

  return (
    <div className={`${fullHeight ? 'h-screen' : ''} flex flex-col bg-gray-50 border-r border-gray-200 ${className}`}>
      {/* Header */}
      <div className="p-2 border-b border-gray-200 bg-white">
        <h2 className="text-sm font-semibold text-gray-800 mb-2">{title}</h2>
        
        {/* Add Ticker Form */}
        <form onSubmit={handleAddTicker} className="flex gap-1">
          <input
            type="text"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            placeholder="Add ticker..."
            className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={isAdding}
          />
          <button
            type="submit"
            disabled={isAdding || !newTicker.trim()}
            className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isAdding ? '...' : 'Add'}
          </button>
        </form>

        {/* Error Display */}
        {error && (
          <div className="mt-2 p-2 text-xs text-red-600 bg-red-50 rounded border border-red-200">
            {error}
            <button
              onClick={clearError}
              className="ml-2 text-red-800 hover:text-red-900"
            >
              ×
            </button>
          </div>
        )}
      </div>

      {/* Watchlist Items */}
      <div className="flex-1 overflow-y-auto">
        {loading && watchlist.length === 0 ? (
          <div className="p-4 text-center text-sm text-gray-500">
            Loading...
          </div>
        ) : watchlist.length === 0 ? (
          <div className="p-4 text-center text-sm text-gray-500">
            No tickers in watchlist
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {/* Header Row for Sorting */}
            <div className="px-2 py-1 bg-white sticky top-0 z-10">
              <div className="flex items-center text-[11px] font-medium text-gray-500 gap-2">
                <button
                  className={`w-16 text-left hover:text-gray-800 ${sortBy === 'ticker' ? 'text-gray-800' : ''}`}
                  onClick={() => toggleSort('ticker')}
                  title="Sort by ticker"
                >
                  Ticker{sortBy === 'ticker' ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
                </button>
                <span className="w-20 text-right">Price</span>
                <span className="w-16 text-right">Chg</span>
                <button
                  className={`w-16 text-right hover:text-gray-800 ${sortBy === 'changePct' ? 'text-gray-800' : ''}`}
                  onClick={() => toggleSort('changePct')}
                  title="Sort by change %"
                >
                  Chg%{sortBy === 'changePct' ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
                </button>
                <span className="w-16 text-right">Vol</span>
                <span className="ml-auto w-4" />
              </div>
            </div>

            {sortedWatchlist.map((item) => {
              const quote = quotes[item.ticker];
              const colorClass = quote ? getPriceColor(quote.change) : 'text-gray-400';
              const priceText = quote ? `$${quote.price.toFixed(2)}` : '—';
              const changeText = quote ? `${quote.change > 0 ? '+' : ''}${quote.change.toFixed(2)}` : '—';
              const changePctText = quote ? `(${quote.changePercent.toFixed(2)}%)` : '—';
              const formatVolume = (v?: number) => {
                if (v === undefined || v === null) return '—';
                if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
                if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
                if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
                return String(v);
              };
              const volText = quote ? formatVolume(quote.volume) : '—';

              return (
                <div key={item.ticker} className="px-2 py-1 hover:bg-gray-50 transition-colors duration-150">
                  <div className="flex items-center text-xs gap-2">
                    <span className="w-16 font-bold text-gray-900 truncate">
                      {item.ticker}
                    </span>
                    <span className={`w-20 text-right font-semibold ${colorClass}`}>
                      {priceText}
                    </span>
                    <span className={`w-16 text-right ${colorClass}`}>
                      {changeText}
                    </span>
                    <span className={`w-16 text-right ${colorClass}`}>
                      {changePctText}
                    </span>
                    <span className="w-16 text-right text-gray-500">
                      {volText}
                    </span>
                    <button
                      onClick={() => handleRemoveTicker(item.ticker)}
                      className="ml-auto p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                      title="Remove from watchlist"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default Watchlist;
