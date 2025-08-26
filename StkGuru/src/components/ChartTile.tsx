import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// Import Highcharts and React wrapper
import Highcharts from 'highcharts/highstock';
import HighchartsReact from 'highcharts-react-official';

// Import all technical indicators (side effect import - automatically registers with Highcharts)
import 'highcharts/indicators/indicators-all';

import { useInView } from 'react-intersection-observer';
import { wsClient, type QuotePayload, type BarsPayload } from '../utils/wsClient';
import { subscriptionManager } from '../utils/subscriptionManager';

// Disable data grouping globally for all Highcharts charts
// This ensures that all data points are displayed individually without grouping,
// which is important for real-time trading charts where every tick matters
Highcharts.setOptions({
  plotOptions: {
    series: {
      dataGrouping: {
        enabled: false
      }
    },
    candlestick: {
      dataGrouping: {
        enabled: false
      }
    },
    column: {
      dataGrouping: {
        enabled: false
      }
    },
    line: {
      dataGrouping: {
        enabled: false
      }
    }
  }
});

// Timezone constant for New York
const AMERICA_NEW_YORK_TZ = 'America/New_York';

// Helper function to convert UTC timestamp to New York time
// This handles the case where backend returns UTC timestamps but we want to display in NY time
function convertUTCToNYTime(utcTimestamp: number): string {
  try {
    const utcDate = new Date(utcTimestamp);
    return utcDate.toLocaleString('en-US', { 
      timeZone: AMERICA_NEW_YORK_TZ,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23'
    });
  } catch (error) {
    // Fallback to UTC if timezone conversion fails
    console.warn('Timezone conversion failed, falling back to UTC:', error);
    return new Date(utcTimestamp).toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23'
    });
  }
}

// Helper function to convert UTC timestamp to New York time (date only)
function convertUTCToNYDate(utcTimestamp: number): string {
  try {
    const utcDate = new Date(utcTimestamp);
    return utcDate.toLocaleString('en-US', { 
      timeZone: AMERICA_NEW_YORK_TZ,
      month: '2-digit',
      day: '2-digit'
    });
  } catch (error) {
    // Fallback to UTC if timezone conversion fails
    console.warn('Timezone conversion failed, falling back to UTC:', error);
    return new Date(utcTimestamp).toLocaleString('en-US', {
      month: '2-digit',
      day: '2-digit'
    });
  }
}

// Helper function to convert UTC timestamp to New York time (date + time, no seconds)
function convertUTCToNYDateTime(utcTimestamp: number): string {
  try {
    const utcDate = new Date(utcTimestamp);
    return utcDate.toLocaleString('en-US', { 
      timeZone: AMERICA_NEW_YORK_TZ,
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    });
  } catch (error) {
    // Fallback to UTC if timezone conversion fails
    console.warn('Timezone conversion failed, falling back to UTC:', error);
    return new Date(utcTimestamp).toLocaleString('en-US', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    });
  }
}

// Helper function to get time window for different timeframes
function getTimeWindowForTimeframe(timeframe: string): number {
  switch (timeframe) {
    case '1m': return 4 * 60 * 60 * 1000;      // 4 hours
    case '5m': return 5 * 24 * 60 * 60 * 1000;      // 4 hours  
    case '15m': return 9 * 24 * 60 * 60 * 1000;     // 4 hours
    case '30m': return 18 * 24 * 60 * 60 * 1000;     // 8 hours
    case '65m': return 40 * 24 * 60 * 60 * 1000;    // 24 hours
    case '1d': return 250 * 24 * 60 * 60 * 1000; // 7 days
    case '1wk': return 250 * 5 * 24 * 60 * 60 * 1000; // 30 days
    case '1mo': return 250 * 30 * 24 * 60 * 60 * 1000; // 90 days
    default: return 5 * 24 * 60 * 60 * 1000;        // 4 hours default
  }
}

// Helper function to calculate xAxis range based on time, not bar count
function calculateXAxisRange(bars: Bar[], timeframe: string) {
  if (bars.length === 0) return { min: undefined, max: undefined };
  
  const timeWindow = getTimeWindowForTimeframe(timeframe);
  const now = Date.now();
  const targetStartTime = now - timeWindow;
  
  // Find the first bar that's within our time window
  let startIndex = 0;
  for (let i = 0; i < bars.length; i++) {
    if (bars[i].timestamp >= targetStartTime) {
      startIndex = i;
      break;
    }
  }
  
  return {
    min: bars[startIndex]?.timestamp,
    max: bars[bars.length - 1]?.timestamp
  };
}

