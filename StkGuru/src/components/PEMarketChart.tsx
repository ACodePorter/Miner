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

const PEMarketChart: React.FC = () => {
  const [spxData, setSpxData] = useState<PEData | null>(null);
  const [qqqData, setQqqData] = useState<PEData | null>(null);
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
        
        const [spx, qqq] = await Promise.all([
          fetchPEData('spx'),
          fetchPEData('qqq')
        ]);
        
        setSpxData(spx);
        setQqqData(qqq);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load PE data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const chartOptions: Highcharts.Options = {
    chart: {
      type: 'line',
      height: 600,
      backgroundColor: '#f8f9fa'
    },
    title: {
      text: 'Market PE Ratios - SPX vs QQQ',
      style: {
        fontSize: '18px',
        fontWeight: 'bold'
      }
    },
    subtitle: {
      text: 'Price-to-Earnings ratios over time',
      style: {
        fontSize: '14px'
      }
    },
    xAxis: {
      type: 'datetime',
      title: {
        text: 'Date'
      },
      labels: {
        format: '{value:%Y-%m-%d}'
      }
    },
    yAxis: {
      title: {
        text: 'PE Ratio'
      },
      labels: {
        format: '{value:.1f}'
      }
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
      }
    },
    legend: {
      enabled: true,
      align: 'center',
      verticalAlign: 'bottom',
      layout: 'horizontal'
    },
    plotOptions: {
      line: {
        marker: {
          enabled: false
        },
        lineWidth: 2
      },
      series: {
        animation: {
          duration: 1000
        }
      }
    },
    series: [
      {
        name: 'S&P 500 (SPX)',
        data: spxData?.data || [],
        color: '#2E86AB',
        type: 'line'
      },
      {
        name: 'NASDAQ 100 (QQQ)',
        data: qqqData?.data || [],
        color: '#A23B72',
        type: 'line'
      }
    ],
    credits: {
      enabled: false
    }
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
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ marginBottom: '10px' }}>Market PE Ratios</h2>
        <div style={{ display: 'flex', gap: '40px', flexWrap: 'wrap' }}>
          {spxData && (
            <div style={{ 
              background: '#f8f9fa', 
              padding: '15px', 
              borderRadius: '8px',
              minWidth: '200px'
            }}>
              <h3 style={{ margin: '0 0 10px 0', color: '#2E86AB' }}>S&P 500 (SPX)</h3>
              <div>Current PE: <strong>{spxData.stats.current_pe.toFixed(2)}</strong></div>
              <div>20Y Average: <strong>{spxData.stats.avg_20y.toFixed(2)}</strong></div>
              <div>Range: <strong>{spxData.stats.min_pe.toFixed(2)} - {spxData.stats.max_pe.toFixed(2)}</strong></div>
            </div>
          )}
          {qqqData && (
            <div style={{ 
              background: '#f8f9fa', 
              padding: '15px', 
              borderRadius: '8px',
              minWidth: '200px'
            }}>
              <h3 style={{ margin: '0 0 10px 0', color: '#A23B72' }}>NASDAQ 100 (QQQ)</h3>
              <div>Current PE: <strong>{qqqData.stats.current_pe.toFixed(2)}</strong></div>
              <div>20Y Average: <strong>{qqqData.stats.avg_20y.toFixed(2)}</strong></div>
              <div>Range: <strong>{qqqData.stats.min_pe.toFixed(2)} - {qqqData.stats.max_pe.toFixed(2)}</strong></div>
            </div>
          )}
        </div>
      </div>
      
      <HighchartsReact
        highcharts={Highcharts}
        options={chartOptions}
      />
    </div>
  );
};

export default PEMarketChart; 