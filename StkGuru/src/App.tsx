import './App.css'
import { lazy, Suspense } from 'react'
import ExtensionWarning from './components/ExtensionWarning';
import LoadingSpinner from './components/LoadingSpinner';

// Lazy load heavy chart components for code splitting
const MarketPeChart = lazy(() => import('./components/MarketPeChart'))
const MarketBreathChart = lazy(() => import('./components/MarketBreathChart'))
const OHLCVChart = lazy(() => import('./components/OHLCVChart'))

function App() {
  return (
    <div className="App">
      <ExtensionWarning />
      <main>
        <div className="space-y-8">
          {/* PE Charts Row - Each chart takes exactly 50% of screen width */}
          <div className="grid grid-cols-2 gap-8 animate-fade-in-up pe-charts-grid" style={{ animationDelay: '0.4s' }}>
            <Suspense fallback={<LoadingSpinner text="Loading SPX Chart..." />}>
              <MarketPeChart 
                indexId="spx" 
                displayName="S&P 500 (SPX)" 
                color="#60A5FA"
                autoRefresh={true}
                refreshInterval={5 * 60 * 1000} // 5 minutes
              />
            </Suspense>
            <Suspense fallback={<LoadingSpinner text="Loading HSI Chart..." />}>
              <MarketPeChart 
                indexId="hsi" 
                displayName="Hang Seng Index (HSI)" 
                color="#A78BFA"
                autoRefresh={true}
                refreshInterval={5 * 60 * 1000} // 5 minutes
              />
            </Suspense>
          </div>
          
          {/* Market Breadth Section */}
          <div className="market-breadth-section animate-fade-in-up" style={{ animationDelay: '0.6s' }}>
            <Suspense fallback={<LoadingSpinner text="Loading Market Breadth..." />}>
              <MarketBreathChart indexId="spx" />
            </Suspense>
          </div>
          
          {/* OHLCV Chart Section */}
          <div className="animate-fade-in-up" style={{ animationDelay: '0.8s' }}>
            <Suspense fallback={<LoadingSpinner text="Loading OHLCV Chart..." />}>
              <OHLCVChart 
                autoRefresh={true}
                refreshInterval={5 * 60 * 1000} // 5 minutes
              />
            </Suspense>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
