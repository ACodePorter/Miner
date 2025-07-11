import React, { useEffect, useState } from "react";

export interface SectorScore {
  sector_key: string;
  score: number;
}

export interface MarketBreadthData {
  index_name: string;
  trade_date: string; // "2024,07,23,00,00,00,000000"
  score_sma20: number;
  score_sma50: number;
  score_sma200: number;
  sector_score20: SectorScore[];
  sector_score50: SectorScore[];
  sector_score200: SectorScore[];
}

interface MarketBreadthCardProps {
  indexId: string; // e.g., 'spx', 'qqq', etc.
}

function formatTradeDate(trade_date: string): string {
  // "2024,07,23,00,00,00,000000" => "2024-07-23"
  const [year, month, day] = trade_date.split(",");
  return `${year}-${month}-${day}`;
}

const MarketBreadthCard: React.FC<MarketBreadthCardProps> = ({ indexId }) => {
  const [data, setData] = useState<MarketBreadthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/mbs?market_index=${indexId}`)
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        let breadthData;
        if (Array.isArray(data)) {
          breadthData = data.length > 0 ? data[data.length - 1] : null;
        } else {
          breadthData = data;
        }
        if (breadthData) {
          setData(breadthData);
        } else {
          setError('No market breadth data available');
        }
        setLoading(false);
      })
      .catch(err => {
        setError(`Failed to load market breadth: ${err.message}`);
        setLoading(false);
      });
  }, [indexId]);

  if (loading) {
    return <div className="text-center">Loading Market Breadth...</div>;
  }
  if (error) {
    return <div className="text-center text-red-600">Error: {error}</div>;
  }
  if (!data) {
    return null;
  }

  return (
    <div className="rounded-lg shadow-md p-6 bg-white max-w-xl mx-auto border border-gray-200">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xl font-bold">{data.index_name.toUpperCase()} Market Breadth</h2>
        <span className="text-gray-500 text-sm">{formatTradeDate(data.trade_date)}</span>
      </div>
      <div className="flex gap-4 mb-4">
        <div className="flex flex-col items-center">
          <span className="text-xs text-gray-400">SMA 20</span>
          <span className="text-lg font-semibold">{data.score_sma20}%</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-xs text-gray-400">SMA 50</span>
          <span className="text-lg font-semibold">{data.score_sma50}%</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-xs text-gray-400">SMA 200</span>
          <span className="text-lg font-semibold">{data.score_sma200}%</span>
        </div>
      </div>
      <div>
        <h3 className="font-semibold mb-2 text-gray-700">Sector Breadth</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border">
            <thead>
              <tr className="bg-gray-100">
                <th className="px-2 py-1 border">Sector</th>
                <th className="px-2 py-1 border">SMA 20</th>
                <th className="px-2 py-1 border">SMA 50</th>
                <th className="px-2 py-1 border">SMA 200</th>
              </tr>
            </thead>
            <tbody>
              {data.sector_score20.map((s20, i) => {
                const s50 = data.sector_score50[i];
                const s200 = data.sector_score200[i];
                return (
                  <tr key={s20.sector_key}>
                    <td className="px-2 py-1 border font-medium">{s20.sector_key}</td>
                    <td className="px-2 py-1 border">{s20.score}%</td>
                    <td className="px-2 py-1 border">{s50 ? s50.score : "-"}%</td>
                    <td className="px-2 py-1 border">{s200 ? s200.score : "-"}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default MarketBreadthCard;