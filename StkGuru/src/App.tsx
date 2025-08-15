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
        <div className="max-w-7xl mx-auto px-4 py-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-5 h-5 bg-gradient-to-r from-blue-500 to-blue-400 rounded-lg flex items-center justify-center">
                <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h1 className="text-lg font-bold text-slate-100">StkGuru</h1>
              <span className="text-xs text-slate-400 bg-slate-700 px-1.5 py-0.5 rounded-full">Pro</span>
            </div>
            
            {/* Navigation Tabs */}
            <div className="flex space-x-1 bg-slate-700 rounded-lg p-0.5">
              <button
                onClick={() => setActive('home')}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all duration-200 flex items-center space-x-1 ${
                  active === 'home' 
                    ? 'bg-gradient-to-r from-blue-500 to-blue-400 text-white shadow-lg' 
                    : 'text-slate-300 hover:text-slate-100 hover:bg-slate-600'
                }`}
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5a2 2 0 012-2h4a2 2 0 012 2v6H8V5z" />
                </svg>
                <span>Dashboard</span>
              </button>
              <button
                onClick={() => setActive('screener')}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all duration-200 flex items-center space-x-1 ${
                  active === 'screener' 
                    ? 'bg-gradient-to-r from-blue-500 to-blue-400 text-white shadow-lg' 
                    : 'text-slate-300 hover:text-slate-100 hover:bg-slate-600'
                }`}
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <span>Screener</span>
              </button>
            </div>

            {/* User Profile Section */}
            <div className="flex items-center space-x-2">
              <div className="text-right">
                <p className="text-xs font-medium text-slate-100">Welcome back</p>
                <p className="text-xs text-slate-400">Ready to trade?</p>
              </div>
              <div className="w-5 h-5 bg-gradient-to-r from-blue-500 to-blue-400 rounded-full flex items-center justify-center">
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
    <div className="p-3 space-y-3 animate-fade-in">
      {/* Market Indices Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Suspense fallback={<LoadingSpinner text="Loading SPX Chart..." />}>
          <MarketPeChart 
            indexId="spx" 
            displayName="SPX" 
            color="#3b82f6"
            autoRefresh={true}
            refreshInterval={60 * 60 * 1000}
          />
        </Suspense>
        
        <Suspense fallback={<LoadingSpinner text="Loading HSI Chart..." />}>
          <MarketPeChart 
            indexId="hsi" 
            displayName="HSI" 
            color="#8b5cf6"
            autoRefresh={true}
            refreshInterval={60 * 60 * 1000}
          />
        </Suspense>
      </div>

      {/* Market Breadth Section */}
      <Suspense fallback={<LoadingSpinner text="Loading Market Breadth..." />}>
        <MarketBreathChart indexId="spx" />
      </Suspense>

      {/* OHLCV Chart Section */}
      <Suspense fallback={<LoadingSpinner text="Loading OHLCV Chart..." />}>
        <OHLCVChart autoRefresh={true} refreshInterval={60 * 60 * 1000} />
      </Suspense>
    </div>
  );
}