export interface ChartTileProps {
  id: string;
  initialTicker: string;
  initialInterval?: string; // e.g., '1m', '5m', '15m', '30m', '65m', '1d', '1wk', '1mo'
  onRemove?: (id: string) => void;
}

interface Bar {
  timestamp: number; // ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Technical indicator interface
interface TechnicalIndicator {
  id: string;
  type: string;
  name: string;
  params: Record<string, any>;
  yAxis?: number;
  linkedTo?: string;
}

// Available technical indicators with their parameters
const AVAILABLE_INDICATORS = [
  { type: 'sma', name: 'Simple Moving Average (SMA)', params: { period: 14 } },
  { type: 'ema', name: 'Exponential Moving Average (EMA)', params: { period: 14 } },
  { type: 'bb', name: 'Bollinger Bands (BB)', params: { period: 20, standardDeviation: 2 } },
  { type: 'rsi', name: 'Relative Strength Index (RSI)', params: { period: 14 } },
  { type: 'macd', name: 'MACD', params: { fastPeriod: 12, slowPeriod: 26, signalPeriod: 9 } },
  { type: 'stochastic', name: 'Stochastic', params: { period: 14, kPeriod: 3, dPeriod: 3 } },
  { type: 'atr', name: 'Average True Range (ATR)', params: { period: 14 } },
  { type: 'ad', name: 'Accumulation/Distribution', params: {} },
  { type: 'obv', name: 'On Balance Volume (OBV)', params: {} },
  { type: 'vwap', name: 'Volume Weighted Average Price (VWAP)', params: {} },
  { type: 'natr', name: 'Normalized ATR', params: { period: 14 } },
  { type: 'mfi', name: 'Money Flow Index (MFI)', params: { period: 14 } },
  { type: 'williamsR', name: 'Williams %R', params: { period: 14 } },
  { type: 'cci', name: 'Commodity Channel Index (CCI)', params: { period: 14 } },
  { type: 'aroon', name: 'Aroon', params: { period: 14 } },
  { type: 'aroonOscillator', name: 'Aroon Oscillator', params: { period: 14 } },
  { type: 'chaikin', name: 'Chaikin Oscillator', params: {} },
  { type: 'cmf', name: 'Chaikin Money Flow (CMF)', params: { period: 14 } },
  { type: 'dmi', name: 'Directional Movement Index (DMI)', params: { period: 14 } },
  { type: 'klinger', name: 'Klinger Oscillator', params: { fastPeriod: 34, slowPeriod: 55 } },
  { type: 'ppo', name: 'Percentage Price Oscillator (PPO)', params: { fastPeriod: 12, slowPeriod: 26 } },
  { type: 'roc', name: 'Rate of Change (ROC)', params: { period: 14 } },
  { type: 'trix', name: 'TRIX', params: { period: 14 } },
  { type: 'zigzag', name: 'Zig Zag', params: { deviation: 5, highLowIndex: 2 } }
];

export const ChartTile: React.FC<ChartTileProps> = ({ 
  id, 
  initialTicker, 
  initialInterval = '1d', 
  onRemove 
}) => {
  // Basic state
  const [ticker, setTicker] = useState(initialTicker.toUpperCase());
  const [timeframe, setTimeframe] = useState(initialInterval);
  const [bars, setBars] = useState<Bar[]>([]);
  const [loading, setLoading] = useState(false);
  const [price, setPrice] = useState<number | null>(null);
  const [change, setChange] = useState<number | null>(null);
  const [changePercent, setChangePercent] = useState<number | null>(null);
  const [volume, setVolume] = useState<number | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState(wsClient.getStatus());
  
  // Technical indicators state
  const [indicators, setIndicators] = useState<TechnicalIndicator[]>([]);
  const [showIndicatorModal, setShowIndicatorModal] = useState(false);
  const [selectedIndicator, setSelectedIndicator] = useState<typeof AVAILABLE_INDICATORS[0] | null>(null);
  
  // Use ref to track if default indicators were added (won't cause re-renders)
  const defaultIndicatorsAddedRef = useRef(false);

  // Refs
  const chartRef = useRef<HighchartsReact.RefObject>(null);
  const { ref: inViewRef, inView } = useInView({ rootMargin: '200px', triggerOnce: false });

  // Track current subscription to prevent duplicates
  // This ensures we only subscribe once per ticker/timeframe combination
  const currentSubscriptionRef = useRef<{ ticker: string; timeframe: string } | null>(null);
  
  // Store the unsubscribe function for bars so we can call it from refresh button
  const unsubscribeBarsRef = useRef<(() => void) | null>(null);

  // Format volume with abbreviations (same as Watchlist)
  const formatVolume = (volume: number) => {
    if (volume >= 1_000_000_000) return `${(volume / 1_000_000_000).toFixed(1)}B`;
    if (volume >= 1_000_000) return `${(volume / 1_000_000).toFixed(1)}M`;
    if (volume >= 1_000) return `${(volume / 1_000).toFixed(1)}K`;
    return volume.toString();
  };

  // WebSocket subscription handlers
  const subscribeQuote = useCallback(() => {
    if (!ticker) return () => {};
    return subscriptionManager.subscribe(ticker, id, (q: QuotePayload) => {
      if (typeof q.price === 'number') setPrice(q.price);
      if (typeof q.change === 'number') setChange(q.change);
      if (typeof q.changePercent === 'number') setChangePercent(q.changePercent);
      if (typeof q.volume === 'number') setVolume(q.volume);
    });
  }, [ticker, id]);

  // Cleanup subscriptions when component unmounts
  useEffect(() => {
    return () => {
      subscriptionManager.unsubscribeComponentAll(id);
    };
  }, [id]);

  // Single bars update handler - doesn't depend on ticker/timeframe to prevent recreation
  // This function is created once and reused, preventing unnecessary WebSocket resubscriptions
  const handleBarsUpdate = useCallback((payload: BarsPayload) => {
    console.log('ChartTile handleBarsUpdate called with:', payload);
    
    if (!payload?.bars?.length) {
      console.log('No bars data in payload, returning');
      return;
    }
    
    const chart = chartRef.current?.chart;
    if (!chart) {
      console.log('Chart not ready, returning');
      return;
    }
    
    // Handle initial snapshot (room join)
    if (payload.is_snapshot) {
      console.log('Processing initial snapshot with', payload.bars.length, 'bars');
      setBars(payload.bars);
      setLoading(false);
      setErrorMsg(null);
      
      // Update chart with snapshot data
      const ohlcSeries = chart.series.find(s => s.type === 'candlestick');
      const volumeSeries = chart.series.find(s => s.type === 'column');
      
      if (ohlcSeries) {
        const ohlcData = payload.bars.map(bar => [
          bar.timestamp,
          bar.open,
          bar.high,
          bar.low,
          bar.close
        ] as [number, number, number, number, number]);
        ohlcSeries.setData(ohlcData, false, false, true);
      }
      
      if (volumeSeries) {
        const volumeData = payload.bars.map(bar => [
          bar.timestamp,
          bar.volume
        ] as [number, number]);
        volumeSeries.setData(volumeData, false, false, true);
      }
      
      chart.redraw(false);
      return;
    }
    
    // Handle real-time updates
    const incoming = payload.bars;
    const lastIncomingBar = incoming[incoming.length - 1];
    
    if (!lastIncomingBar) return;
    
    const ohlcSeries = chart.series.find(s => s.type === 'candlestick');
    const volumeSeries = chart.series.find(s => s.type === 'column');
    
    if (!ohlcSeries || !volumeSeries) return;
    
    // Check if we need to add new point or update existing
    if (ohlcSeries.data.length > 0) {
      const lastPoint = ohlcSeries.data[ohlcSeries.data.length - 1];
      const lastTs = lastPoint.x;
      
      if (lastIncomingBar.timestamp === lastTs) {
        // Update existing point (real-time update to forming bar)
        const newPoint = [
          lastIncomingBar.timestamp,
          lastIncomingBar.open,
          lastIncomingBar.high,
          lastIncomingBar.low,
          lastIncomingBar.close
        ];
        
        // Update the last point
        ohlcSeries.data[ohlcSeries.data.length - 1].update(newPoint, false);
        
        // Update volume
        if (volumeSeries.data.length > 0) {
          volumeSeries.data[volumeSeries.data.length - 1].update([lastIncomingBar.timestamp, lastIncomingBar.volume], false);
        }
      } else if (lastIncomingBar.timestamp > lastTs) {
        // Add new point (completed bar)
        ohlcSeries.addPoint([
          lastIncomingBar.timestamp,
          lastIncomingBar.open,
          lastIncomingBar.high,
          lastIncomingBar.low,
          lastIncomingBar.close
        ], false, false, true);
        
        volumeSeries.addPoint([lastIncomingBar.timestamp, lastIncomingBar.volume], false, false, true);
      }
    }
    
    // Update bars state
    setBars(currentBars => {
      const newBars = [...currentBars, ...incoming];
      return newBars;
    });
    
    chart.redraw(false);
  }, []); // No dependencies - this prevents recreation

  // Data clearing is now handled in the WebSocket subscription effect

  // WebSocket subscription - only subscribe once and update chart data
  useEffect(() => {
    if (!inView) return;
    
    // Check if we already have an active subscription for this ticker/timeframe
    const currentSub = currentSubscriptionRef.current;
    if (currentSub && currentSub.ticker === ticker && currentSub.timeframe === timeframe) {
      console.log('Already subscribed to:', ticker, timeframe, '- skipping duplicate subscription');
      return;
    }
    
    console.log('WebSocket subscription effect running for:', ticker, timeframe);
    
    // Clear existing data when changing ticker/timeframe
    setBars([]);
      setLoading(true);
    setErrorMsg(null);
    
    // Update current subscription ref
    currentSubscriptionRef.current = { ticker, timeframe };
    
    // Subscribe to quotes
    const unsubscribeQuote = subscribeQuote();
    
    // Subscribe to bars
    const unsubscribeBars = wsClient.subscribeBars(ticker, timeframe, handleBarsUpdate);
    unsubscribeBarsRef.current = unsubscribeBars;
    
    return () => {
      console.log('Cleaning up WebSocket subscriptions for:', ticker, timeframe);
      unsubscribeQuote();
      unsubscribeBars();
      // Clear subscription ref
      currentSubscriptionRef.current = null;
    };
  }, [ticker, timeframe, inView, subscribeQuote]); // Removed handleBarsUpdate dependency

  // Monitor WebSocket connection status
  useEffect(() => {
    if (!inView) {
      console.log('Not in view, skipping WebSocket connection status check');
      return;
    }
    
    const checkConnectionStatus = () => {
      const status = wsClient.getStatus();
      setWsStatus(status);
      
      if (status === 'disconnected' && loading) {
        setErrorMsg('WebSocket connection lost. Trying to reconnect...');
      } else if (status === 'connected' && errorMsg && errorMsg.includes('WebSocket connection lost')) {
        setErrorMsg(null);
      }
    };
    
    checkConnectionStatus();
    const interval = setInterval(checkConnectionStatus, 5000);
    
    return () => clearInterval(interval);
  }, [inView, loading, errorMsg]);

  // Subscribe to WebSocket room state changes
  useEffect(() => {
    if (!inView) return;
    
    const unsubscribe = wsClient.onRoomStateChange(() => {
      setWsStatus(wsClient.getStatus());
    });
    
    return unsubscribe;
  }, [inView]);

  // Timeout mechanism for WebSocket subscription
  useEffect(() => {
    if (!inView || !loading) return;
    
    const timeout = setTimeout(() => {
      if (loading && bars.length === 0) {
        setErrorMsg('Timeout waiting for bars data. Please check your connection and try again.');
        setLoading(false);
      }
    }, 30000);
    
    return () => clearTimeout(timeout);
  }, [inView, loading, bars.length]);

  // Clear loading state when bars are received
  useEffect(() => {
    if (bars.length > 0 && loading) {
      setLoading(false);
    }
  }, [bars, loading]);



  // Update chart when indicators change
  useEffect(() => {
    const chart = chartRef.current?.chart;
    if (chart && bars.length > 0) {
      // Force chart redraw when indicators change
      chart.redraw();
    }
  }, [indicators, bars.length]);

  // Technical indicator management functions
  const addIndicator = useCallback((indicatorType: string, params: Record<string, any>) => {
    console.log('addIndicator called with:', indicatorType, params);
    
    const indicator = AVAILABLE_INDICATORS.find(ind => ind.type === indicatorType);
    if (!indicator) return;

    // Generate unique ID with timestamp + random suffix to ensure uniqueness
    const uniqueId = `${indicatorType}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    // Generate short name for display: "type-param1, param2" or just "type" if no params
    const shortName = Object.keys(params).length > 0 
      ? `${indicatorType}-${Object.values(params).join(', ')}`
      : indicatorType;
    
    const newIndicator: TechnicalIndicator = {
      id: uniqueId,
      type: indicatorType,
      name: shortName,
      params: { ...params },
      linkedTo: 'ohlc'
    };

    // Determine yAxis based on indicator type
    if (['rsi', 'stochastic', 'williamsR', 'cci', 'mfi', 'macd', 'ppo', 'roc', 'trix', 'aroonOscillator'].includes(indicatorType)) {
      // Oscillators need separate yAxis
      newIndicator.yAxis = 2;
    } else {
      // Overlay indicators use the same yAxis as price
      newIndicator.yAxis = 0;
    }

    console.log('Adding new indicator:', newIndicator);
    setIndicators(prev => {
      const newIndicators = [...prev, newIndicator];
      console.log('Updated indicators state:', newIndicators);
      return newIndicators;
    });
    setShowIndicatorModal(false);
    setSelectedIndicator(null);
  }, []);

  const removeIndicator = useCallback((indicatorId: string) => {
    setIndicators(prev => prev.filter(ind => ind.id !== indicatorId));
  }, []);

  // Add default EMAs when component mounts (only once)
  useEffect(() => {
    console.log('Default indicators useEffect running, current ref value:', defaultIndicatorsAddedRef.current);
    
    if (defaultIndicatorsAddedRef.current) {
      console.log('Default indicators already added, skipping');
      return;
    }
    
    console.log('Adding default EMAs...');
    
    // Add EMA 10
    addIndicator('ema', { period: 10 });
    
    // Add EMA 20
    addIndicator('ema', { period: 20 });
    
    defaultIndicatorsAddedRef.current = true;
    console.log('Default indicators added, ref set to:', defaultIndicatorsAddedRef.current);
  }, []); // Empty dependency array - only run once on mount



  // Transform data for Highcharts
  const ohlc = useMemo(() => {
    return bars.map(b => [b.timestamp, b.open, b.high, b.low, b.close] as [number, number, number, number, number]);
  }, [bars]);
  
  const volumes = useMemo(() => {
    return bars.map(b => [b.timestamp, b.volume] as [number, number]);
  }, [bars]);

  // Highcharts options
  const options = useMemo<Highcharts.Options>(() => {
    // Calculate xAxis range based on time, not bar count
    const xAxisRange = calculateXAxisRange(bars, timeframe);

    return {
      // Basic chart settings
      chart: {
        height: 360, 
        backgroundColor: 'transparent',
        spacingTop: 0, 
        marginTop: 0, 
        spacing: [0, 0, 0, 0],
        style: {
          fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace'
        },
        // Logarithmic chart options
        type: 'stock',
        // Ensure proper logarithmic rendering
        animation: {
          duration: 300
        }
      },
      
      // Disable accessibility to remove warning
      accessibility: {
        enabled: false
      },
      
      // Disable built-in features for now (we'll add them step by step)
      rangeSelector: { enabled: false },
      navigator: { enabled: true },
      scrollbar: { enabled: false },
      
      // Enable horizontal zooming but hide reset button
      zoomType: 'x',
      resetZoomButton: { enabled: false },
      
      // Plot options for better logarithmic display
      plotOptions: {
        candlestick: {
          // Logarithmic-friendly candlestick options
          color: '#FF7F7F', // Down color
          upColor: '#90EE90', // Up color
          lineWidth: 1,
          // Ensure proper display with logarithmic scaling
          pointPadding: 0.1,
          groupPadding: 0.1,
          // Animation for smooth updates
          animation: {
            duration: 300
          }
        },
        series: {
          // Global series options for logarithmic charts
          animation: {
            duration: 300
          }
        }
      },

      // Title
      title: { text: undefined },
      
      // Subtitle with change and volume information
      subtitle: { text: undefined },

      // X-axis with zoom control
      xAxis: {
        type: 'datetime',
        min: xAxisRange.min,
        max: xAxisRange.max,
        labels: {
          rotation: 0,
          style: {
            fontSize: '10px',
            color: '#F8F8F2'
          },
          formatter: function() {
            const isIntraday = timeframe.includes('m');
            
            if (isIntraday) {
              return convertUTCToNYDateTime(this.value as number);
            } else {
              // For daily timeframes, show only date
              return convertUTCToNYDate(this.value as number);
            }
          }
        },
        lineColor: '#75715E',
        tickColor: '#75715E',
        crosshair: {
          color: '#3B82F6',
          width: 1,
          zIndex: 10
        }
      },

      // Y-axes
      yAxis: [
        {
          // Price axis (logarithmic)
          // Logarithmic scaling makes percentage changes visually equal,
          // which is ideal for financial charts where relative changes matter more than absolute values
          top: '0%',
          height: '80%',
          offset: 0,
          lineWidth: 1,
          lineColor: '#75715E',
          tickColor: '#75715E',
          type: 'logarithmic',
          minorTickInterval: 'auto',
          minorGridLineWidth: 0,
          // Logarithmic-specific options for better display
          endOnTick: false,
          startOnTick: false,
          // Ensure logarithmic scaling works properly with candlestick data
          min: undefined,
          max: undefined,
          // Logarithmic grid lines
          gridLineWidth: 1,
          gridLineColor: '#374151',
          // Minor grid lines for better readability
          minorGridLineColor: '#1F2937',
          labels: {
            align: 'right',
            x: -3,
            format: '{value:.2f}',
            style: { color: '#F8F8F2' }
          },
          title: {
            text: 'Price (Log)',
            style: { color: '#F8F8F2' }
          },
          crosshair: {
            color: '#3B82F6',
            width: 1,
            zIndex: 10
          }
        },
        {
          // Volume axis
          top: '80%',
          height: '20%',
          offset: 0,
          lineWidth: 1,
          lineColor: '#75715E',
          tickColor: '#75715E',
          labels: {
            align: 'right',
            x: -3,
            formatter: function() { 
              return Highcharts.numberFormat(this.value as number, 0); 
            },
            style: { color: '#F8F8F2' }
          },
          title: {
            text: 'Volume',
            style: { color: '#F8F8F2' }
          },
          crosshair: {
            color: '#3B82F6',
            width: 1,
            zIndex: 10
          }
        },
        {
          // Oscillator indicators axis (RSI, Stochastic, etc.)
          top: '0%',
          height: '80%',
          offset: 0,
          lineWidth: 1,
          lineColor: '#75715E',
          tickColor: '#75715E',
          labels: {
            align: 'left',
            x: 3,
            style: { color: '#F8F8F2' }
          },
          title: {
            text: 'Oscillators',
            style: { color: '#F8F8F2' }
          },
          crosshair: {
            color: '#3B82F6',
            width: 1,
            zIndex: 10
          },
          // Hide this axis by default, only show when oscillators are added
          visible: indicators.some(ind => ind.yAxis === 2)
        }
      ],

      // Series
      series: [
        {
          type: 'candlestick',
          id: 'ohlc',
          name: ticker,
          data: ohlc,
          dataGrouping: {
            enabled: false
          }
        },
        {
          type: 'column',
          id: 'volume',
          name: 'Volume',
          data: volumes,
          yAxis: 1,
          color: '#94A3B8',
          tooltip: { valueDecimals: 0 },
          dataGrouping: {
            enabled: false
          }
        },
        // Add technical indicators
        ...indicators.map(indicator => ({
          type: indicator.type,
          id: indicator.id,
          name: indicator.name,
          linkedTo: indicator.linkedTo,
          yAxis: indicator.yAxis || 0,
          params: indicator.params,
          dataGrouping: {
            enabled: false
          },
          // Style indicators with different colors and line styles
          color: indicator.type === 'ema' ? '#FFD700' : 
                 indicator.type === 'sma' ? '#00CED1' : 
                 indicator.type === 'bb' ? '#FF69B4' : 
                 indicator.type === 'rsi' ? '#FF6B6B' : 
                 indicator.type === 'stochastic' ? '#4ECDC4' : 
                 indicator.type === 'macd' ? '#45B7D1' : 
                 indicator.type === 'atr' ? '#FF8C00' : 
                 indicator.type === 'obv' ? '#9370DB' : 
                 indicator.type === 'vwap' ? '#32CD32' : '#A8E6CF',
          lineWidth: indicator.type === 'bb' ? 0.5 : 1,
          // Add dash pattern for certain indicators
          dashStyle: indicator.type === 'bb' ? 'Dash' : 'Solid',
          // Disable point markers (dots) on indicator lines
          marker: { enabled: false }
        }))
      ] as Highcharts.SeriesOptionsType[],
      
      // Tooltip
      tooltip: {
        backgroundColor: 'rgba(17, 24, 39, 0.98)',
        borderWidth: 0,
        shadow: true,
        borderRadius: 8,
        style: { fontSize: '13px', color: '#ffffff' },
        formatter: function() {
          const nyTime = convertUTCToNYTime(this.x);
          
          let tooltip = `<div style="padding: 4px 0;"><b style="color: #F92672; font-size: 14px;">${ticker}: ${nyTime}</b></div><br/>`;
          
          if (this.series.type === 'candlestick') {
            const point = this as any; // Type assertion for candlestick point
            tooltip += `
              <span style="color: #A6E22E; font-weight: 500;">OHLC:</span><br/>
              &nbsp;&nbsp;<span style="color: #F8F8F2;">Open: $${point.open}</span><br/>
              &nbsp;&nbsp;<span style="color: #F8F8F2;">High: $${point.high}</span><br/>
              &nbsp;&nbsp;<span style="color: #F8F8F2;">Low: $${point.low}</span><br/>
              &nbsp;&nbsp;<span style="color: #F8F8F2;">Close: $${point.close}</span><br/>
            `;
          } else if (this.series.type === 'column') {
            tooltip += `
              <span style="color: #75715E; font-weight: 500;">Volume:</span><br/>
              &nbsp;&nbsp;<span style="color: #F8F8F2;">${Highcharts.numberFormat(this.y || 0, 0)}</span><br/>
            `;
          } else {
            // Technical indicator tooltip
            const indicator = indicators.find(ind => ind.name === this.series.name);
            if (indicator) {
              tooltip += `
                <span style="color: #A8E6CF; font-weight: 500;">${indicator.name}:</span><br/>
                &nbsp;&nbsp;<span style="color: #F8F8F2;">Value: ${Highcharts.numberFormat(this.y || 0, 4)}</span><br/>
              `;
            }
          }
          
          return tooltip;
        }
      },

      // Credits
      credits: { enabled: false }
    };
  }, [ticker, timeframe, ohlc, volumes, bars, indicators]); // Removed quote dependencies since they're now in header

  return (
    <div ref={inViewRef} className="chart-container overflow-hidden card-hover">
      {/* Header */}
      <div className="relative flex items-center justify-between gap-2 px-3 py-2 border-b border-slate-700 bg-gradient-to-br from-slate-800 to-slate-700">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            className="w-20 px-2 py-1 text-xs bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100 font-medium"
          />
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="px-2 py-1 text-xs bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100"
          >
            <option value="1m">1m</option>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
            <option value="30m">30m</option>
            <option value="65m">65m</option>
            <option value="1d">1d</option>
            <option value="1wk">1wk</option>
            <option value="1mo">1mo</option>
          </select>
          <button 
            onClick={() => {
              // Clear current data
              setBars([]);
              setLoading(true);
              setErrorMsg(null);
              
              // Unsubscribe and re-subscribe to bars to get fresh data
              if (currentSubscriptionRef.current && unsubscribeBarsRef.current) {
                // Unsubscribe from current bars subscription
                unsubscribeBarsRef.current();
                
                // Re-subscribe to get fresh data
                setTimeout(() => {
                  const newUnsubscribeBars = wsClient.subscribeBars(ticker, timeframe, handleBarsUpdate);
                  unsubscribeBarsRef.current = newUnsubscribeBars;
                }, 100); // Small delay to ensure clean unsubscribe
              }
            }} 
            className="px-2 py-1 text-xs bg-slate-700 border border-slate-600 rounded-lg hover:bg-slate-600 text-slate-300 hover:text-slate-100 transition-all duration-200 flex items-center gap-1.5"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          
          {/* Connection Status Indicator */}
          <div className="flex items-center gap-1.5 px-2 py-1 text-xs">
            <div 
              className={`w-2 h-2 rounded-full ${
                wsStatus === 'connected' 
                  ? 'bg-green-400' 
                  : wsStatus === 'connecting' 
                  ? 'bg-yellow-400' 
                  : 'bg-red-400'
              }`} 
            />
            <span className="text-slate-300">
              {wsStatus === 'connected' ? '' : 
               wsStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
            </span>
          </div>
          

          
          {/* Technical Indicators Management */}
          <div className="flex items-center gap-2">
            {/* Add Indicator Button */}
            <button
              onClick={() => setShowIndicatorModal(true)}
              className="px-2 py-1 text-xs bg-blue-600 border border-blue-500 rounded-lg hover:bg-blue-700 text-white transition-all duration-200 flex items-center gap-1"
              title="Add technical indicator"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              Add
            </button>
            
            {/* Active Indicators List */}
            {indicators.length > 0 && (
              <div className="flex items-center gap-1">
                {indicators.map(indicator => (
                  <div
                    key={indicator.id}
                    className="flex items-center px-2 py-1 text-xs bg-slate-700 border border-slate-600 rounded-lg text-slate-300"
                  >
                    <span className="truncate max-w-20">{indicator.name}</span>
                    <button
                      onClick={() => removeIndicator(indicator.id)}
                      className="text-slate-400 hover:text-red-400 transition-colors"
                      title="Remove indicator"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* Real-time Quote Information */}
          <div className="flex items-center gap-2 px-2 py-1 bg-slate-700/50 border border-slate-600 rounded-lg">
            {/* Ticker and Price */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-bold text-slate-100">{ticker}</span>
              {price !== null ? (
                <span className="text-xs font-medium text-slate-200">
                  ${price.toFixed(2)}
                </span>
              ) : (
                <span className="text-xs text-slate-400">...</span>
              )}
            </div>
            
            {/* Change Percentage */}
            {changePercent !== null ? (
              <div className="flex items-center gap-1">
                <span className={`text-xs ${changePercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {changePercent >= 0 ? '↗' : '↘'}
                </span>
                <span className={`text-xs font-medium ${changePercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {changePercent >= 0 ? '+' : ''}{changePercent.toFixed(2)}%
                </span>
              </div>
            ) : (
              <span className="text-xs text-slate-400">--</span>
            )}
            
            {/* Change Amount */}
            {change !== null ? (
              <div className="flex items-center gap-1">
                <span className={`text-xs font-medium ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {change >= 0 ? '+' : ''}{change.toFixed(2)}
                </span>
              </div>
            ) : (
              <span className="text-xs text-slate-400">--</span>
            )}
            
            {/* Volume */}
            {volume !== null ? (
              <div className="flex items-center gap-1">
                <span className="text-xs text-slate-400">Vol:</span>
                <span className="text-xs font-medium text-slate-300">
                  {formatVolume(volume)}
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-1">
                <span className="text-xs text-slate-400">Vol:</span>
                <span className="text-xs text-slate-400">--</span>
              </div>
            )}
          </div>
        </div>
        
        {/* Close button - absolutely positioned to overlay indicators */}
        {onRemove && (
          <button 
            onClick={() => onRemove(id)} 
            className="absolute top-2 right-2 p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-950/20 rounded-lg transition-all duration-200 z-20 bg-slate-800/90 border border-slate-600" 
            title="Remove chart"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Chart Content */}
      <div className="p-3 relative">
        <div className="outline-none rounded-lg overflow-hidden">
          <HighchartsReact 
            highcharts={Highcharts} 
            constructorType="stockChart" 
            options={options} 
            ref={chartRef} 
          />
        </div>
        
        {/* Loading Overlay */}
        {loading && (
          <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center rounded-lg z-10">
            <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-blue-400 rounded-full flex items-center justify-center animate-spin shadow-lg">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
          </div>
        )}
        
        {/* Error Overlay */}
        {errorMsg && (
          <div className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center rounded-lg z-10">
            <div className="text-center bg-slate-800/90 p-4 rounded-lg border border-slate-700 shadow-xl">
              <div className="w-8 h-8 mx-auto mb-2 bg-red-950/20 rounded-full flex items-center justify-center">
                <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              </div>
              <p className="text-xs text-red-400">{errorMsg}</p>
            </div>
          </div>
        )}
      </div>
      
      {/* Technical Indicator Modal */}
      {showIndicatorModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 max-w-md w-full mx-4 h-[360px] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-slate-100">Add Technical Indicator</h3>
              <button
                onClick={() => {
                  setShowIndicatorModal(false);
                  setSelectedIndicator(null);
                }}
                className="text-slate-400 hover:text-slate-300 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            {!selectedIndicator ? (
              // Indicator selection
              <div className="space-y-2">
                <p className="text-sm text-slate-300 mb-4">Select a technical indicator to add:</p>
                {AVAILABLE_INDICATORS.map(indicator => (
                  <button
                    key={indicator.type}
                    onClick={() => setSelectedIndicator(indicator)}
                    className="w-full text-left p-3 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg transition-colors"
                  >
                    <div className="font-medium text-slate-100">{indicator.name}</div>
                    <div className="text-xs text-slate-400 mt-1">
                      {Object.keys(indicator.params).length > 0 
                        ? `Parameters: ${Object.entries(indicator.params).map(([k, v]) => `${k}: ${v}`).join(', ')}`
                        : 'No parameters required'
                      }
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              // Parameter configuration
              <div className="space-y-4">
                <div>
                  <h4 className="font-medium text-slate-100 mb-2">{selectedIndicator.name}</h4>
                  <p className="text-sm text-slate-400">Configure the indicator parameters:</p>
                </div>
                
                <form onSubmit={(e) => {
                  e.preventDefault();
                  const formData = new FormData(e.currentTarget);
                  const params: Record<string, any> = {};
                  
                  Object.keys(selectedIndicator.params).forEach(key => {
                    const value = formData.get(key);
                    if (value !== null) {
                      params[key] = typeof selectedIndicator.params[key as keyof typeof selectedIndicator.params] === 'number' ? Number(value) : value;
                    }
                  });
                  
                  addIndicator(selectedIndicator.type, params);
                }}>
                  <div className="space-y-3">
                    {Object.entries(selectedIndicator.params).map(([key, defaultValue]) => (
                      <div key={key}>
                        <label className="block text-sm font-medium text-slate-300 mb-1 capitalize">
                          {key.replace(/([A-Z])/g, ' $1').trim()}
                        </label>
                        <input
                          type="number"
                          name={key}
                          defaultValue={defaultValue}
                          min="1"
                          step="1"
                          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50"
                          required
                        />
                      </div>
                    ))}
                  </div>
                  
                  <div className="flex gap-3 mt-6">
                    <button
                      type="button"
                      onClick={() => setSelectedIndicator(null)}
                      className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-slate-300 transition-colors"
                    >
                      Back
                    </button>
                    <button
                      type="submit"
                      className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 border border-blue-500 rounded-lg text-white transition-colors"
                    >
                      Add Indicator
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ChartTile;


