import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import Highcharts from "highcharts/highstock";
import HighchartsReact from "highcharts-react-official";
import LoadingSpinner from "./LoadingSpinner";
import ErrorMessage from "./ErrorMessage";

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
  autoRefresh?: boolean; // Auto refresh data every 5 minutes
  refreshInterval?: number; // Refresh interval in milliseconds
}

const PEMarketChart: React.FC<PEMarketChartProps> = ({
  indexId,
  displayName,
  color = "#2E86AB",
  autoRefresh = false,
  refreshInterval = 5 * 60 * 1000, // 5 minutes
}) => {
  const [peData, setPeData] = useState<PEData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nYears, setNYears] = useState<number>(10); // N-year window
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [showPercentageLines, setShowPercentageLines] = useState(false);
  const [showStdDevLines, setShowStdDevLines] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [currentViewRange, setCurrentViewRange] = useState<{min: number | undefined, max: number | undefined}>({min: undefined, max: undefined});
  const chartRef = useRef<HighchartsReact.RefObject>(null);

  // Memoized fetch function
  const fetchPEData = useCallback(async (index: string): Promise<PEData> => {
    const response = await fetch(`/api/market_pe?index=${index}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch ${index} PE data: ${response.status}`);
    }
    return response.json();
  }, []);

  // Memoized data loading function
  const loadData = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      setIsRefreshing(true);
      setError(null);
      const data = await fetchPEData(indexId);
      setPeData(data);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load PE data");
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [fetchPEData, indexId]);

  // Initial data load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto refresh effect
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      loadData(false); // Don't show loading state for auto-refresh
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, loadData]);

  // Memoized rolling stats calculation for performance
  const rollingStats = useMemo(() => {
    if (!peData || !peData.data.length) {
      return { 
        avg: [], 
        plus2: [], 
        minus2: [], 
        pctLinesAbove: [], 
        pctLinesBelow: [], 
        pctPercents: [] 
      };
    }

    const msPerYear = 365.25 * 24 * 3600 * 1000;
    const resultAvg: [number, number | null][] = [];
    const resultPlus2: [number, number | null][] = [];
    const resultMinus2: [number, number | null][] = [];
    
    // For percentage lines: array of arrays, one for each pct
    const pctPercents = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6];
    const pctLinesAbove: [number, number | null][][] = pctPercents.map(() => []);
    const pctLinesBelow: [number, number | null][][] = pctPercents.map(() => []);

    // Optimized rolling window calculation
    for (let i = 0; i < peData.data.length; ++i) {
      const [ts, v] = peData.data[i];
      const cutoff = ts - nYears * msPerYear;
      
      // Use binary search to find the start of the window
      let startIdx = 0;
      let endIdx = i;
      while (startIdx < endIdx) {
        const mid = Math.floor((startIdx + endIdx) / 2);
        if (peData.data[mid][0] >= cutoff) {
          endIdx = mid;
        } else {
          startIdx = mid + 1;
        }
      }
      
      const window = peData.data.slice(startIdx, i + 1).map(([_, val]) => val);
      
      if (window.length > 1) {
        const avg = window.reduce((a, b) => a + b, 0) / window.length;
        const variance = window.reduce((sum, x) => sum + (x - avg) ** 2, 0) / window.length;
        const std = Math.sqrt(variance);
        
        resultAvg.push([ts, avg]);
        resultPlus2.push([ts, avg + 2 * std]);
        resultMinus2.push([ts, avg - 2 * std]);
        
        pctPercents.forEach((pct, idx) => {
          pctLinesAbove[idx].push([ts, avg * (1 + pct)]);
          pctLinesBelow[idx].push([ts, avg * (1 - pct)]);
        });
      } else {
        resultAvg.push([ts, null]);
        resultPlus2.push([ts, null]);
        resultMinus2.push([ts, null]);
        pctPercents.forEach((_, idx) => {
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
      pctPercents,
    };
  }, [peData, nYears]);

  // Memoized chart configuration
  const chartConfig = useMemo(() => {
    const pctColors = [
      "#1abc9c", "#3498db", "#9b59b6", "#e67e22", "#e74c3c", "#34495e",
    ];
    const pctDashStyles = [
      "ShortDash", "ShortDot", "ShortDashDot", "Dash", "Dot", "DashDot",
    ];

    const pctPercents = rollingStats.pctPercents || [];
    const pctLinesAbove = rollingStats.pctLinesAbove || [];
    const pctLinesBelow = rollingStats.pctLinesBelow || [];

    // Find the two percentage lines closest to the current value
    let visiblePctIdxs: number[] = [];
    if (peData && peData.data.length && pctPercents.length) {
      const lastIdx = peData.data.length - 1;
      const currentPE = peData.data[lastIdx][1];
      const avgAtLast = rollingStats.avg[lastIdx]?.[1];
      
      if (avgAtLast !== null && avgAtLast !== undefined) {
        const aboveVals = pctLinesAbove.map((line) => line[lastIdx]?.[1]);
        const belowVals = pctLinesBelow.map((line) => line[lastIdx]?.[1]);
        
        const allLines = [
          ...aboveVals.map((val, idx) => ({ idx, val, type: "above" })),
          ...belowVals.map((val, idx) => ({ idx, val, type: "below" })),
        ].filter((x) => x.val !== null && x.val !== undefined);
        
        allLines.sort(
          (a, b) =>
            Math.abs((a.val ?? 0) - currentPE) -
            Math.abs((b.val ?? 0) - currentPE)
        );
        
        visiblePctIdxs = allLines
          .slice(0, 2)
          .map((x) => (x.type === "above" ? x.idx : x.idx + pctPercents.length));
      }
    }

    // Calculate default xAxis min and max for last 5 years
    let xAxisMin: number | undefined = undefined;
    let xAxisMax: number | undefined = undefined;
    if (peData && peData.data.length) {
      xAxisMax = peData.data[peData.data.length - 1][0];
      const ms5y = 5 * 365.25 * 24 * 3600 * 1000;
      xAxisMin = xAxisMax - ms5y;
      if (xAxisMin < peData.data[0][0]) xAxisMin = peData.data[0][0];
    }

    return {
      pctColors,
      pctDashStyles,
      pctPercents,
      pctLinesAbove,
      pctLinesBelow,
      visiblePctIdxs,
      xAxisMin,
      xAxisMax,
    };
  }, [peData, rollingStats]);

  // Memoized chart options
  const chartOptions = useMemo(() => {
    const {
      pctColors,
      pctDashStyles,
      pctPercents,
      pctLinesAbove,
      pctLinesBelow,
      visiblePctIdxs,
      xAxisMin,
      xAxisMax,
    } = chartConfig;

    const series: Highcharts.SeriesOptionsType[] = [
      {
        name: displayName,
        data: peData?.data || [],
        color: color,
        type: "line",
        zIndex: 3,
        marker: {
          enabled: false,
          states: {
            hover: { enabled: true, radius: 4 }
          }
        },
      },
    ];

    // Add rolling average
    series.push({
      name: `${nYears}Y Avg`,
      data: rollingStats.avg,
      color: "#888",
               dashStyle: "Dash" as const,
      type: "line",
      zIndex: 2,
      marker: { enabled: false },
    });

    // Add standard deviation lines
    if (showStdDevLines) {
      series.push(
        {
          name: `+2 Std`,
          data: rollingStats.plus2,
          color: "#b8860b",
          dashStyle: "Dot" as const,
          type: "line",
          zIndex: 1,
          marker: { enabled: false },
        },
        {
          name: `-2 Std`,
          data: rollingStats.minus2,
          color: "#b8860b",
          dashStyle: "Dot" as const,
          type: "line",
          zIndex: 1,
          marker: { enabled: false },
        }
      );
    }

    // Add percentage lines if enabled
    if (showPercentageLines) {
      // Add percentage lines above
      pctPercents.forEach((pct, idx) => {
        series.push({
          name: `+${Math.round(pct * 100)}% Avg`,
          data: pctLinesAbove[idx],
          color: pctColors[idx],
          dashStyle: pctDashStyles[idx],
          type: "line",
          zIndex: 0,
          visible: visiblePctIdxs.includes(idx),
          marker: { enabled: false },
        });
      });

      // Add percentage lines below
      pctPercents.forEach((pct, idx) => {
        series.push({
          name: `-${Math.round(pct * 100)}% Avg`,
          data: pctLinesBelow[idx],
          color: pctColors[idx],
          dashStyle: pctDashStyles[idx],
          type: "line",
          zIndex: 0,
          visible: visiblePctIdxs.includes(idx + pctPercents.length),
          marker: { enabled: false },
        });
      });
    }

    return {
      chart: {
        type: "line",
        height: 500,
        backgroundColor: "transparent",
        zoomType: "x",
        panning: {
          enabled: true,
          type: "x",
        },
        style: {
          fontFamily: "inherit",
        },
        events: {
          load: function() {
            // Chart loaded successfully
          }
        }
      },
      title: {
        text: "",
      },
      subtitle: {
        text: "",
      },
      xAxis: {
        type: "datetime",
        title: {
          text: "Date",
          style: { fontSize: "14px", fontWeight: "600" },
        },
        labels: {
          format: "{value:%Y-%m-%d}",
          style: { fontSize: "12px" },
        },
        min: xAxisMin,
        max: xAxisMax,
        gridLineWidth: 1,
        gridLineColor: "#f0f0f0",
        crosshair: {
          color: '#666',
          width: 1,
          dashStyle: 'shortdot'
        }
      },
      yAxis: {
        title: {
          text: "PE Ratio",
          style: { fontSize: "14px", fontWeight: "600" },
        },
        labels: {
          format: "{value:.1f}",
          style: { fontSize: "12px" },
        },
        gridLineWidth: 1,
        gridLineColor: "#f0f0f0",
        crosshair: {
          color: '#666',
          width: 1,
          dashStyle: 'shortdot'
        }
      },
      tooltip: {
        shared: true,
        backgroundColor: "rgba(255, 255, 255, 0.95)",
        borderWidth: 0,
        shadow: true,
        style: { fontSize: "13px" },
        formatter: function () {
          const date = Highcharts.dateFormat("%Y-%m-%d", this.x);
          let tooltip = `<b>${date}</b><br/>`;
          this.points?.forEach((point) => {
            tooltip += `<span style="color:${point.color}">●</span> ${
              point.series.name
            }: <b>${point.y?.toFixed(2)}</b><br/>`;
          });
          return tooltip;
        },
      },
      legend: {
        enabled: true,
        align: "center",
        verticalAlign: "bottom",
        layout: "horizontal",
        itemStyle: { fontSize: "12px" },
        symbolHeight: 8,
        symbolWidth: 18,
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
      navigator: {
        enabled: true,
        height: 40,
        margin: 10,
      },
      scrollbar: {
        enabled: true,
      },
      rangeSelector: {
        enabled: true,
        selected: 2, // 5y button
        inputEnabled: false,
        buttons: [
          { type: "year", count: 1, text: "1y" },
          { type: "year", count: 3, text: "3y" },
          { type: "year", count: 5, text: "5y" },
          { type: "all", text: "All" },
        ],
      },
      series,
      credits: {
        enabled: false,
      },
      exporting: {
        enabled: true,
        buttons: {
          contextButton: {
            menuItems: ['downloadPNG', 'downloadPDF', 'downloadCSV']
          }
        }
      }
    } as unknown as Highcharts.Options;
  }, [
    peData,
    displayName,
    color,
    nYears,
    rollingStats,
    showStdDevLines,
    showPercentageLines,
    chartConfig,
    indexId,
  ]);

  // Handle manual refresh
  const handleRefresh = useCallback(() => {
    loadData(false);
  }, [loadData]);

  // Handle N-year change
  const handleNYearsChange = useCallback((value: number) => {
    setNYears(Math.max(1, Math.min(100, value)));
  }, []);

  // Chart callback to handle zoom events
  const chartCallback = useCallback((chart: Highcharts.Chart) => {
    if (chart && chart.xAxis && chart.xAxis[0]) {
      // Set initial range
      setCurrentViewRange({
        min: chart.xAxis[0].min,
        max: chart.xAxis[0].max
      });

      // Add event listener for zoom/pan
      chart.xAxis[0].update({
        events: {
          afterSetExtremes: function(e: any) {
            setCurrentViewRange({
              min: e.target.min,
              max: e.target.max
            });
          }
        }
      });
    }
  }, []);

  if (loading) {
    return (
      <div className="chart-container">
        <LoadingSpinner text="Loading PE data..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="chart-container">
        <ErrorMessage message={`Error: ${error}`} />
        <div className="mt-4 text-center">
          <button 
            onClick={handleRefresh}
            className="btn-primary"
            disabled={isRefreshing}
          >
            {isRefreshing ? 'Refreshing...' : 'Retry'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="chart-container">
      <div className="chart-header">
        <div className="flex items-center justify-between">
          <h2 className="chart-title" style={{ color }}>
            {displayName}
          </h2>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            {lastUpdated && (
              <span>Last updated: {lastUpdated.toLocaleTimeString()}</span>
            )}
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="btn-secondary text-xs"
              title="Refresh data"
            >
              {isRefreshing ? (
                <div className="loading-spinner w-4 h-4" />
              ) : (
                '↻'
              )}
            </button>
          </div>
        </div>
        
        <div className="chart-controls">
          <div className="flex items-center gap-6 flex-wrap">
            <label className="flex items-center gap-2 text-sm font-medium">
              N-year:
              <input
                type="number"
                min={1}
                max={100}
                value={nYears}
                onChange={(e) => handleNYearsChange(Number(e.target.value))}
                className="input-field w-16 text-center"
                aria-label="N-year window"
              />
            </label>
            
            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={showStdDevLines}
                onChange={(e) => setShowStdDevLines(e.target.checked)}
                className="rounded"
              />
              Std Dev Lines
            </label>
            
            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={showPercentageLines}
                onChange={(e) => setShowPercentageLines(e.target.checked)}
                className="rounded"
              />
              Percentage Lines
            </label>
          </div>
        </div>
      </div>
      
      {peData && (
        <div className="chart-stats">
          <table className="w-full text-center">
            <thead>
              <tr className="text-xs text-gray-600 font-medium">
                <th className="pb-1">Current PE</th>
                <th className="pb-1">{nYears}-Year Avg</th>
                <th className="pb-1">Range</th>
                <th className="pb-1">vs {nYears}Y Avg</th>
              </tr>
            </thead>
            <tbody>
              <tr className="text-lg font-bold text-gray-900">
                <td>{peData.stats.current_pe.toFixed(2)}</td>
                <td>
                  {rollingStats.avg.length > 0 && rollingStats.avg[rollingStats.avg.length - 1]?.[1] 
                    ? rollingStats.avg[rollingStats.avg.length - 1][1]?.toFixed(2)
                    : peData.stats.avg_20y.toFixed(2)
                  }
                </td>
                <td className="text-sm">
                  {(() => {
                    // Calculate range from current view range
                    const visibleData = peData.data.filter(([timestamp]) => {
                      if (!currentViewRange.min || !currentViewRange.max) return true;
                      return timestamp >= currentViewRange.min && timestamp <= currentViewRange.max;
                    });
                    
                    if (visibleData.length > 0) {
                      const values = visibleData.map(([_, value]) => value);
                      const min = Math.min(...values);
                      const max = Math.max(...values);
                      return `${min.toFixed(2)} - ${max.toFixed(2)}`;
                    }
                    
                    // Fallback to full dataset range
                    return `${peData.stats.min_pe.toFixed(2)} - ${peData.stats.max_pe.toFixed(2)}`;
                  })()}
                </td>
                <td className={
                  peData.stats.current_pe > (rollingStats.avg.length > 0 && rollingStats.avg[rollingStats.avg.length - 1]?.[1] || peData.stats.avg_20y) ? 'text-red-600' : 'text-green-600'
                }>
                  {((peData.stats.current_pe / (rollingStats.avg.length > 0 && rollingStats.avg[rollingStats.avg.length - 1]?.[1] || peData.stats.avg_20y) - 1) * 100).toFixed(1)}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
      
      <div className="mt-6">
        <HighchartsReact
          highcharts={Highcharts}
          options={chartOptions}
          callback={chartCallback}
        />
      </div>
    </div>
  );
};

export default PEMarketChart;
