import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Highcharts from 'highcharts/highstock';
import HighchartsReact from 'highcharts-react-official';
import { apiConfig } from '../config/environment';
import { useInView } from 'react-intersection-observer';
import { wsClient, type QuotePayload, type BarsPayload } from '../utils/wsClient';

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
    try {
      if (barsAbortRef.current) {
        barsAbortRef.current.abort();
      }
      const controller = new AbortController();
      barsAbortRef.current = controller;
      let url: string;
      const params = new URLSearchParams({ period: 'max' }).toString();
      url = apiConfig.getApiUrl(`/api/bars/${ticker}/${timeframe}?${params}`);
      const res = await fetch(url, { signal: controller.signal });
      const data = await res.json();
      const raw: Bar[] = data?.bars || [];
      // Keep original UTC timestamps, we'll format as NY time in display
      setBars(raw);
      setErrorMsg(null);
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

  useEffect(() => {
    if (!inView) return;
    fetchBars();
  }, [ticker, timeframe, inView]);

  // Reset default zoom flag when ticker or timeframe changes
  useEffect(() => {
    defaultZoomAppliedRef.current = false;
  }, [ticker, timeframe]);

  useEffect(() => {
    if (!inView) return;
    const unsubscribeQuote = subscribeQuote();
    const start = async () => {
      await fetchBars();
    };
    start();
    // subscribe to live bars over WS
    const unsubscribeBars = wsClient.subscribeBars(ticker, timeframe, (payload: BarsPayload) => {
      console.log('ChartTile received bars payload:', payload);
      if (!payload?.bars?.length) {
        console.log('No bars in payload or empty bars array');
        return;
      }
      
      console.log('Processing bars update:', {
        is_snapshot: payload.is_snapshot,
        bars_count: payload.bars.length,
        first_bar: payload.bars[0],
        last_bar: payload.bars[payload.bars.length - 1]
      });
      
      setBars(prev => {
        console.log('Current bars state:', prev.length, 'bars');
        
        // Handle initial snapshot
        if (payload.is_snapshot) {
          console.log('Handling snapshot - replacing all bars');
          return payload.bars; // Keep original UTC timestamps
        }
        
        // Handle incremental updates
        if (!prev.length) {
          console.log('No previous bars, using incoming bars');
          return payload.bars; // Keep original UTC timestamps
        }
        
        const lastTs = prev[prev.length - 1].timestamp;
        const incoming = payload.bars; // Keep original UTC timestamps
        
        console.log('Incremental update:', {
          lastTs,
          incomingTs: incoming[incoming.length - 1].timestamp,
          timeframe
        });
        
        // For minute bars, we might get updates to the last forming bar
        if (timeframe.includes('m')) {
          const lastIncomingTs = incoming[incoming.length - 1].timestamp;
          if (lastIncomingTs === lastTs) {
            // Replace the last forming bar
            console.log('Replacing last forming bar');
            const newBars = [...prev.slice(0, prev.length - 1), incoming[incoming.length - 1]];
            console.log('New bars after replacement:', newBars.length);
            return newBars;
          } else if (lastIncomingTs > lastTs) {
            // New bar completed, append it
            console.log('Appending new completed bar');
            return [...prev, incoming[incoming.length - 1]];
          } else {
            console.log('Incoming timestamp is older than current, skipping');
          }
        } else {
          // For daily/weekly bars, just append new ones
          const updates: Bar[] = [];
          for (const b of incoming) {
            if (b.timestamp > lastTs) {
              updates.push(b);
            }
          }
          if (updates.length > 0) {
            console.log('Appending new daily/weekly bars:', updates.length);
            return [...prev, ...updates];
          }
        }
        
        console.log('No bars to update');
        return prev;
      });
    });
    return () => {
      if (barsAbortRef.current) barsAbortRef.current.abort();
      unsubscribeQuote();
      unsubscribeBars();
    };
  }, [ticker, timeframe, inView, subscribeQuote]);

  // Monitor bars state changes for debugging
  useEffect(() => {
    console.log('Bars state changed:', bars.length, 'bars');
    if (bars.length > 0) {
      console.log('Latest bar:', bars[bars.length - 1]);
    }
    
    // Trigger chart update when bars change
    const chart = (chartRef as any)?.current?.chart as Highcharts.Chart | undefined;
    if (chart && bars.length > 0) {
      console.log('Triggering chart update');
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
    console.log('Computing OHLC data from', bars.length, 'bars');
    return bars.map(b => [b.timestamp, b.open, b.high, b.low, b.close] as [number, number, number, number, number]);
  }, [bars]);
  
  const volumes = useMemo(() => {
    console.log('Computing volumes data from', bars.length, 'bars');
    return bars.map(b => [b.timestamp, b.volume] as [number, number]);
  }, [bars]);
  
  const closes = useMemo(() => {
    console.log('Computing closes data from', bars.length, 'bars');
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
    chart: { height: 360, backgroundColor: 'transparent', spacingTop: 0, marginTop: 0, spacing: [0, 0, 0, 0] },
    xAxis: { 
      ordinal: true,
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
      }
    },
    plotOptions: {
      series: {
        dataGrouping: { enabled: false },
        lineWidth: 1, // Make indicator lines thinner
      },
      candlestick: {
        dataGrouping: { enabled: false },
        // Reduce spacing between bars to half of defaults
        pointPadding: 0.05,
        groupPadding: 0.1,
      },
      column: {
        dataGrouping: { enabled: false },
        pointPadding: 0.05,
        groupPadding: 0.1,
      },
      line: {
        dataGrouping: { enabled: false },
        lineWidth: 1, // Ensure line indicators are thin
      },
    },
        tooltip: { 
          split: false, // Share tooltip across all series
          shared: true, // Enable shared tooltip
          useHTML: true, // Enable HTML in tooltip
          valueDecimals: 2,
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
            
            let tooltip = `<b>${ticker}: ${nyTime}</b><br/>`;
            
            // Debug: Log what we're working with
            console.log('Tooltip formatter called with:', {
              points: this.points,
              pointsLength: this.points?.length,
              x: this.x
            });
            
            // Group data by series type
            if (this.points && this.points.length > 0) {
              // Find OHLC data first - look for candlestick series by type or name
              const ohlcPoint = this.points.find((point: any) => 
                point.series?.type === 'candlestick' || 
                point.series?.name === ticker ||
                (point.series?.options && point.series.options.type === 'candlestick')
              );
              console.log('Looking for OHLC point, found:', ohlcPoint);
              console.log('All points:', this.points.map((p: any) => ({ 
                id: p.series?.id, 
                name: p.series?.name, 
                type: p.series?.type,
                optionsType: p.series?.options?.type 
              })));
              if (ohlcPoint) {
                tooltip += `<b>OHLC:</b><br/>`;
                // Access OHLC data from the point's options for candlestick series
                const pointOptions = (ohlcPoint as any).options;
                if (pointOptions) {
                  tooltip += `&nbsp;&nbsp;O: <b>${pointOptions.open?.toFixed(2) || 'N/A'}</b><br/>`;
                  tooltip += `&nbsp;&nbsp;H: <b>${pointOptions.high?.toFixed(2) || 'N/A'}</b><br/>`;
                  tooltip += `&nbsp;&nbsp;L: <b>${pointOptions.low?.toFixed(2) || 'N/A'}</b><br/>`;
                  tooltip += `&nbsp;&nbsp;C: <b>${pointOptions.close?.toFixed(2) || 'N/A'}</b><br/>`;
                }
              }
              
              // Find Volume data - look for column series by type or name
              const volumePoint = this.points.find((point: any) => 
                point.series?.type === 'column' || 
                point.series?.name === 'Volume' ||
                (point.series?.options && point.series.options.type === 'column')
              );
              if (volumePoint && volumePoint.y !== null && volumePoint.y !== undefined) {
                tooltip += `<b>Volume:</b><br/>`;
                tooltip += `&nbsp;&nbsp;V: <b>${Highcharts.numberFormat(volumePoint.y, 0)}</b><br/>`;
              }
              
              // Group indicators by type - exclude candlestick and volume, but allow indicator columns
              const indicatorPoints = this.points.filter((point: any) => 
                point.series?.type !== 'candlestick' && 
                point.series?.name !== ticker &&
                point.series?.name !== 'Volume'
              );
              
              if (indicatorPoints.length > 0) {
                console.log('Indicator points found:', indicatorPoints.map(p => ({ 
                  name: p.series?.name, 
                  type: p.series?.type,
                  y: p.y 
                })));
                
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
                
                console.log('Indicator groups:', indicatorGroups);
                
                // Add each indicator group
                Object.entries(indicatorGroups).forEach(([groupName, points]) => {
                  tooltip += `<b>${groupName}:</b><br/>`;
                  
                  points.forEach((point: any) => {
                    const value = point.y !== null ? point.y.toFixed(2) : 'N/A';
                    let label = '';
                    
                    // Customize labels for different indicator types
                    if (groupName === 'MACD') {
                      // For MACD, use the series name to determine the component
                      if (point.series?.name) {
                        if (point.series.name.includes('MACD')) {
                          label = 'MACD';
                        } else if (point.series.name.includes('Signal')) {
                          label = 'Signal';
                        } else if (point.series.name.includes('Hist')) {
                          label = 'Hist';
                        } else {
                          label = 'Value';
                        }
                      }
                    } else if (groupName === 'EMA' || groupName === 'SMA') {
                      // For EMA/SMA, show the period
                      const period = point.series?.name?.match(/\((\d+)\)/)?.[1] || '';
                      label = period ? `${groupName}(${period})` : groupName;
                    } else if (groupName === 'RSI') {
                      // For RSI, show the period
                      const period = point.series?.name?.match(/\((\d+)\)/)?.[1] || '';
                      label = period ? `RSI(${period})` : 'RSI';
                    } else {
                      label = 'Value';
                    }
                    
                    tooltip += `&nbsp;&nbsp;${label}: <b>${value}</b><br/>`;
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

  const handleDialogBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      cancelAddIndicator();
    }
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
    <div ref={inViewRef} className="bg-white border border-gray-200 rounded-md shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 px-2 py-1 border-b border-gray-200">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          onBlur={fetchBars}
          className="w-24 px-2 py-1 text-xs border border-gray-300 rounded"
        />
        <select
          value={timeframe}
          onChange={(e) => setTimeframe(e.target.value)}
          className="px-2 py-1 text-xs border border-gray-300 rounded"
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
        <button onClick={fetchBars} className="px-2 py-1 text-xs bg-gray-100 rounded border border-gray-300">Reload</button>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={indicatorToAdd}
            onChange={(e) => setIndicatorToAdd(e.target.value as IndicatorType)}
            className="px-2 py-1 text-xs border border-gray-300 rounded"
          >
            <option value="EMA">EMA</option>
            <option value="SMA">SMA</option>
            <option value="MACD">MACD</option>
            <option value="RSI">RSI</option>
          </select>
          <button onClick={handleAddIndicator} className="px-2 py-1 text-xs bg-blue-600 text-white rounded">Add Indicator</button>
          {onRemove && (
            <button onClick={() => onRemove(id)} className="p-1 text-gray-500 hover:text-red-600" title="Remove chart">✕</button>
          )}
        </div>
      </div>
      {/* Active indicators */}
      {indicators.length > 0 && (
        <div className="px-2 pb-1 border-b border-gray-200">
          <div className="flex flex-wrap gap-1">
            {indicators.map(ind => (
              <span key={ind.id} className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] bg-gray-100 rounded border border-gray-300">
                {getIndicatorLabel(ind)}
                <button
                  className="text-gray-500 hover:text-red-600"
                  onClick={() => removeIndicator(ind.id)}
                  title="Remove indicator"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="p-1">
        {loading && <div className="text-xs text-gray-500 px-2 py-2">Loading...</div>}
        {errorMsg && <div className="text-xs text-red-600 px-2 py-2">{errorMsg}</div>}
        <div
          tabIndex={0}
          onKeyDown={handleKeyDown}
          ref={wheelContainerRef}
          onMouseDown={handleMouseDown}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onMouseMove={handleMouseMove}
          className="outline-none"
          style={{ cursor: 'grab' }}
        >
          <HighchartsReact highcharts={Highcharts} constructorType="stockChart" options={options} ref={chartRef as any} />
        </div>
      </div>
      
      {/* Indicator Dialog */}
      {showIndicatorDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={handleDialogBackdropClick}>
          <div className="bg-white rounded-lg p-6 w-80 max-w-sm">
            <h3 className="text-lg font-semibold mb-4">Add {indicatorToAdd} Indicator</h3>
            
            {indicatorToAdd === 'EMA' || indicatorToAdd === 'SMA' ? (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Period
                </label>
                <input
                  type="number"
                  value={indicatorParams.period || 20}
                  onChange={(e) => setIndicatorParams(prev => ({ ...prev, period: Number(e.target.value) }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  min="1"
                  max="200"
                />
              </div>
            ) : indicatorToAdd === 'MACD' ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Fast Period
                  </label>
                  <input
                    type="number"
                    value={indicatorParams.fast || 10}
                    onChange={(e) => setIndicatorParams(prev => ({ ...prev, fast: Number(e.target.value) }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="1"
                    max="100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Slow Period
                  </label>
                  <input
                    type="number"
                    value={indicatorParams.slow || 20}
                    onChange={(e) => setIndicatorParams(prev => ({ ...prev, slow: Number(e.target.value) }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="1"
                    max="100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Signal Period
                  </label>
                  <input
                    type="number"
                    value={indicatorParams.signal || 5}
                    onChange={(e) => setIndicatorParams(prev => ({ ...prev, signal: Number(e.target.value) }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="1"
                    max="50"
                  />
                </div>
              </div>
            ) : indicatorToAdd === 'RSI' ? (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Period
                </label>
                <input
                  type="number"
                  value={indicatorParams.period || 14}
                  onChange={(e) => setIndicatorParams(prev => ({ ...prev, period: Number(e.target.value) }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  min="1"
                  max="100"
                />
              </div>
            ) : null}
            
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={cancelAddIndicator}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500"
              >
                Cancel
              </button>
              <button
                onClick={confirmAddIndicator}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
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


