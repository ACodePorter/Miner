import React from "react";
import './App.css'
import PEMarketChart from './components/PEMarketChart'
import MarketBreadthCard from "./components/MarketBreadthCard";

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <div className="w-full text-center">
          <h1>StkGuru - Stock Market Data Visualization</h1>
          <p>Real-time financial market data and analysis</p>
        </div>
      </header>

      <main>
        <div className="space-y-8">
          {/* PE Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <PEMarketChart 
              indexId="spx" 
              displayName="S&P 500 (SPX)" 
              color="#2E86AB"
              autoRefresh={true}
              refreshInterval={5 * 60 * 1000} // 5 minutes
            />
            <PEMarketChart 
              indexId="qqq" 
              displayName="NASDAQ 100 (QQQ)" 
              color="#A23B72"
              autoRefresh={true}
              refreshInterval={5 * 60 * 1000} // 5 minutes
            />
          </div>
          
          {/* Market Breadth Section */}
          <div className="market-breadth-section">
            <h2 className="market-breadth-title">Market Breadth Analysis</h2>
            <MarketBreadthCard indexId="spx" />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
