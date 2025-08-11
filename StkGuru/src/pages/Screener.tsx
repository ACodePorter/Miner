import React, { useCallback, useMemo, useState } from 'react';
import Watchlist from '../components/Watchlist';
import ChartTile from '../components/ChartTile';

const Screener: React.FC = () => {
  const [tiles, setTiles] = useState<{ id: string; ticker: string }[]>([]);

  const addTile = useCallback(() => {
    const t = (window.prompt('Ticker', 'AAPL') || 'AAPL').toUpperCase();
    const id = `${t}-${Date.now()}`;
    setTiles(prev => [...prev, { id, ticker: t }]);
  }, []);

  const removeTile = useCallback((id: string) => {
    setTiles(prev => prev.filter(x => x.id !== id));
  }, []);

  const gridCols = useMemo(() => {
    const n = tiles.length;
    if (n <= 1) return 'grid-cols-1';
    if (n === 2) return 'grid-cols-2';
    if (n <= 4) return 'grid-cols-2';
    return 'grid-cols-3';
  }, [tiles.length]);

  return (
    <div className="flex h-screen">
      <Watchlist className="w-80 flex-shrink-0" fullHeight title="Watchlist" />
      <main className="flex-1 overflow-auto">
        <div className="p-2">
          <div className="mb-2 flex items-center gap-2">
            <button onClick={addTile} className="px-2 py-1 text-xs bg-blue-600 text-white rounded">Add Chart</button>
            <span className="text-xs text-gray-500">Charts: {tiles.length}</span>
          </div>
          <div className={`grid ${gridCols} gap-2`}>
            {tiles.map(t => (
              <ChartTile key={t.id} id={t.id} initialTicker={t.ticker} onRemove={removeTile} />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
};

export default Screener;


