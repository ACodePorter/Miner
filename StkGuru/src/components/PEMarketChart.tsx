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
      },
    ],
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