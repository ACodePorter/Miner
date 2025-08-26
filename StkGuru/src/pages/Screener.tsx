import React, { useCallback, useMemo, useState, useRef, useEffect } from 'react';
import Watchlist from '../components/Watchlist';
import ChartTile from '../components/ChartTile';
import RealTimeMonitor from '../components/RealTimeMonitor';

const Screener: React.FC = () => {
  const [tiles, setTiles] = useState<{ id: string; ticker: string; timeframe: string }[]>([]);
  const [showAddChartDialog, setShowAddChartDialog] = useState(false);
  const [newChartTicker, setNewChartTicker] = useState('AAPL');
  const [newChartTimeframe, setNewChartTimeframe] = useState('65m');
  const [showSidebar, setShowSidebar] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartX, setDragStartX] = useState(0);
  const sidebarRef = useRef<HTMLDivElement>(null);

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
    // On mobile and limited width, always show 1 chart per row
    if (n <= 1) return 'grid-cols-1';
    if (n === 2) return 'grid-cols-1 lg:grid-cols-2';
    if (n <= 4) return 'grid-cols-1 lg:grid-cols-2';
    return 'grid-cols-1 lg:grid-cols-2 xl:grid-cols-3';
  }, [tiles.length]);

  const toggleSidebar = useCallback(() => {
    setShowSidebar(prev => !prev);
  }, []);

  const closeSidebar = useCallback(() => {
    setShowSidebar(false);
  }, []);

  // Touch/swipe handling for mobile sidebar
  useEffect(() => {
    const sidebar = sidebarRef.current;
    if (!sidebar) return;

    const handleTouchStart = (e: TouchEvent) => {
      setDragStartX(e.touches[0].clientX);
      setIsDragging(true);
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!isDragging) return;
      e.preventDefault();
    };

    const handleTouchEnd = (e: TouchEvent) => {
      if (!isDragging) return;
      
      const touchEndX = e.changedTouches[0].clientX;
      const diffX = touchEndX - dragStartX;
      
      // Swipe right to open, swipe left to close
      if (Math.abs(diffX) > 50) { // Minimum swipe distance
        if (diffX > 0 && !showSidebar) {
          setShowSidebar(true);
        } else if (diffX < 0 && showSidebar) {
          setShowSidebar(false);
        }
      }
      
      setIsDragging(false);
    };

    sidebar.addEventListener('touchstart', handleTouchStart, { passive: false });
    sidebar.addEventListener('touchmove', handleTouchMove, { passive: false });
    sidebar.addEventListener('touchend', handleTouchEnd, { passive: false });

    return () => {
      sidebar.removeEventListener('touchstart', handleTouchStart);
      sidebar.removeEventListener('touchmove', handleTouchMove);
      sidebar.removeEventListener('touchend', handleTouchEnd);
    };
  }, [isDragging, dragStartX, showSidebar]);

  // Close sidebar when clicking outside on mobile
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (showSidebar && window.innerWidth < 768) {
        const target = e.target as Element;
        if (!sidebarRef.current?.contains(target) && !target.closest('[data-sidebar-toggle]')) {
          setShowSidebar(false);
        }
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showSidebar]);

  return (
    <div className="flex min-h-screen bg-gradient-primary">
      {/* Mobile Sidebar Toggle Button */}
      <button
        data-sidebar-toggle
        onClick={toggleSidebar}
        className="fixed top-4 left-4 z-40 md:hidden bg-slate-800 border border-slate-700 rounded-lg p-3 text-slate-300 hover:bg-slate-700 hover:text-slate-100 transition-all duration-200 touch-manipulation"
        aria-label="Toggle sidebar"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {/* Enhanced Watchlist Sidebar - Mobile Responsive */}
      <div 
        ref={sidebarRef}
        className={`
          fixed inset-y-0 left-0 z-30 w-80 bg-slate-900 border-r border-slate-700 transform transition-transform duration-300 ease-in-out
          ${showSidebar ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0 md:flex-shrink-0
          touch-pan-y
        `}
      >
        {/* Mobile Close Button */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700 md:hidden">
          <h2 className="text-lg font-semibold text-slate-100">Watchlist</h2>
          <button
            onClick={closeSidebar}
            className="text-slate-400 hover:text-slate-100 transition-colors p-2 touch-manipulation"
            aria-label="Close sidebar"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        <Watchlist className="h-full" fullHeight />
      </div>

      {/* Mobile Sidebar Backdrop */}
      {showSidebar && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-20 md:hidden"
          onClick={closeSidebar}
        />
      )}
      
      {/* Main Content Area */}
      <main className="flex-1 overflow-auto">
        <div className="p-2 md:p-1">
          {/* Header Section */}
          <div className="mb-1 mt-12 md:mt-0">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-2 space-y-1 sm:space-y-0">
              <div>
                <h1 className="text-base md:text-lg font-bold text-slate-100 mb-0.5">Market Screener</h1>
                <p className="text-slate-400 text-xs md:text-sm">Analyze multiple tickers with real-time charts and indicators</p>
              </div>
              <div className="flex items-center space-x-3">
                <div className="text-right">
                  <p className="text-xs text-slate-400">Active Charts</p>
                  <p className="text-lg md:text-xl font-bold text-slate-100">{tiles.length}</p>
                </div>
                <button 
                  onClick={addTile} 
                  className="btn-primary px-3 md:px-3 py-1.5 md:py-1.5 rounded-lg text-xs md:text-sm font-medium flex items-center space-x-1 md:space-x-2 touch-manipulation min-h-[44px] min-w-[44px] md:min-h-0 md:min-w-0"
                >
                  <svg className="w-4 h-4 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  <span className="hidden sm:inline">Add Chart</span>
                  <span className="sm:hidden">Add</span>
                </button>
              </div>
            </div>
          </div>

          {/* Charts Grid */}
          {tiles.length === 0 ? (
            <div className="text-center py-8 md:py-12">
              <div className="w-16 h-16 md:w-20 md:h-20 mx-auto mb-3 bg-gradient-to-br from-slate-800 to-slate-700 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 md:w-10 md:h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="text-sm md:text-base font-medium text-slate-100 mb-1">No charts yet</h3>
              <p className="text-slate-400 text-xs md:text-sm mb-4 px-4">Create your first chart to start analyzing the market</p>
              <button
                onClick={() => setShowAddChartDialog(true)}
                className="btn-primary text-sm md:text-base px-4 py-2 touch-manipulation min-h-[44px]"
              >
                Create Your First Chart
              </button>
            </div>
          ) : (
            <div className="w-full">
              <div className={`grid ${gridCols} gap-2 md:gap-3 lg:gap-1 chart-grid-mobile`}>
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
            </div>
          )}
        </div>
      </main>

      {/* Add Chart Dialog - Mobile Responsive */}
      {showAddChartDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in p-4" onClick={handleDialogBackdropClick}>
          <div className="bg-gradient-to-br from-slate-800 to-slate-700 border border-slate-700 rounded-xl p-4 w-full max-w-sm shadow-2xl animate-scale-in">
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
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100 placeholder-slate-400 text-sm touch-manipulation"
                  autoFocus
                />
              </div>
              
              <div>
                <label className="block text-xs font-medium text-slate-100 mb-1">
                  Timeframe
                </label>
                <select
                  value={newChartTimeframe}
                  onChange={(e) => setNewChartTimeframe(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100 text-sm touch-manipulation"
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
                className="flex-1 px-4 py-2 text-xs font-medium text-slate-300 bg-slate-700 border border-slate-600 rounded-lg hover:bg-slate-600 hover:text-slate-100 transition-all duration-200 touch-manipulation min-h-[44px]"
              >
                Cancel
              </button>
              <button
                onClick={confirmAddChart}
                className="flex-1 px-4 py-2 text-xs font-medium text-white bg-gradient-to-r from-blue-500 to-blue-400 rounded-lg hover:shadow-lg transition-all duration-200 touch-manipulation min-h-[44px]"
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


