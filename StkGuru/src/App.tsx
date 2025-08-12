import './App.css'
import { lazy, Suspense, useState } from 'react'
import ExtensionWarning from './components/ExtensionWarning';
import LoadingSpinner from './components/LoadingSpinner';
import Screener from './pages/Screener';

// Lazy load heavy chart components for code splitting
const MarketPeChart = lazy(() => import('./components/MarketPeChart'))
const MarketBreathChart = lazy(() => import('./components/MarketBreathChart'))
const OHLCVChart = lazy(() => import('./components/OHLCVChart'))

function App() {
  return (
    <div className="App min-h-screen bg-gradient-primary">
      <ExtensionWarning />
      <Tabs />
    </div>
  );
}

export default App;

function Tabs() {
  const [active, setActive] = useState<'home' | 'screener'>('home')
  return (
    <div className="min-h-screen flex flex-col">
      {/* Enhanced Header with gradient background */}
      <div className="bg-gradient-to-br from-slate-800 to-slate-700 border-b border-slate-700 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <div className="w-6 h-6 bg-gradient-to-r from-blue-500 to-blue-400 rounded-lg flex items-center justify-center">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <h1 className="text-xl font-bold text-slate-100">StkGuru</h1>
                <span className="text-xs text-slate-400 bg-slate-700 px-2 py-0.5 rounded-full">Pro</span>
              </div>
            </div>
            
            {/* Navigation Tabs */}
            <div className="flex space-x-1 bg-slate-700 rounded-lg p-1">
              <button
                onClick={() => setActive('home')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                  active === 'home' 
                    ? 'bg-gradient-to-r from-blue-500 to-blue-400 text-white shadow-lg' 
                    : 'text-slate-300 hover:text-slate-100 hover:bg-slate-600'
                }`}
              >
                <div className="flex items-center space-x-1.5">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5a2 2 0 012-2h4a2 2 0 012 2v6H8V5z" />
                  </svg>
                  <span>Dashboard</span>
                </div>
              </button>
              <button
                onClick={() => setActive('screener')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                  active === 'screener' 
                    ? 'bg-gradient-to-r from-blue-500 to-blue-400 text-white shadow-lg' 
                    : 'text-slate-300 hover:text-slate-100 hover:bg-slate-600'
                }`}
              >
                <div className="flex items-center space-x-1.5">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <span>Screener</span>
                </div>
              </button>
            </div>

            {/* User Profile Section */}
            <div className="flex items-center space-x-2">
              <div className="text-right">
                <p className="text-xs font-medium text-slate-100">Welcome back</p>
                <p className="text-xs text-slate-400">Ready to trade?</p>
              </div>
              <div className="w-6 h-6 bg-gradient-to-r from-blue-500 to-blue-400 rounded-full flex items-center justify-center">
                <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        {active === 'home' ? (
          <HomeContent />
        ) : (
          <Screener />
        )}
      </div>
    </div>
  );
}

function HomeContent() {
  return (
    <div className="p-4 space-y-4 animate-fade-in">
      {/* Welcome Section */}
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-slate-100 mb-1">Market Overview</h2>
        <p className="text-slate-400 text-sm">Real-time insights into global markets and indices</p>
      </div>

      {/* Market Indices Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
        <Suspense fallback={<LoadingSpinner text="Loading SPX Chart..." />}>
          <div className="chart-container p-3 card-hover">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-slate-100">S&P 500 (SPX)</h3>
              <div className="flex items-center space-x-2">
                <div className="w-2.5 h-2.5 bg-blue-500 rounded-full"></div>
                <span className="text-xs text-slate-400">Live</span>
              </div>
            </div>
            <MarketPeChart 
              indexId="spx" 
              displayName="S&P 500 (SPX)" 
              color="#3b82f6"
              autoRefresh={true}
              refreshInterval={60 * 60 * 1000}
            />
          </div>
        </Suspense>
        
        <Suspense fallback={<LoadingSpinner text="Loading HSI Chart..." />}>
          <div className="chart-container p-3 card-hover">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-slate-100">Hang Seng Index (HSI)</h3>
              <div className="flex items-center space-x-2">
                <div className="w-2.5 h-2.5 bg-purple-500 rounded-full"></div>
                <span className="text-xs text-slate-400">Live</span>
              </div>
            </div>
            <MarketPeChart 
              indexId="hsi" 
              displayName="Hang Seng Index (HSI)" 
              color="#8b5cf6"
              autoRefresh={true}
              refreshInterval={60 * 60 * 1000}
            />
          </div>
        </Suspense>
      </div>

      {/* Market Breadth Section */}
      <div className="market-breadth-section animate-fade-in-up" style={{ animationDelay: '0.4s' }}>
        <div className="chart-container p-3 card-hover">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-semibold text-slate-100">Market Breadth Analysis</h3>
            <div className="flex items-center space-x-2">
              <div className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-xs text-slate-400">Analyzing</span>
            </div>
          </div>
          <Suspense fallback={<LoadingSpinner text="Loading Market Breadth..." />}>
            <MarketBreathChart indexId="spx" />
          </Suspense>
        </div>
      </div>

      {/* OHLCV Chart Section */}
      <div className="animate-fade-in-up" style={{ animationDelay: '0.6s' }}>
        <div className="chart-container p-3 card-hover">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-semibold text-slate-100">Market Volume Analysis</h3>
            <div className="flex items-center space-x-2">
              <div className="w-2.5 h-2.5 bg-orange-500 rounded-full"></div>
              <span className="text-xs text-slate-400">Updated</span>
            </div>
          </div>
          <Suspense fallback={<LoadingSpinner text="Loading OHLCV Chart..." />}>
            <OHLCVChart autoRefresh={true} refreshInterval={60 * 60 * 1000} />
          </Suspense>
        </div>
      </div>

      {/* Quick Stats Section */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 animate-fade-in-up" style={{ animationDelay: '0.8s' }}>
        <div className="bg-gradient-to-br from-slate-800 to-slate-700 p-3 rounded-lg border border-slate-700 card-hover">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-xs">Total Volume</p>
              <p className="text-xl font-bold text-slate-100">$2.4B</p>
            </div>
            <div className="w-10 h-10 bg-gradient-to-r from-green-500 to-green-400 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
          </div>
        </div>
        
        <div className="bg-gradient-to-br from-slate-800 to-slate-700 p-3 rounded-lg border border-slate-700 card-hover">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-xs">Active Tickers</p>
              <p className="text-xl font-bold text-slate-100">1,247</p>
            </div>
            <div className="w-10 h-10 bg-gradient-to-r from-yellow-500 to-yellow-400 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
              </svg>
            </div>
          </div>
        </div>
        
        <div className="bg-gradient-to-br from-slate-800 to-slate-700 p-3 rounded-lg border border-slate-700 card-hover">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-xs">Market Cap</p>
              <p className="text-xl font-bold text-slate-100">$45.2T</p>
            </div>
            <div className="w-10 h-10 bg-gradient-to-r from-purple-500 to-purple-400 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
              </svg>
            </div>
          </div>
        </div>
        
        <div className="bg-gradient-to-br from-slate-800 to-slate-700 p-3 rounded-lg border border-slate-700 card-hover">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-xs">Risk Level</p>
              <p className="text-xl font-bold text-slate-100">Medium</p>
            </div>
            <div className="w-10 h-10 bg-gradient-to-r from-orange-500 to-orange-400 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
