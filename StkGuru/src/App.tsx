import React from 'react'
import './App.css'
import PEMarketChart from './components/PEMarketChart'

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>StkGuru - Stock Market Data Visualization</h1>
        <p>Real-time financial market data and analysis</p>
      </header>
      
      <main>
        <PEMarketChart />
      </main>
    </div>
  )
}

export default App
