import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Highcharts from 'highcharts/highstock';
import HighchartsReact from 'highcharts-react-official';
import { useInView } from 'react-intersection-observer';
import { wsClient, type QuotePayload, type BarsPayload } from '../utils/wsClient';
import { marketDataApi } from '../utils/api';

type IndicatorType = 'EMA' | 'SMA' | 'MACD' | 'RSI';

// Timezone constant for New York
const AMERICA_NEW_YORK_TZ = 'America/New_York';

export interface ChartTileProps {
  id: string;
  initialTicker: string;
  initialInterval?: string; // e.g., '1m', '5m', '65m', '1d'
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

interface IndicatorConfig {
  id: string;
  type: IndicatorType;
  params: Record<string, number>;
}

// Highcharts live candlestick configuration
const LIVE_CANDLESTICK_CONFIG = {
  // Optimize for real-time updates
  chart: {
    animation: {
      duration: 300,
      easing: 'easeOutQuart'
    },
    events: {
      load: function() {
        // Chart loaded, ready for live updates
        console.log('Chart loaded and ready for live updates');
      }
    }
  },
  
  // Optimize series for live updates
  plotOptions: {
    candlestick: {
      dataGrouping: { enabled: false }, // Disable grouping for live data
      animation: {
        duration: 300,
        easing: 'easeOutQuart'
      },
      // Enable live updates
      enableMouseTracking: true,
      stickyTracking: false
    },
    column: {
      dataGrouping: { enabled: false },
      animation: {
        duration: 300,
        easing: 'easeOutQuart'
      }
    },
    line: {
      dataGrouping: { enabled: false },
      animation: {
        duration: 300,
        easing: 'easeOutQuart'
      }
    }
  }
};

function calculateEMAAligned(values: number[], period: number): (number | null)[] {
  // Wilder-style aligned EMA: keep index alignment and handle nulls gracefully
  const out: (number | null)[] = new Array(values.length).fill(null);
  if (period <= 1) return values.map(v => (Number.isFinite(v) ? v : null));
  const k = 2 / (period + 1);
  let emaPrev: number | null = null;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (!Number.isFinite(v)) {
      // keep output null if no price
      continue;
    }
    if (emaPrev == null) {
      // seed with first valid value (avoids SMA seeding discrepancies across providers)
      emaPrev = v;
    } else {
      emaPrev = k * v + (1 - k) * emaPrev;
    }
    out[i] = emaPrev;
  }
  return out;
}

function calculateSMA(values: number[], period: number): number[] {
  const result: number[] = new Array(values.length).fill(NaN);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) result[i] = sum / period;
  }
  return result;
}

function calculateMACD(values: number[], fast = 10, slow = 20, signal = 5) {
  // EMA aligned arrays
  const emaFast = calculateEMAAligned(values, fast);
  const emaSlow = calculateEMAAligned(values, slow);
  const macdLine: (number | null)[] = values.map((_, i) =>
    emaFast[i] != null && emaSlow[i] != null ? (emaFast[i]! - emaSlow[i]!) : null
  );
  // Signal EMA computed over macdLine, aligned without compressing indices
  const signalLine: (number | null)[] = new Array(values.length).fill(null);
  const k = 2 / (signal + 1);
  let sigPrev: number | null = null;
  for (let i = 0; i < macdLine.length; i++) {
    const v = macdLine[i];
    if (v == null) continue;
    if (sigPrev == null) {
      sigPrev = v;
    } else {
      sigPrev = k * v + (1 - k) * sigPrev;
    }
    signalLine[i] = sigPrev;
  }
  const histogram: (number | null)[] = macdLine.map((v, i) => (
    v != null && signalLine[i] != null ? v - (signalLine[i] as number) : null
  ));
  return { macdLine, signalLine, histogram };
}

function calculateRSI(values: number[], period = 14): number[] {
  const rsi: number[] = new Array(values.length).fill(NaN);
  let gain = 0;
  let loss = 0;
  for (let i = 1; i < values.length; i++) {
    const change = values[i] - values[i - 1];
    gain += Math.max(change, 0);
    loss += Math.max(-change, 0);
    if (i >= period) {
      const prevChange = values[i - period + 1] - values[i - period];
      gain -= Math.max(prevChange, 0);
      loss -= Math.max(-prevChange, 0);
    }
    if (i >= period) {
      const avgGain = gain / period;
      const avgLoss = loss / period;
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      rsi[i] = 100 - 100 / (1 + rs);
    }
  }
  return rsi;
}

