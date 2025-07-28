import React, { useState, useEffect, useCallback, useMemo } from "react";
import Highcharts from "highcharts/highstock";
import HighchartsReact from "highcharts-react-official";
import LoadingSpinner from "./LoadingSpinner";
import ErrorMessage from "./ErrorMessage";

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

interface WedgeTicker {
  ticker: string;
  // Add other fields if available from the API
}

interface OHLCVChartProps {
  autoRefresh?: boolean;
  refreshInterval?: number;
  className?: string;
}



const OHLCVChart: React.FC<OHLCVChartProps> = ({
  autoRefresh = false,
  refreshInterval = 5 * 60 * 1000, // 5 minutes
  className = "",
}) => {
  const [selectedTicker, setSelectedTicker] = useState<string>("");
  const [tickers, setTickers] = useState<WedgeTicker[]>([]);
  const [ohlcvData, setOhlcvData] = useState<OHLCVData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoomWindow, setZoomWindow] = useState<{ min: number; max: number } | null>(null);

  // Fetch tickers list
  const fetchTickers = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('Fetching tickers from /api/wedge_pop/wedges.json');
      const response = await fetch('/api/wedge_pop/wedges.json');
      console.log('Response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch tickers: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('Tickers data:', data);
      
      // Handle different data structures
      let tickersList: WedgeTicker[] = [];
      if (Array.isArray(data)) {
        tickersList = data.map((ticker: string) => ({ ticker }));
      } else if (data && typeof data === 'object') {
        // If data is an object, try to extract tickers
        if (data.tickers) {
          tickersList = Array.isArray(data.tickers) ? data.tickers.map((ticker: string) => ({ ticker })) : [];
        } else if (data.data) {
          // Handle the case where data.data is an array of strings
          if (Array.isArray(data.data)) {
            tickersList = data.data.map((ticker: string) => ({ ticker }));
          } else {
            tickersList = [];
          }
        } else {
          // Try to convert object keys to tickers
          tickersList = Object.keys(data).map(key => ({ ticker: key }));
        }
      }
      
      setTickers(tickersList);
      console.log('Processed tickers:', tickersList);
      
      // Set first ticker as default if available
      if (tickersList.length > 0 && !selectedTicker) {
        setSelectedTicker(tickersList[0].ticker);
      }
    } catch (err) {
      console.error('Failed to fetch tickers:', err);
      setError('Failed to fetch ticker list');
    } finally {
      setLoading(false);
    }
  }, [selectedTicker]);

  // Fetch OHLCV data for selected ticker
  const fetchOHLCVData = useCallback(async (ticker: string) => {
    if (!ticker) return;
    
    try {
      setLoading(true);
      setError(null);
      
      console.log('Fetching OHLCV data for ticker:', ticker);
      const response = await fetch(`/api/ohlcvw/${ticker}.json`);
      console.log('OHLCV response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch OHLCV data: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('OHLCV data:', data);
      
      // Handle different data structures
      let ohlcvList: OHLCVData[] = [];
      if (Array.isArray(data)) {
        ohlcvList = data;
      } else if (data && typeof data === 'object') {
        if (data.data && Array.isArray(data.data)) {
          ohlcvList = data.data;
        } else if (data.ohlcv && Array.isArray(data.ohlcv)) {
          ohlcvList = data.ohlcv;
        } else {
          // Try to find OHLCV data in the object
          const keys = Object.keys(data);
          for (const key of keys) {
            if (Array.isArray(data[key])) {
              ohlcvList = data[key];
              break;
            }
          }
        }
      }
      
      setOhlcvData(ohlcvList);
      console.log('Processed OHLCV data:', ohlcvList);
    } catch (err) {
      console.error('Failed to fetch OHLCV data:', err);
      setError('Failed to fetch OHLCV data');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial data fetch
  useEffect(() => {
    fetchTickers();
  }, [fetchTickers]);

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

    // Create wedge status markers
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
            symbol: 'arrow-up',
            fillColor: '#10B981',
            lineColor: '#10B981',
            lineWidth: 2,
            radius: 5
          }
        };
      } else if (item.wedge_status === 'drop') {
        return {
          x: timestamp,
          y: item.low,
          marker: {
            symbol: 'arrow-down',
            fillColor: '#EF4444',
            lineColor: '#EF4444',
            lineWidth: 2,
            radius: 5
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
            // Highlight wedge status dots when hovering over candlesticks
            if (e.target && e.target.series && e.target.series.type === 'candlestick') {
              const chart = this;
              const wedgeSeries = chart.series.find((s: any) => s.name === 'Wedge Status');
              if (wedgeSeries) {
                // Find wedge markers near the hovered candlestick
                const hoveredX = e.target.x;
                wedgeSeries.points.forEach((point: any) => {
                  if (Math.abs(point.x - hoveredX) < 24 * 60 * 60 * 1000) { // Within 1 day
                    point.update({
                      marker: {
                        radius: 5,
                        lineWidth: 2,
                        fillColor: '#F92672', // Highlight color
                        lineColor: '#F92672'
                      }
                    }, false);
                  }
                });
                chart.redraw();
              }
            }
          },
          mouseOut: function(this: any, e: any) {
            // Reset wedge status dots when mouse leaves candlesticks
            if (e.target && e.target.series && e.target.series.type === 'candlestick') {
              const chart = this;
              const wedgeSeries = chart.series.find((s: any) => s.name === 'Wedge Status');
              if (wedgeSeries) {
                wedgeSeries.points.forEach((point: any) => {
                  point.update({
                    marker: {
                      radius: 3,
                      lineWidth: 1,
                      fillColor: '#A6E22E',
                      lineColor: '#A6E22E'
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
          }
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
          zIndex: 3,
          marker: {
            enabled: true,
            radius: 1, // Very small dots
            symbol: 'arrow-up',
            fillColor: '#A6E22E', // Monokai green
            lineColor: '#A6E22E', // Monokai green
            lineWidth: 0.3, // Very thin line
            states: {
              hover: {
                enabled: true,
                radius: 3, // Small hover state
                lineWidth: 0.8, // Thin hover line
                lineColor: '#A6E22E'
              }
            }
          },
          tooltip: {
            pointFormat: '{point.series.name}: {point.y:.2f}',
          },
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

  const handleTickerChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedTicker(event.target.value);
  };

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
    console.log('Debug - tickers count:', tickers.length);
    console.log('Debug - selectedTicker:', selectedTicker);
    console.log('Debug - chartData:', chartData);
    console.log('Debug - chartOptions:', chartOptions);
  }, [tickers.length, selectedTicker, chartData, chartOptions]);

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
            onClick={() => fetchTickers()}
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
      <div className="chart-header">
        <div className="flex items-center justify-between">
          <h2 className="chart-title">
            {selectedTicker ? `${selectedTicker} OHLCV Chart` : 'OHLCV Chart'}
          </h2>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <button
              onClick={() => fetchTickers()}
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
        
        <div className="chart-controls mt-2">
          <div className="flex items-center gap-6 flex-wrap">
            <label className="flex items-center gap-2 text-sm font-medium">
              Ticker:
              <select
                value={selectedTicker}
                onChange={handleTickerChange}
                className="input-field"
                disabled={loading}
              >
                {tickers.length === 0 ? (
                  <option value="">No tickers available</option>
                ) : (
                  <>
                    <option value="">Select a ticker</option>
                    {tickers.map((ticker) => (
                      <option key={ticker.ticker} value={ticker.ticker}>
                        {ticker.ticker}
                      </option>
                    ))}
                  </>
                )}
              </select>
            </label>
          </div>
        </div>
      </div>

      {chartData && (
        <div className="chart-stats py-1 px-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="chart-stat" key="current-price">
              <div className="chart-stat-label">Current Price</div>
              <div className="chart-stat-value">
                ${(() => {
                  const visibleData = getVisibleData();
                  return visibleData[visibleData.length - 1]?.close?.toFixed(2) || 'N/A';
                })()}
              </div>
            </div>
            <div className="chart-stat" key="change">
              <div className="chart-stat-label">Change</div>
              <div className={`chart-stat-value ${
                (() => {
                  const visibleData = getVisibleData();
                  const current = visibleData[visibleData.length - 1]?.close;
                  const previous = visibleData[visibleData.length - 2]?.close;
                  if (current && previous) {
                    return current > previous ? 'text-green-600' : 'text-red-600';
                  }
                  return 'text-gray-600';
                })()
              }`}>
                {(() => {
                  const visibleData = getVisibleData();
                  const current = visibleData[visibleData.length - 1]?.close;
                  const previous = visibleData[visibleData.length - 2]?.close;
                  if (current && previous) {
                    const change = current - previous;
                    const changePercent = (change / previous) * 100;
                    return `${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%)`;
                  }
                  return 'N/A';
                })()}
              </div>
            </div>
            <div className="chart-stat" key="range">
              <div className="chart-stat-label">Range</div>
              <div className="chart-stat-value">
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
              <div className="chart-stat-label">Last Wedge</div>
              <div className="chart-stat-value">
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
                  
                  const statusColor = lastWedge.status === 'pop' ? 'text-green-600' : 'text-red-600';
                  const statusText = lastWedge.status.toUpperCase();
                  
                  return (
                    <span>
                      <span className="text-gray-400 text-xs">{formattedDate}</span>
                      <br />
                      <span className={statusColor}>{statusText}</span>
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
    </div>
  );
};

export default OHLCVChart; 