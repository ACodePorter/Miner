import React, { useCallback, useMemo, useState } from 'react';
import Watchlist from '../components/Watchlist';
import ChartTile from '../components/ChartTile';

const Screener: React.FC = () => {
  const [tiles, setTiles] = useState<{ id: string; ticker: string; timeframe: string }[]>([]);
  const [showAddChartDialog, setShowAddChartDialog] = useState(false);
  const [newChartTicker, setNewChartTicker] = useState('AAPL');
  const [newChartTimeframe, setNewChartTimeframe] = useState('65m');

  const addTile = useCallback(() => {
    // Open dialog instead of using window.prompt
    setNewChartTicker('AAPL');
    setNewChartTimeframe('65m');
    setShowAddChartDialog(true);
  }, []);

  const confirmAddChart = useCallback(() => {
    const ticker = newChartTicker.toUpperCase();
    if (ticker.trim()) {
      const id = `${ticker}-${Date.now()}`;
      setTiles(prev => [...prev, { id, ticker, timeframe: newChartTimeframe }]);
      setShowAddChartDialog(false);
      setNewChartTicker('AAPL');
    }
  }, [newChartTicker, newChartTimeframe]);

  const cancelAddChart = useCallback(() => {
    setShowAddChartDialog(false);
    setNewChartTicker('AAPL');
  }, []);

  const handleDialogBackdropClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      cancelAddChart();
    }
  }, [cancelAddChart]);

  // Handle escape key and enter key for dialog
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showAddChartDialog) {
        cancelAddChart();
      } else if (e.key === 'Enter' && showAddChartDialog) {
        confirmAddChart();
      }
    };

    if (showAddChartDialog) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [showAddChartDialog, confirmAddChart, cancelAddChart]);

  const removeTile = useCallback((id: string) => {
    setTiles(prev => prev.filter(x => x.id !== id));
  }, []);

  const gridCols = useMemo(() => {
    const n = tiles.length;
    if (n <= 1) return 'grid-cols-1';
    if (n === 2) return 'grid-cols-2';
    if (n <= 4) return 'grid-cols-2';
    return 'grid-cols-3';
  }, [tiles.length]);

  return (
    <div className="flex h-screen">
      <Watchlist className="w-80 flex-shrink-0" fullHeight title="Watchlist" />
      <main className="flex-1 overflow-auto">
        <div className="p-2">
          <div className="mb-2 flex items-center gap-2">
            <button onClick={addTile} className="px-2 py-1 text-xs bg-blue-600 text-white rounded">Add Chart</button>
            <span className="text-xs text-gray-500">Charts: {tiles.length}</span>
          </div>
          <div className={`grid ${gridCols} gap-2`}>
            {tiles.map(t => (
              <ChartTile key={t.id} id={t.id} initialTicker={t.ticker} initialInterval={t.timeframe} onRemove={removeTile} />
            ))}
          </div>
        </div>
      </main>
      
      {/* Add Chart Dialog */}
      {showAddChartDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={handleDialogBackdropClick}>
          <div className="bg-white rounded-lg p-6 w-80 max-w-sm">
            <h3 className="text-lg font-semibold mb-4">Add New Chart</h3>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Ticker Symbol
              </label>
              <input
                type="text"
                value={newChartTicker}
                onChange={(e) => setNewChartTicker(e.target.value.toUpperCase())}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    confirmAddChart();
                  }
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., AAPL"
                autoFocus
              />
            </div>
            
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Timeframe
              </label>
              <select
                value={newChartTimeframe}
                onChange={(e) => setNewChartTimeframe(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="1m">1m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="30m">30m</option>
                <option value="60m">60m</option>
                <option value="65m">65m</option>
                <option value="1d">1d</option>
                <option value="1wk">1wk</option>
                <option value="1mo">1mo</option>
              </select>
            </div>
            
            <div className="flex justify-end space-x-3">
              <button
                onClick={cancelAddChart}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500"
              >
                Cancel
              </button>
              <button
                onClick={confirmAddChart}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Add Chart
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Screener;