export const ChartTile: React.FC<ChartTileProps> = ({ id, initialTicker, initialInterval = '1d', onRemove }) => {
  const [ticker, setTicker] = useState(initialTicker.toUpperCase());
  const [timeframe, setTimeframe] = useState(initialInterval);
  const [bars, setBars] = useState<Bar[]>([]);
  const [loading, setLoading] = useState(false);
  const [price, setPrice] = useState<number | null>(null);
  const [indicators, setIndicators] = useState<IndicatorConfig[]>([
    { id: 'ema-10', type: 'EMA', params: { period: 10 } },
    { id: 'ema-20', type: 'EMA', params: { period: 20 } }
  ]);
  const [indicatorToAdd, setIndicatorToAdd] = useState<IndicatorType>('EMA');
  const [showIndicatorDialog, setShowIndicatorDialog] = useState(false);
  const [indicatorParams, setIndicatorParams] = useState<Record<string, number>>({});
  const chartRef = useRef<HighchartsReact.RefObject>(null);
  const barsAbortRef = useRef<AbortController | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const { ref: inViewRef, inView } = useInView({ rootMargin: '200px', triggerOnce: false });
  const defaultZoomAppliedRef = useRef(false);


  const fetchBars = async () => {
    if (!ticker) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      if (barsAbortRef.current) {
        barsAbortRef.current.abort();
      }
      const controller = new AbortController();
      barsAbortRef.current = controller;
      
      const data = await marketDataApi.getBars(ticker, timeframe, 'max');
      if (data && data.bars) {
        const raw: Bar[] = data.bars;
        // Keep original UTC timestamps, we'll format as NY time in display
        setBars(raw);
        setErrorMsg(null);
      } else {
        throw new Error('No bars data available');
      }
    } catch (e: any) {
      // eslint-disable-next-line no-console
      if (e?.name === 'AbortError') return;
      console.error('fetchBars error', e);
      setErrorMsg('Failed to load bars');
    } finally {
      setLoading(false);
    }
  };

  const subscribeQuote = useCallback(() => {
    if (!ticker) return () => {};
    return wsClient.subscribe(ticker, (q: QuotePayload) => {
      if (typeof q.price === 'number') setPrice(q.price);
    });
  }, [ticker]);

  // Helper function to update indicators with new data
  const updateIndicators = useCallback((chart: Highcharts.Chart, newBars: Bar[]) => {
    if (!newBars.length) return;
    
    const closes = newBars.map(b => b.close);
    
    // Update each indicator series
    indicators.forEach(indicator => {
      if (indicator.type === 'EMA') {
        const period = indicator.params.period ?? 20;
        const ema = calculateEMAAligned(closes, period);
        const emaSeries = chart.series.find(s => s.name === `EMA(${period})`);
        
        if (emaSeries) {
          const data = ema.map((v, i) => [newBars[i]?.timestamp, v] as any);
          emaSeries.setData(data, false, false, true);
        }
      } else if (indicator.type === 'SMA') {
        const period = indicator.params.period ?? 20;
        const sma = calculateSMA(closes, period);
        const smaSeries = chart.series.find(s => s.name === `SMA(${period})`);
        
        if (smaSeries) {
          const data = sma.map((v, i) => [newBars[i]?.timestamp, v] as any);
          smaSeries.setData(data, false, false, true);
        }
      } else if (indicator.type === 'MACD') {
        const fast = indicator.params.fast ?? 10;
        const slow = indicator.params.slow ?? 20;
        const signal = indicator.params.signal ?? 5;
        const { macdLine, signalLine, histogram } = calculateMACD(closes, fast, slow, signal);
        
        const macdSeries = chart.series.find(s => s.name === 'MACD');
        const signalSeries = chart.series.find(s => s.name === 'Signal');
        const histSeries = chart.series.find(s => s.name === 'Hist');
        
        if (macdSeries) {
          const data = macdLine.map((v, i) => [newBars[i]?.timestamp, v] as any);
          macdSeries.setData(data, false, false, true);
        }
        if (signalSeries) {
          const data = signalLine.map((v, i) => [newBars[i]?.timestamp, v] as any);
          signalSeries.setData(data, false, false, true);
        }
        if (histSeries) {
          const data = histogram.map((v, i) => [newBars[i]?.timestamp, v] as any);
          histSeries.setData(data, false, false, true);
        }
      } else if (indicator.type === 'RSI') {
        const period = indicator.params.period ?? 14;
        const rsi = calculateRSI(closes, period);
        const rsiSeries = chart.series.find(s => s.name === `RSI(${period})`);
        
        if (rsiSeries) {
          const data = rsi.map((v, i) => [newBars[i]?.timestamp, v] as any);
          rsiSeries.setData(data, false, false, true);
        }
      }
    });
  }, [indicators]);

  // WebSocket bars update handler
  const handleBarsUpdate = useCallback((payload: BarsPayload) => {
    if (!payload?.bars?.length) {
      return;
    }
    
    const chart = (chartRef as any)?.current?.chart as Highcharts.Chart | undefined;
    if (!chart) return;
    
    // Handle initial snapshot (room join)
    if (payload.is_snapshot) {
      // Set initial data from WebSocket snapshot
      setBars(payload.bars);
      setLoading(false); // Clear loading when we get snapshot
      setErrorMsg(null);
      
      // Update chart with snapshot data
      const ohlcSeries = chart.series.find(s => s.type === 'candlestick');
      const volumeSeries = chart.series.find(s => s.type === 'column' && s.name === 'Volume');
      
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
      
      // Update indicators with new data
      updateIndicators(chart, payload.bars);
      
      // Trigger final redraw
      chart.redraw(false);
      return;
    }
    
    // Handle real-time updates (live room updates)
    const incoming = payload.bars;
    const lastIncomingBar = incoming[incoming.length - 1];
    
    if (!lastIncomingBar) return;
    
    // For minute bars, we might get updates to the last forming bar
    if (timeframe.includes('m')) {
      const ohlcSeries = chart.series.find(s => s.type === 'candlestick');
      const volumeSeries = chart.series.find(s => s.type === 'column' && s.name === 'Volume');
      
      if (ohlcSeries && ohlcSeries.data.length > 0) {
        const lastPoint = ohlcSeries.data[ohlcSeries.data.length - 1];
        const lastTs = lastPoint.x;
        
        if (lastIncomingBar.timestamp === lastTs) {
          // Update the last forming bar (real-time update)
          const newPoint = [
            lastIncomingBar.timestamp,
            lastIncomingBar.open,
            lastIncomingBar.high,
            lastIncomingBar.low,
            lastIncomingBar.close
          ] as [number, number, number, number, number];
          
          // Use removePoint and addPoint for updating
          ohlcSeries.removePoint(ohlcSeries.data.length - 1, false);
          ohlcSeries.addPoint(newPoint, false, false, true);
        } else if (lastIncomingBar.timestamp > lastTs) {
          // New bar completed, add it
          const newPoint = [
            lastIncomingBar.timestamp,
            lastIncomingBar.open,
            lastIncomingBar.high,
            lastIncomingBar.low,
            lastIncomingBar.close
          ] as [number, number, number, number, number];
          
          ohlcSeries.addPoint(newPoint, false, false, true);
        }
      }
      
      if (volumeSeries && volumeSeries.data.length > 0) {
        const lastPoint = volumeSeries.data[volumeSeries.data.length - 1];
        const lastTs = lastPoint.x;
        
        if (lastIncomingBar.timestamp === lastTs) {
          // Update the last forming bar volume
          volumeSeries.removePoint(volumeSeries.data.length - 1, false);
          volumeSeries.addPoint([lastIncomingBar.timestamp, lastIncomingBar.volume], false, false, true);
        } else if (lastIncomingBar.timestamp > lastTs) {
          // New bar completed, add volume
          volumeSeries.addPoint([lastIncomingBar.timestamp, lastIncomingBar.volume], false, false, true);
        }
      }
    } else {
      // For daily/weekly bars, just append new ones
      const ohlcSeries = chart.series.find(s => s.type === 'candlestick');
      const volumeSeries = chart.series.find(s => s.type === 'column' && s.name === 'Volume');
      
      if (ohlcSeries && ohlcSeries.data.length > 0) {
        const lastTs = ohlcSeries.data[ohlcSeries.data.length - 1].x;
        
        for (const bar of incoming) {
          if (bar.timestamp > lastTs) {
            const newPoint = [
              bar.timestamp,
              bar.open,
              bar.high,
              bar.low,
              bar.close
            ] as [number, number, number, number, number];
            
            ohlcSeries.addPoint(newPoint, false, false, true);
          }
        }
      }
      
      if (volumeSeries && volumeSeries.data.length > 0) {
        const lastTs = volumeSeries.data[volumeSeries.data.length - 1].x;
        
        for (const bar of incoming) {
          if (bar.timestamp > lastTs) {
            volumeSeries.addPoint([bar.timestamp, bar.volume], false, false, true);
          }
        }
      }
    }
    
    // Update indicators with new data
    updateIndicators(chart, [...bars, ...incoming]);
    
    // Trigger chart update for real-time data
    chart.redraw(false); // false = no animation for real-time updates
  }, [timeframe, bars, updateIndicators]);

  // Clear data and show loading when ticker or timeframe changes
  useEffect(() => {
    setBars([]);
    setLoading(true);
    setErrorMsg(null);
    defaultZoomAppliedRef.current = false;
  }, [ticker, timeframe]);

  // Initial load only - fetch bars when component first comes into view
  useEffect(() => {
    if (!inView) return;
    fetchBars();
  }, [inView]); // Only depend on inView, not ticker/timeframe

  // Reset default zoom flag when ticker or timeframe changes
  useEffect(() => {
    defaultZoomAppliedRef.current = false;
  }, [ticker, timeframe]);

  // WebSocket subscription - join room for ticker/timeframe
  useEffect(() => {
    if (!inView) return;
    
    // Subscribe to quotes
    const unsubscribeQuote = subscribeQuote();
    
    // Subscribe to bars (join room)
    const unsubscribeBars = wsClient.subscribeBars(ticker, timeframe, handleBarsUpdate);
    
    return () => {
      unsubscribeQuote();
      unsubscribeBars();
    };
  }, [ticker, timeframe, inView, subscribeQuote, handleBarsUpdate]);

  // Monitor bars state changes
  useEffect(() => {
    // Trigger chart update when bars change
    const chart = (chartRef as any)?.current?.chart as Highcharts.Chart | undefined;
    if (chart && bars.length > 0) {
      chart.redraw();
    }
  }, [bars]);

  // Apply default zoom to the latest 128 bars once per ticker/interval
  useEffect(() => {
    if (defaultZoomAppliedRef.current) return;
    if (!bars || bars.length < 2) return;
    const chart = (chartRef as any)?.current?.chart as Highcharts.Chart | undefined;
    const axis = chart?.xAxis && chart.xAxis[0];
    if (!axis) return;
    const endIndex = bars.length - 1;
    const startIndex = Math.max(0, bars.length - 128);
    const min = bars[startIndex].timestamp;
    const max = bars[endIndex].timestamp;
    axis.setExtremes(min, max, true, false);
    defaultZoomAppliedRef.current = true;
  }, [bars]);

  const ohlc = useMemo(() => {
    return bars.map(b => [b.timestamp, b.open, b.high, b.low, b.close] as [number, number, number, number, number]);
  }, [bars]);
  
  const volumes = useMemo(() => {
    return bars.map(b => [b.timestamp, b.volume] as [number, number]);
  }, [bars]);
  
  const closes = useMemo(() => {
    return bars.map(b => b.close);
  }, [bars]);

  const hasMACD = useMemo(() => indicators.some(i => i.type === 'MACD'), [indicators]);
  const hasRSI = useMemo(() => indicators.some(i => i.type === 'RSI'), [indicators]);

  const axisLayout = useMemo(() => {
    // Calculate dynamic heights
    let price = 80, macd = 0, rsi = 0, volume = 20;
    const count = (hasMACD ? 1 : 0) + (hasRSI ? 1 : 0);
    if (count === 1) { price = 70; volume = 10; if (hasMACD) macd = 20; else rsi = 20; }
    if (count === 2) { price = 55; macd = 20; rsi = 15; volume = 10; }
    let top = 0;
    const yAxis: Highcharts.YAxisOptions[] = [];
    const indices: { price: number; volume: number; macd: number | null; rsi: number | null } = { price: 0, volume: 0, macd: null, rsi: null };
    // Price axis (logarithmic for candlesticks)
    yAxis.push({
      top: `${top}%`, height: `${price}%`, offset: 0, lineWidth: 1,
      type: 'logarithmic',
      labels: { align: 'right', x: -3, format: '{value:.2f}' }, title: { text: 'Price (Log)' }
    });
    indices.price = 0; top += price;
    // MACD axis
    if (hasMACD) {
      indices.macd = yAxis.length;
      yAxis.push({ top: `${top}%`, height: `${macd}%`, offset: 0, lineWidth: 1,
        labels: { align: 'right', x: -3, format: '{value:.2f}' }, title: { text: 'MACD' } });
      top += macd;
    }
    // RSI axis
    if (hasRSI) {
      indices.rsi = yAxis.length;
      yAxis.push({ top: `${top}%`, height: `${rsi}%`, offset: 0, lineWidth: 1,
        labels: { align: 'right', x: -3, format: '{value:.2f}' }, title: { text: 'RSI' } });
      top += rsi;
    }
    // Volume axis
    indices.volume = yAxis.length;
    yAxis.push({ top: `${top}%`, height: `${volume}%`, offset: 0, lineWidth: 1,
      labels: { align: 'right', x: -3, formatter: function (this: any) { return Highcharts.numberFormat(this.value as number, 0); } }, title: { text: 'Volume' } });
    return { yAxis, indices };
  }, [hasMACD, hasRSI]);

  const indicatorSeries = useMemo(() => {
    const series: Highcharts.SeriesOptionsType[] = [];
    for (const ind of indicators) {
      if (ind.type === 'EMA') {
        const period = ind.params.period ?? 20;
        const ema = calculateEMAAligned(closes, period);
        const data = ema.map((v, i) => [bars[i]?.timestamp, v] as any);
        series.push({ type: 'line', id: ind.id, name: `EMA(${period})`, data, yAxis: axisLayout.indices.price, color: '#8B5CF6', lineWidth: 1 });
      } else if (ind.type === 'SMA') {
        const period = ind.params.period ?? 20;
        const sma = calculateSMA(closes, period);
        const data = sma.map((v, i) => [bars[i]?.timestamp, v] as any);
        series.push({ type: 'line', id: ind.id, name: `SMA(${period})`, data, yAxis: axisLayout.indices.price, color: '#10B981', lineWidth: 1 });
      } else if (ind.type === 'MACD') {
        const fast = ind.params.fast ?? 10;
        const slow = ind.params.slow ?? 20;
        const signal = ind.params.signal ?? 5;
        const { macdLine, signalLine, histogram } = calculateMACD(closes, fast, slow, signal);
        const macdData = macdLine.map((v, i) => [bars[i]?.timestamp, v] as any);
        const signalData = signalLine.map((v, i) => [bars[i]?.timestamp, v] as any);
        const histData = histogram.map((v, i) => [bars[i]?.timestamp, v] as any);
        const macdAxis = axisLayout.indices.macd ?? axisLayout.indices.price;
        series.push({ type: 'line', id: `${ind.id}-macd`, name: `MACD`, data: macdData, yAxis: macdAxis, color: '#F59E0B', lineWidth: 1 });
        series.push({ type: 'line', id: `${ind.id}-signal`, name: `Signal`, data: signalData, yAxis: macdAxis, color: '#3B82F6', lineWidth: 1 });
        series.push({ type: 'column', id: `${ind.id}-hist`, name: `Hist`, data: histData, yAxis: macdAxis, color: '#9CA3AF' });
      } else if (ind.type === 'RSI') {
        const period = ind.params.period ?? 14;
        const rsi = calculateRSI(closes, period);
        const data = rsi.map((v, i) => [bars[i]?.timestamp, v] as any);
        const rsiAxis = axisLayout.indices.rsi ?? axisLayout.indices.price;
        series.push({ type: 'line', id: ind.id, name: `RSI(${period})`, data, yAxis: rsiAxis, color: '#EF4444', lineWidth: 1 });
      }
    }
    return series;
  }, [indicators, bars, closes, axisLayout]);

  const options = useMemo<Highcharts.Options>(() => ({
    rangeSelector: { enabled: false },
    navigator: { enabled: false },
    scrollbar: { enabled: false },
    title: { text: undefined },
    chart: { 
      height: 360, 
      backgroundColor: 'transparent', 
      spacingTop: 0, 
      marginTop: 0, 
      spacing: [0, 0, 0, 0],
      // Use live candlestick configuration
      ...LIVE_CANDLESTICK_CONFIG.chart,
      // Enable live redraw for real-time updates
      events: {
        load: function() {
          // Chart loaded, ready for real-time updates
          console.log('Chart loaded and ready for live updates');
        },
        // Optimize for real-time updates
        redraw: function() {
          // Chart redrawn, ensure smooth updates
        }
      }
    },
    xAxis: { 
      ordinal: true,
      // Optimize for real-time updates
      type: 'datetime',
      labels: {
        rotation: 0,
        step: 1, // Show every label to prevent overlap
        style: {
          fontSize: '10px' // Smaller font to prevent overlap
        },
        formatter: function() {
          const date = new Date(this.value);
          // For daily or larger timeframes, show date only
          // For intraday timeframes, show date + time
          const isIntraday = timeframe.includes('m');
          
          if (isIntraday) {
            return date.toLocaleString('en-US', { 
              timeZone: AMERICA_NEW_YORK_TZ,
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              hourCycle: 'h23' // Use 24-hour format
            });
          } else {
            return date.toLocaleString('en-US', { 
              timeZone: AMERICA_NEW_YORK_TZ,
              month: '2-digit',
              day: '2-digit'
            });
          }
        }
      },
      // Enable live updates for real-time data
      events: {
        afterSetExtremes: function() {
          // X-axis extremes updated for real-time data
        }
      }
    },
    // Use live candlestick plot options
    plotOptions: {
      ...LIVE_CANDLESTICK_CONFIG.plotOptions,
      series: {
        dataGrouping: { enabled: false }, // Disable grouping for live data
        lineWidth: 1,
        // Enable animation for real-time updates
        animation: {
          duration: 300,
          easing: 'easeOutQuart'
        },
        // Enable live redraw for real-time updates
        enableMouseTracking: true,
        stickyTracking: false
      }
    },
        tooltip: { 
          split: false, // Share tooltip across all series
          shared: true, // Enable shared tooltip
          useHTML: true, // Enable HTML in tooltip
          valueDecimals: 2,
          backgroundColor: 'rgba(17, 24, 39, 0.98)', // Match OHLCV chart style
          borderWidth: 0,
          shadow: true,
          borderRadius: 8,
          style: { fontSize: '13px', color: '#ffffff' }, // Match OHLCV chart style
          formatter: function() {
            const date = new Date(this.x);
            const nyTime = date.toLocaleString('en-US', { 
              timeZone: AMERICA_NEW_YORK_TZ,
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              hourCycle: 'h23'
            });
            
            let tooltip = `<div style="padding: 4px 0;"><b style="color: #F92672; font-size: 14px;">${ticker}: ${nyTime}</b></div><br/>`;
            
            // Group data by series type
            if (this.points && this.points.length > 0) {
              // Find OHLC data first - look for candlestick series by type or name
              const ohlcPoint = this.points.find((point: any) => 
                point.series?.type === 'candlestick' || 
                point.series?.name === ticker ||
                (point.series?.options && point.series.options.type === 'candlestick')
              );
              
              if (ohlcPoint) {
                tooltip += `<span style="color: #A6E22E; font-size: 16px;">●</span> <span style="color: #A6E22E; font-weight: 500;">OHLC:</span><br/>`;
                // Access OHLC data from the point's options for candlestick series
                const pointOptions = (ohlcPoint as any).options;
                if (pointOptions) {
                  tooltip += `&nbsp;&nbsp;<span style="color: #A6E22E; font-weight: 500;">O:</span> <span style="color: #F8F8F2; font-weight: bold;">$${pointOptions.open?.toFixed(2) || 'N/A'}</span><br/>`;
                  tooltip += `&nbsp;&nbsp;<span style="color: #FD971F; font-weight: 500;">H:</span> <span style="color: #F8F8F2; font-weight: bold;">$${pointOptions.high?.toFixed(2) || 'N/A'}</span><br/>`;
                  tooltip += `&nbsp;&nbsp;<span style="color: #F92672; font-weight: 500;">L:</span> <span style="color: #F8F8F2; font-weight: bold;">$${pointOptions.low?.toFixed(2) || 'N/A'}</span><br/>`;
                  tooltip += `&nbsp;&nbsp;<span style="color: #66D9EF; font-weight: 500;">C:</span> <span style="color: #F8F8F2; font-weight: bold;">$${pointOptions.close?.toFixed(2) || 'N/A'}</span><br/>`;
                }
              }
              
              // Find Volume data - look for column series by type or name
              const volumePoint = this.points.find((point: any) => 
                point.series?.type === 'column' || 
                point.series?.name === 'Volume' ||
                (point.series?.options && point.series.options.type === 'column')
              );
              if (volumePoint && volumePoint.y !== null && volumePoint.y !== undefined) {
                tooltip += `<span style="color: #75715E; font-size: 16px;">●</span> <span style="color: #75715E; font-weight: 500;">Volume:</span><br/>`;
                tooltip += `&nbsp;&nbsp;<span style="color: #75715E; font-weight: 500;">V:</span> <span style="color: #F8F8F2; font-weight: bold;">${Highcharts.numberFormat(volumePoint.y, 0)}</span><br/>`;
              }
              
              // Group indicators by type - exclude candlestick and volume, but allow indicator columns
              const indicatorPoints = this.points.filter((point: any) => 
                point.series?.type !== 'candlestick' && 
                point.series?.name !== ticker &&
                point.series?.name !== 'Volume'
              );
              
              if (indicatorPoints.length > 0) {
                // Group indicators by their base type (remove suffixes like -macd, -signal, -hist)
                const indicatorGroups: Record<string, any[]> = {};
                
                indicatorPoints.forEach((point: any) => {
                  if (point.series?.name) {
                    // Extract base indicator name by removing common suffixes
                    let baseName = point.series.name;
                    
                    // Handle MACD components - group MACD, Signal, and Hist together
                    if (baseName === 'MACD' || baseName === 'Signal' || baseName === 'Hist') {
                      baseName = 'MACD';
                    }
                    // Handle EMA/SMA with period
                    else if (baseName.includes('EMA(') || baseName.includes('SMA(')) {
                      baseName = baseName.split('(')[0]; // Get EMA or SMA
                    }
                    // Handle RSI with period
                    else if (baseName.includes('RSI(')) {
                      baseName = 'RSI';
                    }
                    
                    if (!indicatorGroups[baseName]) {
                      indicatorGroups[baseName] = [];
                    }
                    indicatorGroups[baseName].push(point);
                  }
                });
                
                // Add each indicator group
                Object.entries(indicatorGroups).forEach(([groupName, points]) => {
                  tooltip += `<span style="color: #FD971F; font-size: 16px;">●</span> <span style="color: #FD971F; font-weight: 500;">${groupName}:</span><br/>`;
                  
                  points.forEach((point: any) => {
                    const value = point.y !== null ? point.y.toFixed(2) : 'N/A';
                    let label = '';
                    let color = '#75715E'; // Default gray
                    
                    // Customize labels and colors for different indicator types
                    if (groupName === 'MACD') {
                      // For MACD, use the series name to determine the component
                      if (point.series?.name) {
                        if (point.series.name.includes('MACD')) {
                          label = 'MACD';
                          color = '#A6E22E'; // Green
                        } else if (point.series.name.includes('Signal')) {
                          label = 'Signal';
                          color = '#F92672'; // Red
                        } else if (point.series.name.includes('Hist')) {
                          label = 'Hist';
                          color = '#75715E'; // Gray
                        } else {
                          label = 'Value';
                          color = '#75715E';
                        }
                      }
                    } else if (groupName === 'EMA') {
                      // For EMA, show the period
                      const period = point.series?.name?.match(/\((\d+)\)/)?.[1] || '';
                      label = period ? `EMA(${period})` : 'EMA';
                      color = '#8B5CF6'; // Purple
                    } else if (groupName === 'SMA') {
                      // For SMA, show the period
                      const period = point.series?.name?.match(/\((\d+)\)/)?.[1] || '';
                      label = period ? `SMA(${period})` : 'SMA';
                      color = '#10B981'; // Green
                    } else if (groupName === 'RSI') {
                      // For RSI, show the period
                      const period = point.series?.name?.match(/\((\d+)\)/)?.[1] || '';
                      label = period ? `RSI(${period})` : 'RSI';
                      color = '#EF4444'; // Red
                    } else {
                      label = 'Value';
                      color = '#75715E';
                    }
                    
                    tooltip += `&nbsp;&nbsp;<span style="color: ${color}; font-weight: 500;">${label}:</span> <span style="color: #F8F8F2; font-weight: bold;">${value}</span><br/>`;
                  });
                });
              }
            }
            
            return tooltip;
          }
        },
    yAxis: axisLayout.yAxis,
    series: [
      { type: 'candlestick', id: 'ohlc', name: ticker, data: ohlc, lineWidth: 1 },
      { type: 'column', id: 'volume', name: 'Volume', data: volumes, yAxis: axisLayout.indices.volume, color: '#94A3B8', tooltip: { valueDecimals: 0 } },
      ...indicatorSeries,
    ],
    credits: { enabled: false },
  }), [ticker, timeframe, price, ohlc, volumes, indicatorSeries, axisLayout]);

  const handleAddIndicator = () => {
    // Reset params and open dialog
    setIndicatorParams({});
    setShowIndicatorDialog(true);
  };

  const confirmAddIndicator = () => {
    const type = indicatorToAdd;
    const id = `${type}-${Date.now()}`;
    
    // Set default params if none provided
    let params: Record<string, number> = {};
    if (type === 'EMA' || type === 'SMA') {
      params = { period: indicatorParams.period || 20 };
    } else if (type === 'MACD') {
      params = { 
        fast: indicatorParams.fast || 10, 
        slow: indicatorParams.slow || 20, 
        signal: indicatorParams.signal || 5 
      };
    } else if (type === 'RSI') {
      params = { period: indicatorParams.period || 14 };
    }
    
    setIndicators(prev => [...prev, { id, type, params }]);
    setShowIndicatorDialog(false);
    setIndicatorParams({});
  };

  const cancelAddIndicator = () => {
    setShowIndicatorDialog(false);
    setIndicatorParams({});
  };

  // Handle escape key to close dialog
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showIndicatorDialog) {
        cancelAddIndicator();
      }
    };

    if (showIndicatorDialog) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [showIndicatorDialog]);

  const removeIndicator = (id: string) => {
    setIndicators(prev => prev.filter(ind => ind.id !== id));
  };

  const getIndicatorLabel = (ind: IndicatorConfig): string => {
    if (ind.type === 'EMA' || ind.type === 'SMA') {
      return `${ind.type}(${ind.params.period ?? 20})`;
    }
    if (ind.type === 'MACD') {
      const f = ind.params.fast ?? 10;
      const s = ind.params.slow ?? 20;
      const sig = ind.params.signal ?? 5;
      return `MACD(${f},${s},${sig})`;
    }
    if (ind.type === 'RSI') {
      return `RSI(${ind.params.period ?? 14})`;
    }
    return ind.type;
  };

  const panOrZoom = useCallback((action: 'panLeft' | 'panRight' | 'zoomIn' | 'zoomOut') => {
    const chart = (chartRef as any)?.current?.chart as Highcharts.Chart | undefined;
    if (!chart || !chart.xAxis || !chart.xAxis.length) return;
    const axis = chart.xAxis[0];
    const ext = axis.getExtremes();
    const dataMin = ext.dataMin ?? ext.min;
    const dataMax = ext.dataMax ?? ext.max;
    let min = ext.min;
    let max = ext.max;
    const range = Math.max(1, max - min);
    const step = range * 0.2; // 20% pan step
    const zoomStep = range * 0.1; // 10% zoom step
    if (action === 'panLeft') {
      min = Math.max(dataMin, min - step);
      max = min + range;
      if (max > dataMax) { max = dataMax; min = max - range; }
    } else if (action === 'panRight') {
      max = Math.min(dataMax, max + step);
      min = max - range;
      if (min < dataMin) { min = dataMin; max = min + range; }
    } else if (action === 'zoomIn') {
      const center = (min + max) / 2;
      let newRange = Math.max(10, range - zoomStep);
      min = Math.max(dataMin, center - newRange / 2);
      max = Math.min(dataMax, center + newRange / 2);
    } else if (action === 'zoomOut') {
      const center = (min + max) / 2;
      let newRange = Math.min(dataMax - dataMin, range + zoomStep);
      min = Math.max(dataMin, center - newRange / 2);
      max = Math.min(dataMax, center + newRange / 2);
    }
    axis.setExtremes(min, max, true, false);
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); panOrZoom('panLeft'); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); panOrZoom('panRight'); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); panOrZoom('zoomIn'); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); panOrZoom('zoomOut'); }
  }, [panOrZoom]);

  // Non-passive wheel listener to avoid browser warning and enable preventDefault
  const wheelContainerRef = useRef<HTMLDivElement | null>(null);
  const isPanningRef = useRef(false);
  const panStartXRef = useRef(0);
  const panStartMinRef = useRef<number | null>(null);
  const panStartMaxRef = useRef<number | null>(null);
  useEffect(() => {
    const el = wheelContainerRef.current;
    if (!el) return;
    const handler = (ev: WheelEvent) => {
      ev.preventDefault();
      const chart = (chartRef as any)?.current?.chart as Highcharts.Chart | undefined;
      const axis = chart?.xAxis && chart.xAxis[0];
      if (!chart || !axis) {
        // Fallback to zoom if chart not ready
        if (ev.deltaY < 0) panOrZoom('zoomIn'); else panOrZoom('zoomOut');
        return;
      }
      const ext = axis.getExtremes();
      const range = Math.max(1, ext.max - ext.min);
      const isHorizontal = Math.abs(ev.deltaX) > Math.abs(ev.deltaY);
      if (isHorizontal) {
        const plotWidth = chart.plotWidth || 1;
        const deltaVal = -ev.deltaX / plotWidth * range;
        let newMin = ext.min + deltaVal;
        let newMax = ext.max + deltaVal;
        const dataMin = ext.dataMin ?? newMin;
        const dataMax = ext.dataMax ?? newMax;
        if (newMin < dataMin) { newMin = dataMin; newMax = newMin + range; }
        if (newMax > dataMax) { newMax = dataMax; newMin = newMax - range; }
        axis.setExtremes(newMin, newMax, true, false);
      } else {
        if (ev.deltaY < 0) panOrZoom('zoomIn'); else panOrZoom('zoomOut');
      }
    };
    el.addEventListener('wheel', handler, { passive: false });
    return () => {
      el.removeEventListener('wheel', handler as any);
    };
  }, [panOrZoom]);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const chart = (chartRef as any)?.current?.chart as Highcharts.Chart | undefined;
    if (!chart || !chart.xAxis || !chart.xAxis.length) return;
    const axis = chart.xAxis[0];
    const ext = axis.getExtremes();
    isPanningRef.current = true;
    panStartXRef.current = e.clientX;
    panStartMinRef.current = ext.min;
    panStartMaxRef.current = ext.max;
    (e.currentTarget as HTMLDivElement).style.cursor = 'grabbing';
    e.preventDefault();
  }, []);

  const handleMouseUp = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    isPanningRef.current = false;
    (e.currentTarget as HTMLDivElement).style.cursor = 'default';
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!isPanningRef.current) return;
    const chart = (chartRef as any)?.current?.chart as Highcharts.Chart | undefined;
    if (!chart || !chart.xAxis || !chart.xAxis.length) return;
    const axis = chart.xAxis[0];
    const plotWidth = chart.plotWidth || 1;
    const startMin = panStartMinRef.current;
    const startMax = panStartMaxRef.current;
    if (startMin == null || startMax == null) return;
    const range = Math.max(1, startMax - startMin);
    const deltaPx = e.clientX - panStartXRef.current;
    const deltaVal = -deltaPx / plotWidth * range;
    const newMin = startMin + deltaVal;
    const newMax = startMax + deltaVal;
    axis.setExtremes(newMin, newMax, true, false);
    e.preventDefault();
  }, []);

  return (
    <div ref={inViewRef} className="chart-container overflow-hidden card-hover">
      {/* Enhanced Header */}
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-slate-700 bg-gradient-to-br from-slate-800 to-slate-700">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onBlur={fetchBars}
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
            <option value="60m">60m</option>
            <option value="65m">65m</option>
            <option value="1d">1d</option>
            <option value="1wk">1wk</option>
            <option value="1mo">1mo</option>
          </select>
          <button 
            onClick={fetchBars} 
            className="px-2 py-1 text-xs bg-slate-700 border border-slate-600 rounded-lg hover:bg-slate-600 text-slate-300 hover:text-slate-100 transition-all duration-200 flex items-center gap-1.5"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Reload
          </button>
        </div>
        
        <div className="flex items-center gap-2">
          <select
            value={indicatorToAdd}
            onChange={(e) => setIndicatorToAdd(e.target.value as IndicatorType)}
            className="px-2 py-1 text-xs bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100"
          >
            <option value="EMA">EMA</option>
            <option value="SMA">SMA</option>
            <option value="MACD">MACD</option>
            <option value="RSI">RSI</option>
          </select>
          <button 
            onClick={handleAddIndicator} 
            className="btn-primary px-2 py-1 text-xs rounded-lg font-medium flex items-center gap-1.5"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Add
          </button>
          {onRemove && (
            <button 
              onClick={() => onRemove(id)} 
              className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-950/20 rounded-lg transition-all duration-200" 
              title="Remove chart"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Enhanced Active Indicators */}
      {indicators.length > 0 && (
        <div className="px-3 py-2 border-b border-slate-700 bg-slate-700">
          <div className="flex flex-wrap gap-1.5">
            {indicators.map(ind => (
              <span key={ind.id} className="inline-flex items-center gap-1.5 px-2 py-1 text-xs bg-gradient-to-br from-slate-800 to-slate-700 border border-slate-600 rounded-lg text-slate-100">
                <span className="font-medium">{getIndicatorLabel(ind)}</span>
                <button
                  className="ml-1 text-slate-400 hover:text-red-400 transition-colors"
                  onClick={() => removeIndicator(ind.id)}
                  title="Remove indicator"
                >
                  <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Chart Content */}
      <div className="p-3 relative">
        <div
          tabIndex={0}
          onKeyDown={handleKeyDown}
          ref={wheelContainerRef}
          onMouseDown={handleMouseDown}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onMouseMove={handleMouseMove}
          className="outline-none rounded-lg overflow-hidden"
          style={{ cursor: 'grab' }}
        >
          <HighchartsReact highcharts={Highcharts} constructorType="stockChart" options={options} ref={chartRef as any} />
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
      
      {/* Enhanced Indicator Dialog */}
      {showIndicatorDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-gradient-to-br from-slate-800 to-slate-700 border border-slate-700 rounded-xl p-4 w-80 max-w-sm shadow-2xl animate-scale-in">
            <div className="flex items-center space-x-2 mb-4">
              <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-blue-400 rounded-lg flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-100">Add Indicator</h3>
                <p className="text-xs text-slate-400">Configure technical indicators</p>
              </div>
            </div>
            
            {indicatorToAdd === 'EMA' || indicatorToAdd === 'SMA' ? (
              <div className="mb-3">
                <label className="block text-xs font-medium text-slate-100 mb-1">
                  Period
                </label>
                <input
                  type="number"
                  value={indicatorParams.period || 20}
                  onChange={(e) => setIndicatorParams(prev => ({ ...prev, period: Number(e.target.value) }))}
                  className="w-full px-2 py-1.5 text-xs bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100"
                  min="1"
                  max="200"
                />
              </div>
            ) : indicatorToAdd === 'MACD' ? (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-100 mb-1">
                    Fast Period
                  </label>
                  <input
                    type="number"
                    value={indicatorParams.fast || 10}
                    onChange={(e) => setIndicatorParams(prev => ({ ...prev, fast: Number(e.target.value) }))}
                    className="w-full px-2 py-1.5 text-xs bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100"
                    min="1"
                    max="100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-100 mb-1">
                    Slow Period
                  </label>
                  <input
                    type="number"
                    value={indicatorParams.slow || 20}
                    onChange={(e) => setIndicatorParams(prev => ({ ...prev, slow: Number(e.target.value) }))}
                    className="w-full px-2 py-1.5 text-xs bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100"
                    min="1"
                    max="100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-100 mb-1">
                    Signal Period
                  </label>
                  <input
                    type="number"
                    value={indicatorParams.signal || 5}
                    onChange={(e) => setIndicatorParams(prev => ({ ...prev, signal: Number(e.target.value) }))}
                    className="w-full px-2 py-1.5 text-xs bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100"
                    min="1"
                    max="50"
                  />
                </div>
              </div>
            ) : indicatorToAdd === 'RSI' ? (
              <div className="mb-3">
                <label className="block text-xs font-medium text-slate-100 mb-1">
                  Period
                </label>
                <input
                  type="number"
                  value={indicatorParams.period || 14}
                  onChange={(e) => setIndicatorParams(prev => ({ ...prev, period: Number(e.target.value) }))}
                  className="w-full px-2 py-1.5 text-xs bg-slate-700 border border-slate-600 rounded-lg focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 text-slate-100"
                  min="1"
                  max="100"
                />
              </div>
            ) : null}
            
            <div className="flex justify-end space-x-2 mt-4">
              <button
                onClick={cancelAddIndicator}
                className="px-4 py-1.5 text-xs font-medium text-slate-300 bg-slate-700 border border-slate-600 rounded-lg hover:bg-slate-600 hover:text-slate-100 transition-all duration-200"
              >
                Cancel
              </button>
              <button
                onClick={confirmAddIndicator}
                className="btn-primary px-4 py-1.5 text-xs font-medium rounded-lg"
              >
                Add Indicator
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChartTile;


