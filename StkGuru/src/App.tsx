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
    <div className="App">
      <ExtensionWarning />
      <Tabs />
    </div>
  );
}

export default App;

function Tabs() {
  const [active, setActive] = useState<'home' | 'screener'>('home')
  return (
    <div className="h-screen flex flex-col">
      <div className="border-b border-gray-200 bg-white">
        <div className="flex gap-2 px-2 py-1 text-sm">
          <button
            onClick={() => setActive('home')}
            className={`px-3 py-1 rounded ${active === 'home' ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}
          >
            Home
          </button>
          <button
            onClick={() => setActive('screener')}
            className={`px-3 py-1 rounded ${active === 'screener' ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}
          >
            Screener
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        {active === 'home' ? (
          <HomeContent />
        ) : (
          <Screener />
        )}
      </div>
    </div>
  )
}

function HomeContent() {
  return (
    <div className="p-4 space-y-6">
      <div className="grid grid-cols-2 gap-6 animate-fade-in-up pe-charts-grid" style={{ animationDelay: '0.4s' }}>
        <Suspense fallback={<LoadingSpinner text="Loading SPX Chart..." />}>
          <MarketPeChart 
            indexId="spx" 
            displayName="S&P 500 (SPX)" 
            color="#60A5FA"
            autoRefresh={true}
            refreshInterval={60 * 60 * 1000}
          />
        </Suspense>
        <Suspense fallback={<LoadingSpinner text="Loading HSI Chart..." />}>
          <MarketPeChart 
            indexId="hsi" 
            displayName="Hang Seng Index (HSI)" 
            color="#A78BFA"
            autoRefresh={true}
            refreshInterval={60 * 60 * 1000}
          />
        </Suspense>
      </div>
      <div className="market-breadth-section animate-fade-in-up" style={{ animationDelay: '0.6s' }}>
        <Suspense fallback={<LoadingSpinner text="Loading Market Breadth..." />}>
          <MarketBreathChart indexId="spx" />
        </Suspense>
      </div>
      <div className="animate-fade-in-up" style={{ animationDelay: '0.8s' }}>
        <Suspense fallback={<LoadingSpinner text="Loading OHLCV Chart..." />}>
          <OHLCVChart autoRefresh={true} refreshInterval={60 * 60 * 1000} />
        </Suspense>
      </div>
    </div>
  )
}
