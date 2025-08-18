import { useState, useEffect, useRef, useCallback } from 'react';

interface RollingStatsResult {
  avg: [number, number | null][];
  plus2: [number, number | null][];
  minus2: [number, number | null][];
  pctLinesAbove: [number, number | null][][];
  pctLinesBelow: [number, number | null][][];
  pctPercents: number[];
}

interface UseRollingStatsWorkerReturn {
  rollingStats: RollingStatsResult | null;
  isLoading: boolean;
  error: string | null;
  calculateStats: (peData: [number, number][], nYears: number) => void;
}

export const useRollingStatsWorker = (): UseRollingStatsWorkerReturn => {
  const [rollingStats, setRollingStats] = useState<RollingStatsResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const workerRef = useRef<Worker | null>(null);

  // Initialize worker
  useEffect(() => {
    if (typeof Window !== 'undefined' && 'Worker' in window) {
      try {
        workerRef.current = new Worker(
          new URL('../workers/rollingStatsWorker.ts', import.meta.url),
          { type: 'module' }
        );

        workerRef.current.onmessage = (event) => {
          if (event.data.type === 'ROLLING_STATS_RESULT') {
            setRollingStats(event.data.data);
            setIsLoading(false);
            setError(null);
          } else if (event.data.type === 'ERROR') {
            setError(event.data.error);
            setIsLoading(false);
          }
        };

        workerRef.current.onerror = (event) => {
          setError(`Worker error: ${event.message}`);
          setIsLoading(false);
        };
      } catch (err) {
        setError('Worker not available, using main thread');
      }
    }

    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
        workerRef.current = null;
      }
    };
  }, []);

  // Fallback calculation function for when worker is not available
  const calculateRollingStatsFallback = useCallback((peData: [number, number][], nYears: number): RollingStatsResult => {
    if (!peData || !peData.length) {
      return { 
        avg: [], 
        plus2: [], 
        minus2: [], 
        pctLinesAbove: [], 
        pctLinesBelow: [], 
        pctPercents: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6] 
      };
    }

    const PCT_PERCENTS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6];
    const msPerYear = 365.25 * 24 * 3600 * 1000;
    const resultAvg: [number, number | null][] = [];
    const resultPlus2: [number, number | null][] = [];
    const resultMinus2: [number, number | null][] = [];
    
    const pctLinesAbove: [number, number | null][][] = PCT_PERCENTS.map(() => []);
    const pctLinesBelow: [number, number | null][][] = PCT_PERCENTS.map(() => []);

    for (let i = 0; i < peData.length; ++i) {
      const [ts] = peData[i];
      const cutoff = ts - nYears * msPerYear;
      
      let startIdx = 0;
      let endIdx = i;
      while (startIdx < endIdx) {
        const mid = Math.floor((startIdx + endIdx) / 2);
        if (peData[mid][0] >= cutoff) {
          endIdx = mid;
        } else {
          startIdx = mid + 1;
        }
      }
      
      const window = peData.slice(startIdx, i + 1).map(([_, val]) => val);
      
      if (window.length > 1) {
        const avg = window.reduce((a, b) => a + b, 0) / window.length;
        const variance = window.reduce((sum, x) => sum + (x - avg) ** 2, 0) / window.length;
        const std = Math.sqrt(variance);
        
        resultAvg.push([ts, avg]);
        resultPlus2.push([ts, avg + 2 * std]);
        resultMinus2.push([ts, avg - 2 * std]);
        
        PCT_PERCENTS.forEach((pct, idx) => {
          pctLinesAbove[idx].push([ts, avg * (1 + pct)]);
          pctLinesBelow[idx].push([ts, avg * (1 - pct)]);
        });
      } else {
        resultAvg.push([ts, null]);
        resultPlus2.push([ts, null]);
        resultMinus2.push([ts, null]);
        PCT_PERCENTS.forEach((_, idx) => {
          pctLinesAbove[idx].push([ts, null]);
          pctLinesBelow[idx].push([ts, null]);
        });
      }
    }

    return {
      avg: resultAvg,
      plus2: resultPlus2,
      minus2: resultMinus2,
      pctLinesAbove,
      pctLinesBelow,
      pctPercents: PCT_PERCENTS,
    };
  }, []);

  const calculateStats = useCallback((peData: [number, number][], nYears: number) => {
    setIsLoading(true);
    setError(null);

    if (workerRef.current) {
      // Use worker
      workerRef.current.postMessage({
        type: 'CALCULATE_ROLLING_STATS',
        data: { peData, nYears }
      });
    } else {
      // Fallback to main thread
      try {
        const result = calculateRollingStatsFallback(peData, nYears);
        setRollingStats(result);
        setIsLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Calculation failed');
        setIsLoading(false);
      }
    }
  }, [calculateRollingStatsFallback]);

  return {
    rollingStats,
    isLoading,
    error,
    calculateStats
  };
}; 