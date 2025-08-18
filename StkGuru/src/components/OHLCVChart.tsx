import React, { useState, useEffect, useCallback, useMemo } from "react";
import Highcharts from "highcharts/highstock";
import HighchartsReact from "highcharts-react-official";
import LoadingSpinner from "./LoadingSpinner";
import ErrorMessage from "./ErrorMessage";
import { dataApi } from '../utils/api';

interface OHLCVData {
  trade_date: string;
  ticker: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  wedge_status: 'pop' | 'drop' | 'none';
}

// New interfaces for the stats.json structure
interface WedgeStats {
  date: string;
  total: number;
  pop: string[];
  drop: string[];
  pop_pct: number;
  drop_pct: number;
}

interface CategorizedTickers {
  date: string;
  pop: string[];
  drop: string[];
  pop_pct: number;
  drop_pct: number;
}

// EMA calculation function
const calculateEMA = (data: number[], period: number): number[] => {
  const ema: number[] = [];
  const multiplier = 2 / (period + 1);
  
  // First EMA is SMA
  let sum = 0;
  for (let i = 0; i < period && i < data.length; i++) {
    sum += data[i];
  }
  ema[period - 1] = sum / period;
  
  // Calculate EMA for remaining data
  for (let i = period; i < data.length; i++) {
    ema[i] = (data[i] * multiplier) + (ema[i - 1] * (1 - multiplier));
  }
  
  return ema;
};

// MACD calculation function
const calculateMACD = (data: number[], fastPeriod: number = 10, slowPeriod: number = 20, signalPeriod: number = 5) => {
  const emaFast = calculateEMA(data, fastPeriod);
  const emaSlow = calculateEMA(data, slowPeriod);
  
  const macdLine: number[] = [];
  const signalLine: number[] = [];
  const histogram: number[] = [];
  
  // Calculate MACD line
  for (let i = Math.max(fastPeriod, slowPeriod) - 1; i < data.length; i++) {
    macdLine[i] = emaFast[i] - emaSlow[i];
  }
  
  // Calculate signal line (EMA of MACD line)
  const signalEMA = calculateEMA(macdLine.filter(val => val !== undefined), signalPeriod);
  let signalIndex = 0;
  for (let i = Math.max(fastPeriod, slowPeriod) - 1; i < data.length; i++) {
    if (macdLine[i] !== undefined) {
      signalLine[i] = signalEMA[signalIndex];
      histogram[i] = macdLine[i] - signalLine[i];
      signalIndex++;
    }
  }
  
  return { macdLine, signalLine, histogram };
};

interface OHLCVChartProps {
  autoRefresh?: boolean;
  refreshInterval?: number;
  className?: string;
}

