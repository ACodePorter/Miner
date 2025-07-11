import React from "react";
import './App.css'
import PEMarketChart from './components/PEMarketChart'
import MarketBreadthCard from "./components/MarketBreadthCard";

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <div className="w-full text-center">
          <h1 className="animate-fade-in-up">StkGuru</h1>
          <p className="animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
            Advanced Stock Market Analytics & Visualization
          </p>
        </div>
      </header>

      <main>
        <div className="space-y-8">
          {/* PE Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fade-in-up" style={{ animationDelay: '0.4s' }}>
            <PEMarketChart 
              indexId="spx" 
              displayName="S&P 500 (SPX)" 
              color="#60A5FA"
              autoRefresh={true}
              refreshInterval={5 * 60 * 1000} // 5 minutes
            />
            <PEMarketChart 
              indexId="qqq" 
              displayName="NASDAQ 100 (QQQ)" 
              color="#A78BFA"
              autoRefresh={true}
              refreshInterval={5 * 60 * 1000} // 5 minutes
            />
          </div>
          
          {/* Market Breadth Section */}
          <div className="market-breadth-section animate-fade-in-up" style={{ animationDelay: '0.6s' }}>
            <h2 className="market-breadth-title">Market Breadth Analysis</h2>
            <MarketBreadthCard indexId="spx" />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
