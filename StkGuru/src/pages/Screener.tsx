import React, { useCallback, useMemo, useState } from 'react';
import Watchlist from '../components/Watchlist';
import ChartTile from '../components/ChartTile';
import RealTimeMonitor from '../components/RealTimeMonitor';

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
    <div className="flex min-h-screen bg-gradient-primary">
      {/* Enhanced Watchlist Sidebar */}
      <div className="w-80 flex-shrink-0">
        <Watchlist className="h-full" fullHeight />
      </div>
      
      {/* Main Content Area */}
      <main className="flex-1 overflow-auto">
        <div className="p-4">
          {/* Header Section */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h1 className="text-xl font-bold text-slate-100 mb-1">Market Screener</h1>
                <p className="text-slate-400 text-sm">Analyze multiple tickers with real-time charts and indicators</p>
              </div>
              <div className="flex items-center space-x-3">
                <div className="text-right">
                  <p className="text-xs text-slate-400">Active Charts</p>
                  <p className="text-xl font-bold text-slate-100">{tiles.length}</p>
                </div>
                <button 
                  onClick={addTile} 
                  className="btn-primary px-3 py-1.5 rounded-lg text-sm font-medium flex items-center space-x-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  <span>Add Chart</span>
                </button>
              </div>
            </div>
          </div>

          {/* Charts Grid */}
          {tiles.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-20 h-20 mx-auto mb-3 bg-gradient-to-br from-slate-800 to-slate-700 rounded-full flex items-center justify-center">
                <svg className="w-10 h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="text-base font-medium text-slate-100 mb-1">No charts yet</h3>
              <p className="text-slate-400 text-sm mb-4">Create your first chart to start analyzing the market</p>
              <button
                onClick={() => setShowAddChartDialog(true)}
                className="btn-primary"
              >
                Create Your First Chart
              </button>
            </div>
          ) : (
            <div className={`grid ${gridCols} gap-4`}>
              {tiles.map((tile) => (
                <ChartTile
                  key={tile.id}
                  id={tile.id}
                  initialTicker={tile.ticker}
                  initialInterval={tile.timeframe}
                  onRemove={() => removeTile(tile.id)}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Add Chart Dialog */}
      {showAddChartDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in" onClick={handleDialogBackdropClick}>
          <div className="bg-gradient-to-br from-slate-800 to-slate-700 border border-slate-700 rounded-xl p-4 w-80 max-w-sm shadow-2xl animate-scale-in">
            <div className="flex items-center space-x-2 mb-4">
              <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-blue-400 rounded-lg flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-100">Add New Chart</h3>
                <p className="text-xs text-slate-400">Create a new stock chart</p>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-100 mb-1">
                  Ticker Symbol
                </label>
                <input
                  type="text"
                  value={newChartTicker}
                  onChange={(e) => setNewChartTicker(e.target.value)}
                  placeholder="Enter ticker symbol (e.g., AAPL)"
                  className="w-full px-2 py-1.5 bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100 placeholder-slate-400 text-sm"
                />
              </div>
              
              <div>
                <label className="block text-xs font-medium text-slate-100 mb-1">
                  Timeframe
                </label>
                <select
                  value={newChartTimeframe}
                  onChange={(e) => setNewChartTimeframe(e.target.value)}
                  className="w-full px-2 py-1.5 bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100 text-sm"
                >
                  <option value="1m">1 Minute</option>
                  <option value="5m">5 Minutes</option>
                  <option value="15m">15 Minutes</option>
                  <option value="30m">30 Minutes</option>
                  <option value="65m">1 Hour</option>
                  <option value="1d">Daily</option>
                  <option value="1w">Weekly</option>
                  <option value="1M">Monthly</option>
                </select>
              </div>
            </div>
            
            <div className="flex space-x-2 pt-3">
              <button
                onClick={cancelAddChart}
                className="px-4 py-1.5 text-xs font-medium text-slate-300 bg-slate-700 border border-slate-600 rounded-lg hover:bg-slate-600 hover:text-slate-100 transition-all duration-200"
              >
                Cancel
              </button>
              <button
                onClick={confirmAddChart}
                className="px-4 py-1.5 text-xs font-medium text-white bg-gradient-to-r from-blue-500 to-blue-400 rounded-lg hover:shadow-lg transition-all duration-200"
              >
                Add Chart
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Real-Time Performance Monitor */}
      <RealTimeMonitor />
    </div>
  );
};

export default Screener;


