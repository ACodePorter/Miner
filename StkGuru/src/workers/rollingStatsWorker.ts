// Web Worker for heavy rolling stats calculations
// This moves the O(n²) calculations off the main thread

interface WorkerMessage {
  type: 'CALCULATE_ROLLING_STATS';
  data: {
    peData: [number, number][];
    nYears: number;
  };
}

interface WorkerResponse {
  type: 'ROLLING_STATS_RESULT';
  data: {
    avg: [number, number | null][];
    plus2: [number, number | null][];
    minus2: [number, number | null][];
    pctLinesAbove: [number, number | null][][];
    pctLinesBelow: [number, number | null][][];
    pctPercents: number[];
  };
}

const PCT_PERCENTS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6];

function calculateRollingStats(peData: [number, number][], nYears: number) {
  if (!peData || !peData.length) {
    return { 
      avg: [], 
      plus2: [], 
      minus2: [], 
      pctLinesAbove: [], 
      pctLinesBelow: [], 
      pctPercents: PCT_PERCENTS 
    };
  }

  const msPerYear = 365.25 * 24 * 3600 * 1000;
  const resultAvg: [number, number | null][] = [];
  const resultPlus2: [number, number | null][] = [];
  const resultMinus2: [number, number | null][] = [];
  
  // For percentage lines: array of arrays, one for each pct
  const pctLinesAbove: [number, number | null][][] = PCT_PERCENTS.map(() => []);
  const pctLinesBelow: [number, number | null][][] = PCT_PERCENTS.map(() => []);

  // Optimized rolling window calculation
  for (let i = 0; i < peData.length; ++i) {
    const [ts] = peData[i];
    const cutoff = ts - nYears * msPerYear;
    
    // Use binary search to find the start of the window
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
}

// Worker message handler
self.addEventListener('message', (event: MessageEvent<WorkerMessage>) => {
  if (event.data.type === 'CALCULATE_ROLLING_STATS') {
    const { peData, nYears } = event.data.data;
    
    try {
      const result = calculateRollingStats(peData, nYears);
      
      const response: WorkerResponse = {
        type: 'ROLLING_STATS_RESULT',
        data: result
      };
      
      self.postMessage(response);
    } catch (error) {
      self.postMessage({
        type: 'ERROR',
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  }
});

// TypeScript worker context
export type { WorkerMessage, WorkerResponse }; 