import React from "react";
import './App.css'
import PEMarketChart from './components/PEMarketChart'
import MarketBreadthCard from "./components/MarketBreadthCard";

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>StkGuru - Stock Market Data Visualization</h1>
        <p>Real-time financial market data and analysis</p>
      </header>

      <main>
        <PEMarketChart indexId="spx" displayName="S&P 500 (SPX)" color="#2E86AB" />
        <div style={{ height: '32px' }} />
        <PEMarketChart indexId="qqq" displayName="NASDAQ 100 (QQQ)" color="#A23B72" />
        <div style={{ height: '32px' }} />

        <div className="market-breadth-section">
          <h2 className="text-xl font-bold text-center mb-4">Market Breadth Analysis</h2>
          <MarketBreadthCard indexId="spx" />
        </div>
      </main>
    </div>
  );
}

export default App;
