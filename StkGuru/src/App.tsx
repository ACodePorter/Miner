import './App.css'
import MarketPeChart from './components/MarketPeChart'
import MarketBreathChart from "./components/MarketBreathChart";
import ExtensionWarning from './components/ExtensionWarning';

function App() {
  return (
    <div className="App">
      <ExtensionWarning />
      <header className="App-header">
        <div className="w-full text-center">
          <h1 className="animate-fade-in-up">StkGuru</h1>
        </div>
      </header>

      <main>
        <div className="space-y-8">
          {/* PE Charts Row - Each chart takes exactly 50% of screen width */}
          <div className="grid grid-cols-2 gap-8 animate-fade-in-up pe-charts-grid" style={{ animationDelay: '0.4s' }}>
            <MarketPeChart 
              indexId="spx" 
              displayName="S&P 500 (SPX)" 
              color="#60A5FA"
              autoRefresh={true}
              refreshInterval={5 * 60 * 1000} // 5 minutes
            />
            <MarketPeChart 
              indexId="qqq" 
              displayName="NASDAQ 100 (QQQ)" 
              color="#A78BFA"
              autoRefresh={true}
              refreshInterval={5 * 60 * 1000} // 5 minutes
            />
          </div>
          
          {/* Market Breadth Section */}
          <div className="market-breadth-section animate-fade-in-up" style={{ animationDelay: '0.6s' }}>
            <MarketBreathChart indexId="spx" />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