const OHLCVChart: React.FC<OHLCVChartProps> = ({
  autoRefresh = false,
  refreshInterval = 60 * 60 * 1000, // 1 hour
  className = "",
}) => {
  const [selectedTicker, setSelectedTicker] = useState<string>("");
  const [categorizedTickers, setCategorizedTickers] = useState<CategorizedTickers[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [selectedWedgeStatus, setSelectedWedgeStatus] = useState<'pop' | 'drop'>('pop');
  const [ohlcvData, setOhlcvData] = useState<OHLCVData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoomWindow, setZoomWindow] = useState<{ min: number; max: number } | null>(null);

  // Fetch categorized tickers from stats.json
  const fetchCategorizedTickers = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('Fetching categorized tickers from new API');
      const data = await dataApi.getWedgePopStats();
      console.log('Categorized tickers data:', data);
      
      if (!data || !Array.isArray(data)) {
        throw new Error('Invalid data format received');
      }
      
      // Sort by date (newest first)
      const sortedData = data.sort((a: any, b: any) => {
        const dateA = new Date(a.date.substring(0, 4) + '-' + a.date.substring(4, 6) + '-' + a.date.substring(6, 8));
        const dateB = new Date(b.date.substring(0, 4) + '-' + b.date.substring(4, 6) + '-' + b.date.substring(6, 8));
        return dateB.getTime() - dateA.getTime();
      });
      
      const categorized: CategorizedTickers[] = sortedData.map((item: any) => ({
        date: item.date,
        pop: item.pop,
        drop: item.drop,
        pop_pct: item.pop_pct,
        drop_pct: item.drop_pct
      }));
      
      setCategorizedTickers(categorized);
      console.log('Processed categorized tickers:', categorized);
      
      // Set default selections
      if (categorized.length > 0) {
        const lastDate = categorized[0].date;
        setSelectedDate(lastDate);
        
        // Set default ticker to first pop ticker of the last date
        if (categorized[0].pop.length > 0) {
          setSelectedTicker(categorized[0].pop[0]);
          setSelectedWedgeStatus('pop');
        } else if (categorized[0].drop.length > 0) {
          setSelectedTicker(categorized[0].drop[0]);
          setSelectedWedgeStatus('drop');
        }
      }
    } catch (err) {
      console.error('Failed to fetch categorized tickers:', err);
      setError('Failed to fetch categorized ticker list');
    } finally {
      setLoading(false);
    }
  }, []);

  // Get available tickers for selected date and wedge status
  const getAvailableTickers = useCallback(() => {
    if (!selectedDate || !categorizedTickers.length) return [];
    
    const dateData = categorizedTickers.find(item => item.date === selectedDate);
    if (!dateData) return [];
    
    return selectedWedgeStatus === 'pop' ? dateData.pop : dateData.drop;
  }, [selectedDate, selectedWedgeStatus, categorizedTickers]);

  // Fetch OHLCV data for selected ticker
  const fetchOHLCVData = useCallback(async (ticker: string) => {
    if (!ticker) return;
    
    try {
      setLoading(true);
      setError(null);
      
      console.log('Fetching OHLCV data for ticker:', ticker);
      const data = await dataApi.getOHLCVW(ticker);
      console.log('OHLCV data:', data);
      
      if (!data || !Array.isArray(data)) {
        throw new Error('Invalid OHLCV data format received');
      }
      
      // Data is already an array from the API
      setOhlcvData(data);
      console.log('Processed OHLCV data:', data);
    } catch (err) {
      console.error('Failed to fetch OHLCV data:', err);
      setError('Failed to fetch OHLCV data');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial data fetch
  useEffect(() => {
    fetchCategorizedTickers();
  }, [fetchCategorizedTickers]);

  // Fetch OHLCV data when ticker changes
  useEffect(() => {
    if (selectedTicker) {
      fetchOHLCVData(selectedTicker);
    }
  }, [selectedTicker, fetchOHLCVData]);

  // Auto-refresh functionality
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      if (selectedTicker) {
        fetchOHLCVData(selectedTicker);
      }
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, selectedTicker, fetchOHLCVData]);

  // Update selected ticker when date or wedge status changes
  useEffect(() => {
    const availableTickers = getAvailableTickers();
    if (availableTickers.length > 0) {
      setSelectedTicker(availableTickers[0]);
    } else {
      setSelectedTicker("");
    }
  }, [selectedDate, selectedWedgeStatus, getAvailableTickers]);

  // Process chart data
  const chartData = useMemo(() => {
    console.log('Processing chart data, ohlcvData length:', ohlcvData.length);
    if (!ohlcvData.length) {
      console.log('No OHLCV data available');
      return null;
    }

    console.log('Sample OHLCV data:', ohlcvData[0]);

    // Sort data by date
    const sortedData = [...ohlcvData].sort((a, b) => {
      const dateA = new Date(a.trade_date.replace(/,/g, '-'));
      const dateB = new Date(b.trade_date.replace(/,/g, '-'));
      return dateA.getTime() - dateB.getTime();
    });

    console.log('Sorted data length:', sortedData.length);

    // Convert to Highcharts candlestick format [timestamp, open, high, low, close]
    const candlestickData = sortedData.map(item => {
      // Handle different date formats from the backend
      let timestamp: number;
      if (typeof item.trade_date === 'string') {
        // Try to parse the custom format used by the scraper "2024,01,15,00,00,00,000000"
        if (item.trade_date.includes(',')) {
          const [year, month, day] = item.trade_date.split(',');
          timestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
        } else {
          timestamp = new Date(item.trade_date).getTime();
        }
      } else {
        timestamp = new Date(item.trade_date).getTime();
      }
      return [timestamp, item.open, item.high, item.low, item.close];
    });

    console.log('Candlestick data length:', candlestickData.length);

    // Calculate EMA10 and EMA20
    const closePrices = sortedData.map(item => item.close);
    const ema10 = calculateEMA(closePrices, 10);
    const ema20 = calculateEMA(closePrices, 20);

    // Calculate MACD (10, 20, 5)
    const macdData = calculateMACD(closePrices, 10, 20, 5);

    // Create EMA data for Highcharts
    const ema10Data = sortedData.map((item, index) => {
      let timestamp: number;
      if (typeof item.trade_date === 'string') {
        if (item.trade_date.includes(',')) {
          const [year, month, day] = item.trade_date.split(',');
          timestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
        } else {
          timestamp = new Date(item.trade_date).getTime();
        }
      } else {
        timestamp = new Date(item.trade_date).getTime();
      }
      return [timestamp, ema10[index] || null];
    }).filter(item => item[1] !== null);

    const ema20Data = sortedData.map((item, index) => {
      let timestamp: number;
      if (typeof item.trade_date === 'string') {
        if (item.trade_date.includes(',')) {
          const [year, month, day] = item.trade_date.split(',');
          timestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
        } else {
          timestamp = new Date(item.trade_date).getTime();
        }
      } else {
        timestamp = new Date(item.trade_date).getTime();
      }
      return [timestamp, ema20[index] || null];
    }).filter(item => item[1] !== null);

    // Create MACD data for Highcharts
    const macdLineData = sortedData.map((item, index) => {
      let timestamp: number;
      if (typeof item.trade_date === 'string') {
        if (item.trade_date.includes(',')) {
          const [year, month, day] = item.trade_date.split(',');
          timestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
        } else {
          timestamp = new Date(item.trade_date).getTime();
        }
      } else {
        timestamp = new Date(item.trade_date).getTime();
      }
      return [timestamp, macdData.macdLine[index] || null];
    }).filter(item => item[1] !== null);

    const signalLineData = sortedData.map((item, index) => {
      let timestamp: number;
      if (typeof item.trade_date === 'string') {
        if (item.trade_date.includes(',')) {
          const [year, month, day] = item.trade_date.split(',');
          timestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
        } else {
          timestamp = new Date(item.trade_date).getTime();
        }
      } else {
        timestamp = new Date(item.trade_date).getTime();
      }
      return [timestamp, macdData.signalLine[index] || null];
    }).filter(item => item[1] !== null);

    const histogramData = sortedData.map((item, index) => {
      let timestamp: number;
      if (typeof item.trade_date === 'string') {
        if (item.trade_date.includes(',')) {
          const [year, month, day] = item.trade_date.split(',');
          timestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
        } else {
          timestamp = new Date(item.trade_date).getTime();
        }
      } else {
        timestamp = new Date(item.trade_date).getTime();
      }
      return [timestamp, macdData.histogram[index] || null];
    }).filter(item => item[1] !== null);

    // Create wedge status markers with blur light effect
    const wedgeMarkers = sortedData.map((item) => {
      // Handle different date formats from the backend
      let timestamp: number;
      if (typeof item.trade_date === 'string') {
        // Try to parse the custom format used by the scraper "2024,01,15,00,00,00,000000"
        if (item.trade_date.includes(',')) {
          const [year, month, day] = item.trade_date.split(',');
          timestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
        } else {
          timestamp = new Date(item.trade_date).getTime();
        }
      } else {
        timestamp = new Date(item.trade_date).getTime();
      }
      
      if (item.wedge_status === 'pop') {
        return {
          x: timestamp,
          y: item.high,
          marker: {
            symbol: 'circle',
            fillColor: '#A6E22E',
            lineColor: 'transparent',
            lineWidth: 0,
            radius: 6,
            states: {
              hover: {
                enabled: true,
                radius: 10,
                fillColor: '#A6E22E',
                lineColor: 'transparent',
                brightness: 0.5
              }
            }
          },
          dataLabels: {
            enabled: true,
            format: 'POP',
            style: {
              color: '#A6E22E',
              fontSize: '9px',
              fontWeight: 'bold',
              textOutline: 'none',
              textShadow: '0 0 3px #A6E22E'
            },
            y: -20
          }
        };
      } else if (item.wedge_status === 'drop') {
        return {
          x: timestamp,
          y: item.low,
          marker: {
            symbol: 'circle',
            fillColor: '#F92672',
            lineColor: 'transparent',
            lineWidth: 0,
            radius: 6,
            states: {
              hover: {
                enabled: true,
                radius: 10,
                fillColor: '#F92672',
                lineColor: 'transparent',
                brightness: 0.5
              }
            }
          },
          dataLabels: {
            enabled: true,
            format: 'DROP',
            style: {
              color: '#F92672',
              fontSize: '9px',
              fontWeight: 'bold',
              textOutline: 'none',
              textShadow: '0 0 3px #F92672'
            },
            y: 20
          }
        };
      }
      return null;
    }).filter(Boolean);

    console.log('Wedge markers count:', wedgeMarkers.length);

    return { 
      candlestickData, 
      wedgeMarkers, 
      sortedData,
      ema10Data,
      ema20Data,
      macdLineData,
      signalLineData,
      histogramData,
      ema10,
      ema20,
      macdData
    };
  }, [ohlcvData]);

  // Generate chart options
  const chartOptions = useMemo(() => {
    if (!chartData) return null;

    const { 
      candlestickData, 
      wedgeMarkers, 
      sortedData,
      ema10Data,
      ema20Data,
      macdLineData,
      signalLineData,
      histogramData
    } = chartData;

    return {
      chart: {
        type: 'candlestick',
        height: 650,
        backgroundColor: 'rgba(0, 0, 0, 0.3)', // Match other charts
        zoomType: 'x',
        panning: {
          enabled: true,
          type: 'x',
        },
        style: {
          fontFamily: 'inherit',
        },
        plotBackgroundColor: 'rgba(0, 0, 0, 0.2)', // Match other charts
        plotBorderWidth: 0,
        plotShadow: false,
        spacing: [5, 5, 5, 5],
        reflow: true,
        events: {
          load: function() {
            // Chart loaded successfully
          },
          mouseOver: function(this: any, e: any) {
            // Subtle blur light highlighting
            if (e.target && e.target.series && e.target.series.type === 'candlestick') {
              const chart = this;
              const wedgeSeries = chart.series.find((s: any) => s.name === 'Wedge Status');
              if (wedgeSeries) {
                // Find wedge markers near the hovered candlestick
                const hoveredX = e.target.x;
                wedgeSeries.points.forEach((point: any) => {
                  if (Math.abs(point.x - hoveredX) < 24 * 60 * 60 * 1000) { // Within 1 day
                    const isPop = point.dataLabels?.text === 'POP';
                    const color = isPop ? '#A6E22E' : '#F92672';
                    point.update({
                      marker: {
                        radius: 12,
                        lineWidth: 0,
                        fillColor: color,
                        lineColor: 'transparent',
                        symbol: 'circle'
                      }
                    }, false);
                  }
                });
                chart.redraw();
              }
            }
          },
          mouseOut: function(this: any, e: any) {
            // Reset wedge status dots to blur light effect
            if (e.target && e.target.series && e.target.series.type === 'candlestick') {
              const chart = this;
              const wedgeSeries = chart.series.find((s: any) => s.name === 'Wedge Status');
              if (wedgeSeries) {
                wedgeSeries.points.forEach((point: any) => {
                  const isPop = point.dataLabels?.text === 'POP';
                  const color = isPop ? '#A6E22E' : '#F92672';
                  point.update({
                    marker: {
                      radius: 6,
                      lineWidth: 0,
                      fillColor: color,
                      lineColor: 'transparent',
                      symbol: 'circle'
                    }
                  }, false);
                });
                chart.redraw();
              }
            }
          },
          setExtremes: function(this: any, e: any) {
            setZoomWindow({ min: e.min, max: e.max });
          }
        }
      },
      title: {
        text: '',
      },
      subtitle: {
        text: '',
      },
      xAxis: {
        type: 'datetime',
        labels: {
          format: '{value:%Y-%m-%d}',
          style: { fontSize: '14px', color: '#D1D5DB', fontWeight: '500' },
        },
        gridLineWidth: 2,
        gridLineColor: 'rgba(107, 114, 128, 0.4)',
        lineColor: 'rgba(156, 163, 175, 0.6)',
        tickColor: 'rgba(156, 163, 175, 0.6)',
        tickWidth: 2,
        tickLength: 6,
        crosshair: {
          color: 'rgba(96, 165, 250, 0.7)',
          width: 2,
          dashStyle: 'shortdot'
        },
        events: {
          setExtremes: function(this: any, e: any) {
            setZoomWindow({ min: e.min, max: e.max });
          }
        }
      },
      yAxis: [
        {
          type: 'logarithmic',
          title: {
            text: 'Price ($)',
            style: { fontSize: '16px', fontWeight: '700', color: '#E5E7EB' },
          },
          labels: {
            format: '{value:.2f}',
            style: { fontSize: '14px', color: '#D1D5DB', fontWeight: '500' },
          },
          gridLineWidth: 2,
          gridLineColor: 'rgba(107, 114, 128, 0.4)',
          lineColor: 'rgba(156, 163, 175, 0.6)',
          tickColor: 'rgba(156, 163, 175, 0.6)',
          tickWidth: 2,
          tickLength: 6,
          crosshair: {
            color: 'rgba(96, 165, 250, 0.7)',
            width: 2,
            dashStyle: 'shortdot'
          },
          minorGridLineWidth: 1,
          minorGridLineColor: 'rgba(107, 114, 128, 0.2)',
          minorTickLength: 3,
          minorTickColor: 'rgba(156, 163, 175, 0.4)',
          minorTickWidth: 1
        },
        {
          title: {
            text: '',
            style: { fontSize: '16px', fontWeight: '700', color: '#E5E7EB' },
          },
          labels: {
            enabled: false,
          },
          gridLineWidth: 2,
          gridLineColor: 'rgba(107, 114, 128, 0.4)',
          lineColor: 'rgba(156, 163, 175, 0.6)',
          tickColor: 'rgba(156, 163, 175, 0.6)',
          tickWidth: 2,
          tickLength: 6,
          opposite: true,
          crosshair: {
            color: 'rgba(96, 165, 250, 0.7)',
            width: 2,
            dashStyle: 'shortdot'
          }
        },
        {
          title: {
            text: 'MACD',
            style: { fontSize: '16px', fontWeight: '700', color: '#E5E7EB' },
          },
          labels: {
            format: '{value:.2f}',
            style: { fontSize: '14px', color: '#D1D5DB', fontWeight: '500' },
          },
          gridLineWidth: 2,
          gridLineColor: 'rgba(107, 114, 128, 0.4)',
          lineColor: 'rgba(156, 163, 175, 0.6)',
          tickColor: 'rgba(156, 163, 175, 0.6)',
          tickWidth: 2,
          tickLength: 6,
          top: '75%',
          height: '25%',
          offset: 0,
          crosshair: {
            color: 'rgba(96, 165, 250, 0.7)',
            width: 2,
            dashStyle: 'shortdot'
          },
          plotLines: [{
            value: 0,
            color: '#F8F8F2', // Monokai foreground - more visible
            width: 3, // Thicker line
            dashStyle: 'solid',
            zIndex: 1,
            label: {
              text: '0',
              style: {
                color: '#F8F8F2', // Monokai foreground
                fontSize: '14px', // Larger font
                fontWeight: 'bold',
                textShadow: '0 0 3px rgba(0,0,0,0.8)' // Text shadow for better contrast
              }
            }
          }]
        },
      ],
      series: [
        {
          name: selectedTicker,
          data: candlestickData,
          type: 'candlestick',
          color: '#F92672', // Monokai red
          upColor: '#A6E22E', // Monokai green
          downColor: '#F92672', // Monokai red
          lineColor: '#F92672', // Monokai red
          upLineColor: '#A6E22E', // Monokai green
          downLineColor: '#F92672', // Monokai red
          zIndex: 2,
          lineWidth: 2,
          marker: {
            enabled: false,
            states: {
              hover: { enabled: true, radius: 6, lineWidth: 2, lineColor: '#F92672' }
            }
          },
          tooltip: {
            enabled: true,
            pointFormat: '', // Disable default tooltip format
          },
        },
        {
          name: "Volume",
          data: sortedData.map(item => {
            // Handle different date formats from the backend
            let timestamp: number;
            if (typeof item.trade_date === 'string') {
              // Try to parse the custom format used by the scraper "2024,01,15,00,00,00,000000"
              if (item.trade_date.includes(',')) {
                const [year, month, day] = item.trade_date.split(',');
                timestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
              } else {
                timestamp = new Date(item.trade_date).getTime();
              }
            } else {
              timestamp = new Date(item.trade_date).getTime();
            }
            return [timestamp, item.volume];
          }),
          type: "column",
          yAxis: 1,
          visible: true, // Show volume by default
          color: '#66D9EF', // Monokai blue for better readability
          opacity: 0.6,
          zIndex: 1,
        },
        {
          name: "Wedge Status",
          data: wedgeMarkers,
          type: "scatter",
          zIndex: 10, // Higher z-index to ensure visibility
          marker: {
            enabled: true,
            radius: 6, // Soft blur light size
            symbol: 'circle',
            fillColor: '#A6E22E', // Monokai green
            lineColor: 'transparent', // No border for blur effect
            lineWidth: 0,
            states: {
              hover: {
                enabled: true,
                radius: 10, // Larger glow on hover
                fillColor: '#A6E22E',
                lineColor: 'transparent',
                brightness: 0.5
              }
            }
          },
          tooltip: {
            pointFormat: '{point.series.name}: {point.y:.2f}',
            backgroundColor: 'rgba(17, 24, 39, 0.98)',
            borderWidth: 0,
            shadow: true,
            borderRadius: 8,
            style: { fontSize: '13px', color: '#ffffff' },
            formatter: function(this: any) {
              const date = Highcharts.dateFormat('%Y-%m-%d', this.x);
              const status = this.point.dataLabels?.text || 'Wedge';
              const color = status === 'POP' ? '#A6E22E' : '#F92672';
              return `<div style="padding: 4px 0;"><b style="color: ${color}; font-size: 14px;">${status} - ${date}</b></div>`;
            }
          },
          dataLabels: {
            enabled: true,
            style: {
              color: '#A6E22E',
              fontSize: '9px',
              fontWeight: 'bold',
              textOutline: 'none',
              textShadow: '0 0 3px #A6E22E'
            }
          }
        },
        {
          name: "EMA10",
          data: ema10Data,
          type: "line",
          color: '#FD971F', // Monokai orange
          lineWidth: 2,
          zIndex: 1,
          marker: {
            enabled: false,
          },
          tooltip: {
            pointFormat: '{point.series.name}: {point.y:.2f}',
          },
        },
        {
          name: "EMA20",
          data: ema20Data,
          type: "line",
          color: '#66D9EF', // Monokai blue
          lineWidth: 2,
          zIndex: 1,
          marker: {
            enabled: false,
          },
          tooltip: {
            pointFormat: '{point.series.name}: {point.y:.2f}',
          },
        },
        {
          name: "MACD",
          data: macdLineData,
          type: "line",
          color: '#A6E22E', // Monokai green
          lineWidth: 2,
          yAxis: 2,
          zIndex: 1,
          visible: false, // Hidden by default
          marker: {
            enabled: false,
          },
          tooltip: {
            pointFormat: '{point.series.name}: {point.y:.2f}',
          },
        },
        {
          name: "MACD",
          data: signalLineData,
          type: "line",
          color: '#F92672', // Monokai red
          lineWidth: 2,
          yAxis: 2,
          zIndex: 1,
          visible: false, // Hidden by default
          linkedTo: ':previous', // Link to previous MACD series
          marker: {
            enabled: false,
          },
          tooltip: {
            pointFormat: '{point.series.name}: {point.y:.2f}',
          },
        },
        {
          name: "MACD",
          data: histogramData,
          type: "column",
          color: '#75715E', // Monokai gray
          opacity: 0.6,
          yAxis: 2,
          zIndex: 0,
          visible: false, // Hidden by default
          linkedTo: ':previous', // Link to previous MACD series
          tooltip: {
            pointFormat: '{point.series.name}: {point.y:.2f}',
          },
        },
      ],
      tooltip: {
        shared: false,
        backgroundColor: 'rgba(17, 24, 39, 0.98)', // Match other charts
        borderWidth: 0,
        shadow: true,
        borderRadius: 8,
        style: { fontSize: '13px', color: '#ffffff' }, // Match other charts
        formatter: function(this: any) {
          const date = Highcharts.dateFormat('%Y-%m-%d', this.x);
          let tooltip = `<div style="padding: 4px 0;"><b style="color: #F92672; font-size: 14px;">${date}</b></div><br/>`;
          
          // Find the corresponding OHLCV data for this timestamp
          const timestamp = this.x;
          let ohlcvData = null;
          
          // Try to find data by exact timestamp match
          ohlcvData = sortedData.find(item => {
            let itemTimestamp: number;
            if (typeof item.trade_date === 'string') {
              if (item.trade_date.includes(',')) {
                const [year, month, day] = item.trade_date.split(',');
                itemTimestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
              } else {
                itemTimestamp = new Date(item.trade_date).getTime();
              }
            } else {
              itemTimestamp = new Date(item.trade_date).getTime();
            }
            return itemTimestamp === timestamp;
          });
          
          // If not found, try to find by date string match
          if (!ohlcvData) {
            const dateStr = Highcharts.dateFormat('%Y-%m-%d', timestamp);
            ohlcvData = sortedData.find(item => {
              let itemDateStr: string;
              if (typeof item.trade_date === 'string') {
                if (item.trade_date.includes(',')) {
                  const [year, month, day] = item.trade_date.split(',');
                  const itemDate = new Date(Number(year), Number(month) - 1, Number(day));
                  itemDateStr = Highcharts.dateFormat('%Y-%m-%d', itemDate.getTime());
                } else {
                  const itemDate = new Date(item.trade_date);
                  itemDateStr = Highcharts.dateFormat('%Y-%m-%d', itemDate.getTime());
                }
              } else {
                const itemDate = new Date(item.trade_date);
                itemDateStr = Highcharts.dateFormat('%Y-%m-%d', itemDate.getTime());
              }
              return itemDateStr === dateStr;
            });
          }
          
                      // Show OHLCV data if available
            if (ohlcvData) {
              tooltip += `<span style="color: #A6E22E; font-size: 16px;">●</span> <span style="color: #A6E22E; font-weight: 500;">Open:</span> <span style="color: #F8F8F2; font-weight: bold;">$${ohlcvData.open?.toFixed(2)}</span><br/>`;
              tooltip += `<span style="color: #FD971F; font-size: 16px;">●</span> <span style="color: #FD971F; font-weight: 500;">High:</span> <span style="color: #F8F8F2; font-weight: bold;">$${ohlcvData.high?.toFixed(2)}</span><br/>`;
              tooltip += `<span style="color: #F92672; font-size: 16px;">●</span> <span style="color: #F92672; font-weight: 500;">Low:</span> <span style="color: #F8F8F2; font-weight: bold;">$${ohlcvData.low?.toFixed(2)}</span><br/>`;
              tooltip += `<span style="color: #66D9EF; font-size: 16px;">●</span> <span style="color: #66D9EF; font-weight: 500;">Close:</span> <span style="color: #F8F8F2; font-weight: bold;">$${ohlcvData.close?.toFixed(2)}</span><br/>`;
              tooltip += `<span style="color: #75715E; font-size: 16px;">●</span> <span style="color: #75715E; font-weight: 500;">Volume:</span> <span style="color: #F8F8F2; font-weight: bold;">${ohlcvData.volume?.toLocaleString()}</span><br/>`;
            
            // Show wedge status if available
            if (ohlcvData.wedge_status && ohlcvData.wedge_status !== 'none') {
              const statusColor = ohlcvData.wedge_status === 'pop' ? '#A6E22E' : '#F92672';
              const statusText = ohlcvData.wedge_status === 'pop' ? 'POP' : 'DROP';
              tooltip += `<span style="color: ${statusColor}; font-size: 16px;">●</span> <span style="color: ${statusColor}; font-weight: 500;">Wedge Status:</span> <span style="color: ${statusColor}; font-weight: bold;">${statusText}</span><br/>`;
            }

            // Show EMA values if available
            const dataIndex = sortedData.findIndex(item => {
              let itemTimestamp: number;
              if (typeof item.trade_date === 'string') {
                if (item.trade_date.includes(',')) {
                  const [year, month, day] = item.trade_date.split(',');
                  itemTimestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
                } else {
                  itemTimestamp = new Date(item.trade_date).getTime();
                }
              } else {
                itemTimestamp = new Date(item.trade_date).getTime();
              }
              return itemTimestamp === timestamp;
            });

            if (dataIndex >= 0 && dataIndex < chartData.ema10.length && chartData.ema10[dataIndex]) {
              tooltip += `<span style="color: #FD971F; font-size: 16px;">●</span> <span style="color: #FD971F; font-weight: 500;">EMA10:</span> <span style="color: #F8F8F2; font-weight: bold;">$${chartData.ema10[dataIndex].toFixed(2)}</span><br/>`;
            }
            if (dataIndex >= 0 && dataIndex < chartData.ema20.length && chartData.ema20[dataIndex]) {
              tooltip += `<span style="color: #66D9EF; font-size: 16px;">●</span> <span style="color: #66D9EF; font-weight: 500;">EMA20:</span> <span style="color: #F8F8F2; font-weight: bold;">$${chartData.ema20[dataIndex].toFixed(2)}</span><br/>`;
            }
          } else {
            // Fallback: show candlestick data from the point itself
            if (this.points && this.points.length > 0) {
              const point = this.points[0];
              if (point.series.type === 'candlestick' && point.open !== undefined) {
                tooltip += `<span style="color: #A6E22E; font-size: 16px;">●</span> <span style="color: #A6E22E; font-weight: 500;">Open:</span> <span style="color: #F8F8F2; font-weight: bold;">$${point.open?.toFixed(2)}</span><br/>`;
                tooltip += `<span style="color: #FD971F; font-size: 16px;">●</span> <span style="color: #FD971F; font-weight: 500;">High:</span> <span style="color: #F8F8F2; font-weight: bold;">$${point.high?.toFixed(2)}</span><br/>`;
                tooltip += `<span style="color: #F92672; font-size: 16px;">●</span> <span style="color: #F92672; font-weight: 500;">Low:</span> <span style="color: #F8F8F2; font-weight: bold;">$${point.low?.toFixed(2)}</span><br/>`;
                tooltip += `<span style="color: #66D9EF; font-size: 16px;">●</span> <span style="color: #66D9EF; font-weight: 500;">Close:</span> <span style="color: #F8F8F2; font-weight: bold;">$${point.close?.toFixed(2)}</span><br/>`;
              }
            }
          }
          
          // Show series data for non-candlestick series
          this.points?.forEach((point: any) => {
            const seriesName = point.series.name;
            let value = point.y?.toFixed(2);
            const isMainSeries = seriesName === selectedTicker;
            const isWedgeSeries = seriesName === 'Wedge Status';
            const isVolumeSeries = seriesName === 'Volume';
            const isEMA10Series = seriesName === 'EMA10';
            const isEMA20Series = seriesName === 'EMA20';
            const isMACDSeries = seriesName === 'MACD';
            
            // Skip candlestick series, volume series, EMA series, and MACD series as we handle them above
            if (isMainSeries || isVolumeSeries || isEMA10Series || isEMA20Series || isMACDSeries) {
              return;
            }
            
            let nameColor = '#75715E';
            let valueColor = '#F8F8F2';
            let icon = '●';
            
            if (isWedgeSeries) {
              nameColor = '#A6E22E';
              valueColor = '#A6E22E';
            }
            
            tooltip += `<span style="color:${point.color}; font-size: 16px;">${icon}</span> <span style="color: ${nameColor}; font-weight: 500;">${seriesName}</span>: <span style="color: ${valueColor}; font-weight: bold;">${value}</span><br/>`;
          });
          return tooltip;
        },
      },
      legend: {
        enabled: true,
        align: 'center',
        verticalAlign: 'bottom',
        layout: 'horizontal',
        itemStyle: { 
          fontSize: '14px',
          color: '#F8F8F2', // Monokai foreground
          fontWeight: '600'
        },
        itemHoverStyle: {
          color: '#F92672' // Monokai red
        },
        symbolHeight: 12,
        symbolWidth: 24,
        symbolRadius: 3,
        backgroundColor: '#272822', // Monokai background
        borderWidth: 1,
        borderColor: '#75715E', // Monokai gray
        borderRadius: 8,
        shadow: true,
        itemDistance: 20,
        padding: 12,
        width: '100%',
        height: 50,
        itemWidth: 150,
        useHTML: false,
        floating: false,
        x: 0,
        y: 0,
      },
      plotOptions: {
        candlestick: {
          color: '#F92672', // Monokai red
          upColor: '#A6E22E', // Monokai green
          lineColor: '#F92672', // Monokai red
          upLineColor: '#A6E22E', // Monokai green
          tooltip: {
            enabled: true,
          },
        },
        column: {
          color: '#66D9EF', // Monokai blue for better readability
          opacity: 0.6,
        },
        series: {
          animation: {
            duration: 1000,
          },
          tooltip: {
            enabled: true,
          },
        },
      },
      navigator: {
        enabled: true,
        height: 40,
        margin: 10,
        outlineWidth: 0,
        outlineColor: 'transparent',
        handles: {
          backgroundColor: 'rgba(96, 165, 250, 0.8)',
          borderColor: 'rgba(96, 165, 250, 1)',
          lineColor: 'rgba(96, 165, 250, 0.5)',
          rifleColor: 'rgba(96, 165, 250, 0.8)',
        },
        xAxis: {
          gridLineColor: 'rgba(0, 0, 0, 0.4)',
          lineColor: 'rgba(75, 85, 99, 0.6)',
          tickColor: 'rgba(75, 85, 99, 0.4)',
          labels: {
            style: {
              color: '#9ca3af',
              fontSize: '10px',
            },
          },
        },
      },
      scrollbar: {
        enabled: true,
        barBackgroundColor: 'rgba(75, 85, 99, 0.5)',
        barBorderColor: 'rgba(75, 85, 99, 0.8)',
        buttonBackgroundColor: 'rgba(55, 65, 81, 0.8)',
        buttonBorderColor: 'rgba(75, 85, 99, 0.8)',
        buttonArrowColor: '#9ca3af',
        rifleColor: 'rgba(96, 165, 250, 0.8)',
        trackBackgroundColor: 'rgba(31, 41, 55, 0.3)',
        trackBorderColor: 'rgba(75, 85, 99, 0.3)',
      },
      rangeSelector: {
        enabled: true,
        selected: 0, // 6m button (first button)
        inputEnabled: false,
        buttonTheme: {
          fill: 'rgba(0, 0, 0, 0.9)',
          stroke: 'rgba(75, 85, 99, 0.6)',
          r: 8,
          states: {
            hover: {
              fill: 'rgba(31, 41, 55, 0.9)',
              style: {
                color: '#ffffff',
              },
            },
            select: {
              fill: 'rgba(96, 165, 250, 0.8)',
              style: {
                color: '#ffffff',
                fontWeight: 'bold',
              },
            },
          },
          style: {
            color: '#9ca3af',
            fontSize: '12px',
            fontWeight: '500',
          },
        },
        buttons: [
          { type: 'month', count: 6, text: '6m' },
          { type: 'year', count: 1, text: '1y' },
          { type: 'year', count: 3, text: '3y' },
          { type: 'year', count: 5, text: '5y' },
          { type: 'all', text: 'All' },
        ],
      },
      responsive: {
        rules: [{
          condition: {
            maxWidth: 768
          },
          chartOptions: {
            legend: {
              enabled: false
            },
            chart: {
              height: 400
            }
          }
        }]
      },
      credits: {
        enabled: false,
      },
      exporting: {
        enabled: true,
        buttons: {
          contextButton: {
            symbol: 'menu',
            symbolX: 12,
            symbolY: 10,
            symbolSize: 14,
            symbolStrokeWidth: 2,
            symbolStroke: '#9ca3af',
            symbolFill: 'rgba(31, 41, 55, 0.8)',
            menuItems: ['downloadPNG', 'downloadPDF', 'downloadCSV'],
            theme: {
              fill: 'rgba(31, 41, 55, 0.95)',
              stroke: 'rgba(75, 85, 99, 0.5)',
              states: {
                hover: {
                  fill: 'rgba(55, 65, 81, 0.95)',
                  style: {
                    color: '#ffffff'
                  }
                }
              }
            }
          }
        }
      }
    };
  }, [chartData, selectedTicker]);

  // Generate wedge statistics chart options
  const wedgeStatsChartOptions = useMemo(() => {
    if (!categorizedTickers.length) return null;

    // Sort categorized tickers by date (oldest first for proper timeline)
    const sortedCategorizedTickers = [...categorizedTickers].sort((a, b) => {
      const dateA = new Date(a.date.substring(0, 4) + '-' + a.date.substring(4, 6) + '-' + a.date.substring(6, 8));
      const dateB = new Date(b.date.substring(0, 4) + '-' + b.date.substring(4, 6) + '-' + b.date.substring(6, 8));
      return dateA.getTime() - dateB.getTime();
    });

    // Create data for the stacked area chart
    const popData = sortedCategorizedTickers.map(item => {
      const timestamp = new Date(
        item.date.substring(0, 4) + '-' + 
        item.date.substring(4, 6) + '-' + 
        item.date.substring(6, 8)
      ).getTime();
      return [timestamp, item.pop.length];
    });

    const dropData = sortedCategorizedTickers.map(item => {
      const timestamp = new Date(
        item.date.substring(0, 4) + '-' + 
        item.date.substring(4, 6) + '-' + 
        item.date.substring(6, 8)
      ).getTime();
      return [timestamp, item.drop.length];
    });

    // Create total data for reference line
    const totalData = sortedCategorizedTickers.map(item => {
      const timestamp = new Date(
        item.date.substring(0, 4) + '-' + 
        item.date.substring(4, 6) + '-' + 
        item.date.substring(6, 8)
      ).getTime();
      return [timestamp, item.pop.length + item.drop.length];
    });

    return {
      chart: {
        type: 'area',
        height: 400,
        backgroundColor: 'rgba(0, 0, 0, 0.3)',
        zoomType: 'x',
        panning: {
          enabled: true,
          type: 'x',
        },
        style: {
          fontFamily: 'inherit',
        },
        plotBackgroundColor: 'rgba(0, 0, 0, 0.2)',
        plotBorderWidth: 0,
        plotShadow: false,
        spacing: [5, 5, 5, 5],
        reflow: true,
      },
      title: {
        text: 'Wedge Statistics',
        style: { 
          fontSize: '16px', 
          fontWeight: '700', 
          color: '#E5E7EB' 
        },
        align: 'left',
        x: 10,
        y: 8,
      },
              xAxis: {
          type: 'datetime',
          labels: {
            format: '{value:%Y-%m-%d}',
            style: { fontSize: '14px', color: '#D1D5DB', fontWeight: '500' },
            rotation: 0,
            step: 2,
          },
          gridLineWidth: 2,
          gridLineColor: 'rgba(107, 114, 128, 0.4)',
          lineColor: 'rgba(156, 163, 175, 0.6)',
          tickColor: 'rgba(156, 163, 175, 0.6)',
          tickWidth: 2,
          tickLength: 6,
          crosshair: {
            color: 'rgba(96, 165, 250, 0.7)',
            width: 2,
            dashStyle: 'shortdot'
          }
        },
      yAxis: {
        title: {
          text: 'Number of Events',
          style: { fontSize: '14px', fontWeight: '700', color: '#E5E7EB' },
        },
        labels: {
          style: { fontSize: '12px', color: '#D1D5DB', fontWeight: '500' },
        },
        gridLineWidth: 1,
        gridLineColor: 'rgba(107, 114, 128, 0.3)',
        lineColor: 'rgba(156, 163, 175, 0.6)',
        tickColor: 'rgba(156, 163, 175, 0.6)',
        tickWidth: 1,
        tickLength: 4,
        crosshair: {
          color: 'rgba(96, 165, 250, 0.7)',
          width: 1,
          dashStyle: 'shortdot'
        }
      },
      series: [
        {
          name: 'DROP Events',
          data: dropData,
          type: 'areaspline',
          color: '#F92672', // Monokai red
          fillColor: {
            linearGradient: {
              x1: 0,
              y1: 0,
              x2: 0,
              y2: 1
            },
            stops: [
              [0, 'rgba(249, 38, 114, 0.8)'], // Monokai red with opacity
              [1, 'rgba(249, 38, 114, 0.1)']
            ]
          },
          lineColor: '#F92672',
          lineWidth: 2,
          marker: {
            enabled: false,
          },
          tooltip: {
            pointFormat: '{point.series.name}: {point.y} events',
          },
        },
        {
          name: 'POP Events',
          data: popData,
          type: 'areaspline',
          color: '#A6E22E', // Monokai green
          fillColor: {
            linearGradient: {
              x1: 0,
              y1: 0,
              x2: 0,
              y2: 1
            },
            stops: [
              [0, 'rgba(166, 226, 46, 0.8)'], // Monokai green with opacity
              [1, 'rgba(166, 226, 46, 0.1)']
            ]
          },
          lineColor: '#A6E22E',
          lineWidth: 2,
          marker: {
            enabled: false,
          },
          tooltip: {
            pointFormat: '{point.series.name}: {point.y} events',
          },
        },
        {
          name: 'Total Events',
          data: totalData,
          type: 'spline',
          color: '#66D9EF', // Monokai blue
          lineWidth: 3,
          marker: {
            enabled: false,
          },
          tooltip: {
            pointFormat: '{point.series.name}: {point.y} events',
          },
          zIndex: 10, // Higher z-index to appear above stacked areas
        }
      ],
      tooltip: {
        shared: true,
        backgroundColor: 'rgba(17, 24, 39, 0.98)',
        borderWidth: 0,
        shadow: true,
        borderRadius: 8,
        style: { fontSize: '13px', color: '#ffffff' },
        formatter: function(this: any) {
          const date = Highcharts.dateFormat('%Y-%m-%d', this.x);
          let tooltip = `<div style="padding: 4px 0;"><b style="color: #F92672; font-size: 14px;">${date}</b></div><br/>`;
          
          this.points?.forEach((point: any) => {
            const seriesName = point.series.name;
            const value = point.y;
            let color = '#75715E'; // Default gray
            
            if (seriesName.includes('POP')) {
              color = '#A6E22E';
            } else if (seriesName.includes('DROP')) {
              color = '#F92672';
            } else if (seriesName.includes('Total')) {
              color = '#66D9EF';
            }
            
            tooltip += `<span style="color: ${color}; font-size: 16px;">●</span> <span style="color: ${color}; font-weight: 500;">${seriesName}:</span> <span style="color: #F8F8F2; font-weight: bold;">${value}</span><br/>`;
          });
          
          return tooltip;
        },
      },
      legend: {
        enabled: true,
        align: 'center',
        verticalAlign: 'bottom',
        layout: 'horizontal',
        itemStyle: { 
          fontSize: '12px',
          color: '#F8F8F2',
          fontWeight: '600'
        },
        itemHoverStyle: {
          color: '#F92672'
        },
        symbolHeight: 10,
        symbolWidth: 20,
        symbolRadius: 2,
        backgroundColor: '#272822',
        borderWidth: 1,
        borderColor: '#75715E',
        borderRadius: 6,
        shadow: true,
        itemDistance: 15,
        padding: 8,
        width: '100%',
        height: 40,
        itemWidth: 120,
        useHTML: false,
        floating: false,
        x: 0,
        y: 0,
      },
      plotOptions: {
        area: {
          stacking: 'normal',
          lineWidth: 2,
          marker: {
            enabled: true,
            radius: 3,
            symbol: 'circle',
            states: {
              hover: {
                enabled: true,
                radius: 5,
                brightness: 0.3
              }
            }
          },
          tooltip: {
            enabled: true,
          },
        },
        series: {
          animation: {
            duration: 1000,
          },
          tooltip: {
            enabled: true,
          },
        },
      },
      rangeSelector: {
        enabled: true,
        selected: 0, // 6m button (first button)
        inputEnabled: false,
        buttonTheme: {
          fill: 'rgba(0, 0, 0, 0.9)',
          stroke: 'rgba(75, 85, 99, 0.6)',
          r: 6,
          states: {
            hover: {
              fill: 'rgba(31, 41, 55, 0.9)',
              style: {
                color: '#ffffff',
              },
            },
            select: {
              fill: 'rgba(96, 165, 250, 0.8)',
              style: {
                color: '#ffffff',
                fontWeight: 'bold',
              },
            },
          },
          style: {
            color: '#9ca3af',
            fontSize: '11px',
            fontWeight: '500',
          },
        },
        buttons: [
          { type: 'month', count: 6, text: '6m' },
          { type: 'year', count: 1, text: '1y' },
          { type: 'year', count: 3, text: '3y' },
          { type: 'year', count: 5, text: '5y' },
          { type: 'all', text: 'All' },
        ],
      },
      navigator: {
        enabled: true,
        height: 30,
        margin: 5,
        outlineWidth: 0,
        outlineColor: 'transparent',
        handles: {
          backgroundColor: 'rgba(96, 165, 250, 0.8)',
          borderColor: 'rgba(96, 165, 250, 1)',
          lineColor: 'rgba(96, 165, 250, 0.5)',
          rifleColor: 'rgba(96, 165, 250, 0.8)',
        },
        xAxis: {
          gridLineColor: 'rgba(0, 0, 0, 0.3)',
          lineColor: 'rgba(75, 85, 99, 0.6)',
          tickColor: 'rgba(75, 85, 99, 0.4)',
          labels: {
            style: {
              color: '#9ca3af',
              fontSize: '9px',
            },
          },
        },
      },
      scrollbar: {
        enabled: true,
        barBackgroundColor: 'rgba(75, 85, 99, 0.5)',
        barBorderColor: 'rgba(75, 85, 99, 0.8)',
        buttonBackgroundColor: 'rgba(55, 65, 81, 0.8)',
        buttonBorderColor: 'rgba(75, 85, 99, 0.8)',
        buttonArrowColor: '#9ca3af',
        rifleColor: 'rgba(96, 165, 250, 0.8)',
        trackBackgroundColor: 'rgba(31, 41, 55, 0.3)',
        trackBorderColor: 'rgba(75, 85, 99, 0.3)',
      },
      responsive: {
        rules: [{
          condition: {
            maxWidth: 768
          },
          chartOptions: {
            legend: {
              enabled: false
            },
            chart: {
              height: 200
            },
            rangeSelector: {
              enabled: false
            },
            navigator: {
              enabled: false
            },
            scrollbar: {
              enabled: false
            }
          }
        }]
      },
      credits: {
        enabled: false,
      },
      exporting: {
        enabled: true,
        buttons: {
          contextButton: {
            symbol: 'menu',
            symbolX: 12,
            symbolY: 10,
            symbolSize: 12,
            symbolStrokeWidth: 2,
            symbolStroke: '#9ca3af',
            symbolFill: 'rgba(31, 41, 55, 0.8)',
            menuItems: ['downloadPNG', 'downloadPDF', 'downloadCSV'],
            theme: {
              fill: 'rgba(31, 41, 55, 0.95)',
              stroke: 'rgba(75, 85, 99, 0.5)',
              states: {
                hover: {
                  fill: 'rgba(55, 65, 81, 0.95)',
                  style: {
                    color: '#ffffff'
                  }
                }
              }
            }
          }
        }
      }
    };
  }, [categorizedTickers]);

  // Get visible data based on zoom window
  const getVisibleData = useCallback(() => {
    if (!chartData?.sortedData) return chartData?.sortedData || [];
    
    if (!zoomWindow) return chartData.sortedData;
    
    return chartData.sortedData.filter(item => {
      let timestamp: number;
      if (typeof item.trade_date === 'string') {
        if (item.trade_date.includes(',')) {
          const [year, month, day] = item.trade_date.split(',');
          timestamp = new Date(Number(year), Number(month) - 1, Number(day)).getTime();
        } else {
          timestamp = new Date(item.trade_date).getTime();
        }
      } else {
        timestamp = new Date(item.trade_date).getTime();
      }
      return timestamp >= zoomWindow.min && timestamp <= zoomWindow.max;
    });
  }, [chartData, zoomWindow]);

  // Get last wedge status
  const getLastWedgeStatus = useCallback(() => {
    if (!chartData?.sortedData) return null;
    
    const visibleData = getVisibleData();
    if (visibleData.length === 0) return null;
    
    // Find the last item with a wedge status
    for (let i = visibleData.length - 1; i >= 0; i--) {
      const item = visibleData[i];
      if (item.wedge_status && item.wedge_status !== 'none') {
        return {
          date: item.trade_date,
          status: item.wedge_status
        };
    }
    }
    return null;
  }, [chartData, getVisibleData]);

  // Debug logging
  useEffect(() => {
    console.log('Debug - categorizedTickers count:', categorizedTickers.length);
    console.log('Debug - selectedTicker:', selectedTicker);
    console.log('Debug - chartData:', chartData);
    console.log('Debug - chartOptions:', chartOptions);
  }, [categorizedTickers.length, selectedTicker, chartData, chartOptions]);

  if (loading && !ohlcvData.length) {
    return (
      <div className={`chart-container ${className}`}>
        <LoadingSpinner text="Loading OHLCV data..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className={`chart-container ${className}`}>
        <ErrorMessage message={`Error: ${error}`} />
        <div className="mt-4 text-center">
          <button 
            onClick={() => fetchCategorizedTickers()}
            className="btn-primary"
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Retry'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`chart-container ${className}`}>
      <div className="chart-header py-1">
        <div className="flex items-center justify-between">
          <h2 className="chart-title text-lg">
            {selectedTicker ? selectedTicker : 'OHLCV Chart'}
          </h2>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm font-medium text-text-primary">
              Date:
              <select
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="input-field"
                disabled={loading}
              >
                {categorizedTickers.length === 0 ? (
                  <option value="">No dates available</option>
                ) : (
                  <>
                    <option value="">Select a date</option>
                    {categorizedTickers.map((item) => (
                      <option key={item.date} value={item.date}>
                        {item.date.substring(0, 4)}-{item.date.substring(4, 6)}-{item.date.substring(6, 8)}
                      </option>
                    ))}
                  </>
                )}
              </select>
            </label>
            
            <label className="flex items-center gap-2 text-sm font-medium text-text-primary">
              Wedge Status:
              <select
                value={selectedWedgeStatus}
                onChange={(e) => setSelectedWedgeStatus(e.target.value as 'pop' | 'drop')}
                className="input-field"
                disabled={loading}
              >
                <option value="pop">Pop</option>
                <option value="drop">Drop</option>
              </select>
            </label>
            
            <label className="flex items-center gap-2 text-sm font-medium text-text-primary">
              Ticker:
              <select
                value={selectedTicker}
                onChange={(e) => setSelectedTicker(e.target.value)}
                className="input-field"
                disabled={loading}
              >
                {(() => {
                  if (!selectedDate) return <option value="">Select a date first</option>;
                  
                  const dateData = categorizedTickers.find(item => item.date === selectedDate);
                  if (!dateData) return <option value="">No data for selected date</option>;
                  
                  const tickers = selectedWedgeStatus === 'pop' ? dateData.pop : dateData.drop;
                  if (tickers.length === 0) return <option value="">No {selectedWedgeStatus} tickers</option>;
                  
                  return (
                    <>
                      <option value="">Select a ticker</option>
                      {tickers.map((ticker) => (
                        <option key={ticker} value={ticker}>
                          {ticker}
                        </option>
                      ))}
                    </>
                  );
                })()}
              </select>
            </label>
            
            <button
              onClick={() => fetchCategorizedTickers()}
              disabled={loading}
              className="btn-secondary text-xs"
              title="Refresh data"
            >
              {loading ? (
                <div className="loading-spinner w-4 h-4" />
              ) : (
                '↻'
              )}
            </button>
          </div>
        </div>
      </div>
      
      {chartData && (
        <div className="chart-stats py-0.5">
          <div className="grid grid-cols-5 gap-2">
            <div className="chart-stat" key="price">
              <div className="chart-stat-label text-xs leading-tight">Price</div>
              <div className="chart-stat-value text-sm leading-tight">
                {(() => {
                  const visibleData = getVisibleData();
                  if (visibleData.length === 0) return 'N/A';
                  return `$${visibleData[visibleData.length - 1].close.toFixed(2)}`;
                })()}
              </div>
            </div>
            <div className="chart-stat" key="change">
              <div className="chart-stat-label text-xs leading-tight">Change</div>
              <div className="chart-stat-value text-sm leading-tight">
                {(() => {
                  const visibleData = getVisibleData();
                  if (visibleData.length < 2) return 'N/A';
                  
                  const current = visibleData[visibleData.length - 1].close;
                  const previous = visibleData[visibleData.length - 2].close;
                  const change = current - previous;
                  const changePercent = (change / previous) * 100;
                  return `${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%)`;
                })()}
              </div>
            </div>
            <div className="chart-stat" key="range">
              <div className="chart-stat-label text-xs leading-tight">Range</div>
              <div className="chart-stat-value text-sm leading-tight">
                {(() => {
                  const visibleData = getVisibleData();
                  const prices = visibleData.map(d => d.close);
                  if (prices.length === 0) return 'N/A';
                  const max = Math.max(...prices);
                  const min = Math.min(...prices);
                  return `${min.toFixed(2)} - ${max.toFixed(2)}`;
                })()}
              </div>
            </div>
            <div className="chart-stat" key="last-wedge">
              <div className="chart-stat-label text-xs leading-tight">Last Wedge</div>
              <div className="chart-stat-value text-sm leading-tight">
                {(() => {
                  const lastWedge = getLastWedgeStatus();
                  if (!lastWedge) return 'None';
                  
                  // Format the date
                  let formattedDate: string;
                  if (typeof lastWedge.date === 'string') {
                    if (lastWedge.date.includes(',')) {
                      const [year, month, day] = lastWedge.date.split(',');
                      formattedDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
                    } else {
                      formattedDate = lastWedge.date;
                    }
                  } else {
                    formattedDate = new Date(lastWedge.date).toISOString().split('T')[0];
                  }
                  
                  const statusColor = lastWedge.status === 'pop' ? 'text-success-400' : 'text-danger-400';
                  const statusText = lastWedge.status.toUpperCase();
                  
                  return (
                    <span>
                      <span className="text-text-tertiary text-xs">{formattedDate}</span>
                      <br />
                      <span className={statusColor}>{statusText}</span>
                    </span>
                  );
                })()}
              </div>
            </div>
            <div className="chart-stat" key="date-stats">
              <div className="chart-stat-label text-xs leading-tight">Date Stats</div>
              <div className="chart-stat-value text-sm leading-tight">
                {(() => {
                  if (!selectedDate) return 'N/A';
                  const dateData = categorizedTickers.find(item => item.date === selectedDate);
                  if (!dateData) return 'N/A';
                  
                  const formattedDate = `${selectedDate.substring(0, 4)}-${selectedDate.substring(4, 6)}-${selectedDate.substring(6, 8)}`;
                  return (
                    <span>
                      <span className="text-text-tertiary text-xs">{formattedDate}</span>
                      <br />
                      <span className="text-primary-400">{dateData.pop.length}P/{dateData.drop.length}D</span>
                    </span>
                  );
                })()}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="mt-1">
        {chartOptions && (
          <HighchartsReact
            highcharts={Highcharts}
            options={chartOptions}
            constructorType="stockChart"
          />
        )}
      </div>

      <div className="mt-4">
        {wedgeStatsChartOptions && (
          <HighchartsReact
            highcharts={Highcharts}
            options={wedgeStatsChartOptions}
            constructorType="stockChart"
          />
        )}
      </div>
    </div>
  );
};

export default OHLCVChart; 