import React, { useState, useEffect } from 'react';
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';

interface PEData {
  index: string;
  data: [number, number][];
  stats: {
    avg_20y: number;
    current_pe: number;
    min_pe: number;
    max_pe: number;
  };
}

interface PEMarketChartProps {
  indexId: string; // e.g., 'spx', 'qqq', etc.
  displayName: string; // e.g., 'S&P 500 (SPX)'
  color?: string; // e.g., '#2E86AB'
}

const PEMarketChart: React.FC<PEMarketChartProps> = ({ indexId, displayName, color = '#2E86AB' }) => {
  const [peData, setPeData] = useState<PEData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nYears, setNYears] = useState<number>(20); // N-year window

  const fetchPEData = async (index: string): Promise<PEData> => {
    const response = await fetch(`/api/market_pe?index=${index}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch ${index} PE data`);
    }
    return response.json();
  };

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchPEData(indexId);
        setPeData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load PE data');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [indexId]);

  // Helper to get N-year window data (assume data is sorted by date ascending)
  const getNYearWindowData = () => {
    if (!peData || !peData.data.length) return [];
    // Each data point: [timestamp, value]
    const msPerYear = 365.25 * 24 * 3600 * 1000;
    const cutoff = peData.data[peData.data.length - 1][0] - nYears * msPerYear;
    return peData.data.filter(([ts]) => ts >= cutoff);
  };

  // Calculate rolling N-year average and stddev for each point in history
  const getRollingStats = () => {
    if (!peData || !peData.data.length) return { avg: [], plus2: [], minus2: [] };
    const msPerYear = 365.25 * 24 * 3600 * 1000;
    const resultAvg: [number, number|null][] = [];
    const resultPlus2: [number, number|null][] = [];
    const resultMinus2: [number, number|null][] = [];
    for (let i = 0; i < peData.data.length; ++i) {
      const [ts, v] = peData.data[i];
      // Find all points within the N-year window ending at ts
      const cutoff = ts - nYears * msPerYear;
      const window = [];
      for (let j = i; j >= 0; --j) {
        if (peData.data[j][0] >= cutoff) window.push(peData.data[j][1]);
        else break;
      }
      if (window.length > 1) {
        const avg = window.reduce((a, b) => a + b, 0) / window.length;
        const std = Math.sqrt(window.reduce((sum, x) => sum + (x - avg) ** 2, 0) / window.length);
        resultAvg.push([ts, avg]);
        resultPlus2.push([ts, avg + 2 * std]);
        resultMinus2.push([ts, avg - 2 * std]);
      } else {
        resultAvg.push([ts, null]);
        resultPlus2.push([ts, null]);
        resultMinus2.push([ts, null]);
      }
    }
    return { avg: resultAvg, plus2: resultPlus2, minus2: resultMinus2 };
  };

  const rollingStats = getRollingStats();

  const chartOptions: Highcharts.Options = {
    chart: {
      type: 'line',
      height: 600,
      backgroundColor: '#f8f9fa',
    },
    title: {
      text: `${displayName} PE Ratio`,
      style: {
        fontSize: '18px',
        fontWeight: 'bold',
      },
    },
    subtitle: {
      text: 'Price-to-Earnings ratio over time',
      style: {
        fontSize: '14px',
      },
    },
    xAxis: {
      type: 'datetime',
      title: {
        text: 'Date',
      },
      labels: {
        format: '{value:%Y-%m-%d}',
      },
    },
    yAxis: {
      title: {
        text: 'PE Ratio',
      },
      labels: {
        format: '{value:.1f}',
      },
    },
    tooltip: {
      shared: true,
      formatter: function() {
        const date = Highcharts.dateFormat('%Y-%m-%d', this.x);
        let tooltip = `<b>${date}</b><br/>`;
        this.points?.forEach(point => {
          tooltip += `<span style="color:${point.color}">●</span> ${point.series.name}: <b>${point.y?.toFixed(2)}</b><br/>`;
        });
        return tooltip;
      },
    },
    legend: {
      enabled: true,
      align: 'center',
      verticalAlign: 'bottom',
      layout: 'horizontal',
    },
    plotOptions: {
      line: {
        marker: {
          enabled: false,
        },
        lineWidth: 2,
      },
      series: {
        animation: {
          duration: 1000,
        },
      },
    },
    series: [
      {
        name: displayName,
        data: peData?.data || [],
        color: color,
        type: 'line',
        zIndex: 3,
      },
      {
        name: `${nYears}Y Avg`,
        data: rollingStats.avg,
        color: '#888',
        dashStyle: 'Dash',
        type: 'line',
        zIndex: 2,
      },
      {
        name: `+2 Std`,
        data: rollingStats.plus2,
        color: '#b8860b',
        dashStyle: 'Dot',
        type: 'line',
        zIndex: 1,
      },
      {
        name: `-2 Std`,
        data: rollingStats.minus2,
        color: '#b8860b',
        dashStyle: 'Dot',
        type: 'line',
        zIndex: 1,
      },
    ].filter(Boolean) as Highcharts.SeriesOptionsType[],
    credits: {
      enabled: false,
    },
  };

  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '400px',
        fontSize: '18px'
      }}>
        Loading PE data...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '400px',
        color: 'red',
        fontSize: '16px'
      }}>
        Error: {error}
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', background: '#fff', borderRadius: '10px', boxShadow: '0 2px 8px rgba(0,0,0,0.05)', maxWidth: 900, margin: '0 auto' }}>
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ marginBottom: '10px', color }}>{displayName}</h2>
        <div style={{ marginBottom: '10px' }}>
          <label>
            N-year window for average/stddev: 
            <input
              type="number"
              min={1}
              max={100}
              value={nYears}
              onChange={e => setNYears(Number(e.target.value))}
              style={{ marginLeft: 8, width: 60 }}
            />
          </label>
        </div>
        {peData && (
          <div style={{ background: '#f8f9fa', padding: '15px', borderRadius: '8px', minWidth: '200px', marginBottom: '10px' }}>
            <div>Current PE: <strong>{peData.stats.current_pe.toFixed(2)}</strong></div>
            <div>20Y Average: <strong>{peData.stats.avg_20y.toFixed(2)}</strong></div>
            <div>Range: <strong>{peData.stats.min_pe.toFixed(2)} - {peData.stats.max_pe.toFixed(2)}</strong></div>
          </div>
        )}
      </div>
      <HighchartsReact
        highcharts={Highcharts}
        options={chartOptions}
      />
    </div>
  );
};

export default PEMarketChart; 