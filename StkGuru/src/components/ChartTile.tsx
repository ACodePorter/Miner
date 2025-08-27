import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// Import Highcharts and React wrapper
import Highcharts from 'highcharts/highstock';
import HighchartsReact from 'highcharts-react-official';

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


  // Refs
  const chartRef = useRef<HighchartsReact.RefObject>(null);
  const { ref: inViewRef, inView } = useInView({ rootMargin: '200px', triggerOnce: false });

  // Track current subscription to prevent duplicates
  const currentSubscriptionRef = useRef<{ ticker: string; timeframe: string } | null>(null);
  
  // Store the unsubscribe function for bars so we can call it from refresh button
  const unsubscribeBarsRef = useRef<(() => void) | null>(null);

  // Format volume with abbreviations
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
  const handleBarsUpdate = useCallback((payload: BarsPayload) => {
    if (!payload?.bars?.length) return;
    
    const chart = chartRef.current?.chart;
    if (!chart) return;
    
    // Handle initial snapshot (room join)
    if (payload.is_snapshot) {
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
        
        ohlcSeries.data[ohlcSeries.data.length - 1].update(newPoint, false);
        
        if (volumeSeries.data.length > 0) {
          volumeSeries.data[volumeSeries.data.length - 1].update([lastIncomingBar.timestamp, lastIncomingBar.volume], false);
        }
        
        // Also update the bars state for this real-time update
        setBars(currentBars => {
          if (currentBars.length === 0) return currentBars;
          
          const updatedBars = [...currentBars];
          const lastBarIndex = updatedBars.length - 1;
          
          // Update the last bar with real-time data
          updatedBars[lastBarIndex] = {
            ...updatedBars[lastBarIndex],
            open: lastIncomingBar.open,
            high: lastIncomingBar.high,
            low: lastIncomingBar.low,
            close: lastIncomingBar.close,
            volume: lastIncomingBar.volume
          };
          
          return updatedBars;
        });
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
        
        // Add new bar to state
        setBars(currentBars => [...currentBars, lastIncomingBar]);
      }
    } else {
      // No existing data, add the first point
      ohlcSeries.addPoint([
        lastIncomingBar.timestamp,
        lastIncomingBar.open,
        lastIncomingBar.high,
        lastIncomingBar.low,
        lastIncomingBar.close
      ], false, false, true);
      
      volumeSeries.addPoint([lastIncomingBar.timestamp, lastIncomingBar.volume], false, false, true);
      
      // Add first bar to state
      setBars([lastIncomingBar]);
    }
    
    chart.redraw(false);
  }, []);

  // WebSocket subscription - only subscribe once and update chart data
  useEffect(() => {
    if (!inView) return;
    
    // Check if we already have an active subscription for this ticker/timeframe
    const currentSub = currentSubscriptionRef.current;
    if (currentSub && currentSub.ticker === ticker && currentSub.timeframe === timeframe) {
      return;
    }
    
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
      unsubscribeQuote();
      unsubscribeBars();
      currentSubscriptionRef.current = null;
    };
  }, [ticker, timeframe, inView, subscribeQuote]);





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

  // Transform data for Highcharts
  const ohlc = useMemo(() => {
    return bars.map(b => [b.timestamp, b.open, b.high, b.low, b.close] as [number, number, number, number, number]);
  }, [bars]);
  
  const volumes = useMemo(() => {
    return bars.map(b => [b.timestamp, b.volume] as [number, number]);
  }, [bars]);

  // Highcharts options
  const options = useMemo<Highcharts.Options>(() => {
    const xAxisRange = calculateXAxisRange(bars, timeframe);

    return {
      chart: {
        height: 360, 
        backgroundColor: 'transparent',
        spacingTop: 0, 
        marginTop: 0, 
        spacing: [0, 0, 0, 0],
        style: {
          fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace'
        },
        type: 'stock',
        animation: { duration: 300 }
      },
      
      accessibility: { enabled: false },
      
      rangeSelector: { enabled: false },
      navigator: { enabled: true },
      scrollbar: { enabled: false },
      
      zoomType: 'x',
      resetZoomButton: { enabled: false },
      
      plotOptions: {
        candlestick: {
          color: '#FF7F7F',
          upColor: '#90EE90',
          lineWidth: 1,
          pointPadding: 0.1,
          groupPadding: 0.1,
          animation: { duration: 300 }
        },
        series: {
          animation: { duration: 300 }
        }
      },

      title: { text: undefined },
      subtitle: { text: undefined },

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
            return isIntraday 
              ? convertUTCToNYDateTime(this.value as number)
              : convertUTCToNYDate(this.value as number);
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

      yAxis: [
        {
          // Price axis (logarithmic)
          top: '0%',
          height: '80%',
          offset: 0,
          lineWidth: 1,
          lineColor: '#75715E',
          tickColor: '#75715E',
          type: 'logarithmic',
          minorTickInterval: 'auto',
          minorGridLineWidth: 0,
          endOnTick: false,
          startOnTick: false,
          min: undefined,
          max: undefined,
          gridLineWidth: 1,
          gridLineColor: '#374151',
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
        }
      ],

      series: [
        {
          type: 'candlestick',
          id: 'ohlc',
          name: ticker,
          data: ohlc,
          dataGrouping: { enabled: false }
        },
        {
          type: 'column',
          id: 'volume',
          name: 'Volume',
          data: volumes,
          yAxis: 1,
          color: '#94A3B8',
          tooltip: { valueDecimals: 0 },
          dataGrouping: { enabled: false }
        }
      ],
      
      tooltip: {
        backgroundColor: 'rgba(17, 24, 39, 0.98)',
        borderWidth: 0,
        shadow: true,
        borderRadius: 8,
        style: { fontSize: '13px', color: '#ffffff' },
        formatter: function() {
          const nyTime = convertUTCToNYTime(this.x);
          
          if (this.series.type === 'candlestick') {
            const point = this as any;
            return `
              <div style="padding: 4px 0;"><b style="color: #F92672; font-size: 14px;">${ticker}: ${nyTime}</b></div><br/>
              <span style="color: #A6E22E; font-weight: 500;">OHLC:</span><br/>
              &nbsp;&nbsp;<span style="color: #F8F8F2;">Open: $${point.open}</span><br/>
              &nbsp;&nbsp;<span style="color: #F8F8F2;">High: $${point.high}</span><br/>
              &nbsp;&nbsp;<span style="color: #F8F8F2;">Low: $${point.low}</span><br/>
              &nbsp;&nbsp;<span style="color: #F8F8F2;">Close: $${point.close}</span><br/>
            `;
          } else if (this.series.type === 'column') {
            return `
              <div style="padding: 4px 0;"><b style="color: #F92672; font-size: 14px;">${ticker}: ${nyTime}</b></div><br/>
              <span style="color: #75715E; font-weight: 500;">Volume:</span><br/>
              &nbsp;&nbsp;<span style="color: #F8F8F2;">${Highcharts.numberFormat(this.y || 0, 0)}</span><br/>
            `;
          }
          
          return '';
        }
      },

      credits: { enabled: false }
    };
  }, [ticker, timeframe, ohlc, volumes, bars]);

  // Handle refresh button click
  const handleRefresh = useCallback(() => {
    setBars([]);
    setLoading(true);
    setErrorMsg(null);
    
    if (currentSubscriptionRef.current && unsubscribeBarsRef.current) {
      unsubscribeBarsRef.current();
      
      setTimeout(() => {
        const newUnsubscribeBars = wsClient.subscribeBars(ticker, timeframe, handleBarsUpdate);
        unsubscribeBarsRef.current = newUnsubscribeBars;
      }, 100);
    }
  }, [ticker, timeframe, handleBarsUpdate]);

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
            onClick={handleRefresh}
            className="px-2 py-1 text-xs bg-slate-700 border border-slate-600 rounded-lg hover:bg-slate-600 text-slate-300 hover:text-slate-100 transition-all duration-200 flex items-center gap-1.5"
            title="Refresh chart data"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          

          
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
        
        {/* Close button */}
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
    </div>
  );
};

export default ChartTile;


