import React, { useState, useEffect, useMemo, useCallback } from "react";
import Highcharts from "highcharts/highstock";
import HighchartsReact from "highcharts-react-official";
import LoadingSpinner from "./LoadingSpinner";
import ErrorMessage from "./ErrorMessage";
import { useRollingStatsWorker } from "../hooks/useRollingStatsWorker";
import { dataApi } from '../utils/api';

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

interface MarketPeChartProps {
  indexId: string; // e.g., 'spx', 'qqq', etc.
  displayName: string; // e.g., 'S&P 500 (SPX)'
  color?: string; // e.g., '#2E86AB'
  autoRefresh?: boolean; // Auto refresh data every 5 minutes
  refreshInterval?: number; // Refresh interval in milliseconds
}

// Memoized constants to prevent recreation on every render
const PCT_COLORS = [
  "#1abc9c", "#3498db", "#9b59b6", "#e67e22", "#e74c3c", "#f39c12",
];

const PCT_DASH_STYLES = [
  "ShortDash", "ShortDot", "ShortDashDot", "Dash", "Dot", "DashDot",
];

const PCT_PERCENTS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6];

const MarketPeChart: React.FC<MarketPeChartProps> = React.memo(({
  indexId,
  displayName,
  color = "#2E86AB",
  autoRefresh = false,
  refreshInterval = 60 * 60 * 1000, // 1 hour
}) => {
  const [peData, setPeData] = useState<PEData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nYears, setNYears] = useState<number>(20); // N-year window
  const [showPercentageLines, setShowPercentageLines] = useState(true);
  const [showStdDevLines, setShowStdDevLines] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [currentViewRange, setCurrentViewRange] = useState<{min: number | undefined, max: number | undefined}>({min: undefined, max: undefined});

  // Web Worker for heavy calculations
  const { rollingStats, isLoading: isCalculating, calculateStats } = useRollingStatsWorker();

  // Memoized fetch function - updated to use new API structure
  const fetchPEData = useCallback(async (index: string): Promise<PEData> => {
    const data = await dataApi.getMarketPE(index);
    if (!data) {
      throw new Error(`Failed to fetch ${index} PE data: No data available`);
    }
    return data;
  }, []);

  // Memoized data loading function
  const loadData = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      setIsRefreshing(true);
      setError(null);
      const data = await fetchPEData(indexId);

      if (data && data.stats && data.stats.current_pe !== undefined) {
        setPeData(data);
      } else {
        console.error('MarketPeChart: Invalid PE data structure:', data);
        setError('Invalid data structure received from API');
      }
    } catch (err) {
      console.error('MarketPeChart: Error loading PE data:', err);
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

  // Auto refresh effect with proper cleanup
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      loadData(false); // Don't show loading state for auto-refresh
    }, refreshInterval);

    return () => {
      clearInterval(interval);
    };
  }, [autoRefresh, refreshInterval, loadData]);

  // Trigger worker calculation when data or nYears changes
  useEffect(() => {
    if (peData?.data && peData.data.length > 0) {
      calculateStats(peData.data, nYears);
    }
  }, [peData?.data, nYears, calculateStats]);

  // Memoized chart configuration with optimized dependencies
  const chartConfig = useMemo(() => {
    if (!rollingStats) {
      return {
        pctColors: PCT_COLORS,
        pctDashStyles: PCT_DASH_STYLES,
        pctPercents: PCT_PERCENTS,
        pctLinesAbove: [],
        pctLinesBelow: [],
        visiblePctIdxs: [],
        xAxisMin: undefined,
        xAxisMax: undefined,
      };
    }

    const pctPercents = rollingStats.pctPercents || [];
    const pctLinesAbove = rollingStats.pctLinesAbove || [];
    const pctLinesBelow = rollingStats.pctLinesBelow || [];

    // Find the two percentage lines closest to the current value
    let visiblePctIdxs: number[] = [];
    if (peData?.data && peData.data.length && pctPercents.length) {
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

    // Calculate default xAxis min and max for last 6 months
    let xAxisMin: number | undefined = undefined;
    let xAxisMax: number | undefined = undefined;
    if (peData?.data && peData.data.length) {
      xAxisMax = peData.data[peData.data.length - 1][0];
      const ms6m = 6 * 30.44 * 24 * 3600 * 1000; // 6 months in milliseconds
      xAxisMin = xAxisMax - ms6m;
      if (xAxisMin < peData.data[0][0]) xAxisMin = peData.data[0][0];
    }

    return {
      pctColors: PCT_COLORS,
      pctDashStyles: PCT_DASH_STYLES,
      pctPercents,
      pctLinesAbove,
      pctLinesBelow,
      visiblePctIdxs,
      xAxisMin,
      xAxisMax,
    };
  }, [
    rollingStats, // depend on the full rollingStats object
    nYears, // depend on nYears
    peData?.data, // depend on the actual data array
    showPercentageLines, // in case config needs it
  ]);

  // Memoized chart options with optimized dependencies
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
        color: "#F92672",
        type: "line",
        zIndex: 3,
        lineWidth: 2,
        marker: {
          enabled: false,
          states: {
            hover: { enabled: true, radius: 6, lineWidth: 2, lineColor: color }
          }
        },
      },
    ];

    // Add rolling average
    if (rollingStats) {
      series.push({
        name: `${nYears}Y Avg`,
        data: rollingStats.avg,
        color: "#A6E22E",
        dashStyle: "Dash" as const,
        type: "line",
        zIndex: 2,
        lineWidth: 2,
        marker: { enabled: false },
      });

      // Add standard deviation lines
      if (showStdDevLines) {
        series.push(
          {
            name: `+2 Std`,
            data: rollingStats.plus2,
            color: "#FD971F",
            dashStyle: "Dot" as const,
            type: "line",
            zIndex: 1,
            lineWidth: 3,
            marker: { enabled: false },
          },
          {
            name: `-2 Std`,
            data: rollingStats.minus2,
            color: "#FD971F",
            dashStyle: "Dot" as const,
            type: "line",
            zIndex: 1,
            lineWidth: 3,
            marker: { enabled: false },
          }
        );
      }
    }

    // Add percentage lines if enabled
    if (showPercentageLines) {
      // Add percentage lines above
      pctPercents.forEach((pct, idx) => {
        series.push({
          name: `+${Math.round(pct * 100)}% Avg`,
          data: pctLinesAbove[idx],
          color: pctColors[idx],
          dashStyle: pctDashStyles[idx] as any,
          type: "line",
          zIndex: 0,
          lineWidth: 3,
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
          dashStyle: pctDashStyles[idx] as any,
          type: "line",
          zIndex: 0,
          lineWidth: 3,
          visible: visiblePctIdxs.includes(idx + pctPercents.length),
          marker: { enabled: false },
        });
      });
    }

    return {
      chart: {
        type: "line",
        height: 650,
        backgroundColor: "rgba(0, 0, 0, 0.3)",
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
        },
        plotBackgroundColor: "rgba(0, 0, 0, 0.2)",
        plotBorderWidth: 0,
        plotShadow: false,
        spacing: [5, 5, 5, 5], // Reduced spacing: [top, right, bottom, left]
        reflow: true, // Enable responsive behavior
      },
      title: {
        text: "",
      },
      subtitle: {
        text: "",
      },
      xAxis: {
        type: "datetime",
        labels: {
          format: "{value:%Y-%m-%d}",
          style: { fontSize: "14px", color: "#D1D5DB", fontWeight: "500" },
        },
        min: xAxisMin,
        max: xAxisMax,
        gridLineWidth: 2,
        gridLineColor: "rgba(107, 114, 128, 0.4)",
        lineColor: "rgba(156, 163, 175, 0.6)",
        tickColor: "rgba(156, 163, 175, 0.6)",
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
          text: "PE Ratio",
          style: { fontSize: "16px", fontWeight: "700", color: "#E5E7EB" },
        },
        labels: {
          format: "{value:.1f}",
          style: { fontSize: "14px", color: "#D1D5DB", fontWeight: "500" },
        },
        gridLineWidth: 2,
        gridLineColor: "rgba(107, 114, 128, 0.4)",
        lineColor: "rgba(156, 163, 175, 0.6)",
        tickColor: "rgba(156, 163, 175, 0.6)",
        tickWidth: 2,
        tickLength: 6,
        crosshair: {
          color: 'rgba(96, 165, 250, 0.7)',
          width: 2,
          dashStyle: 'shortdot'
        }
      },
      tooltip: {
        shared: true,
        backgroundColor: "rgba(17, 24, 39, 0.98)",
        borderWidth: 0,
        shadow: true,
        borderRadius: 8,
        style: { fontSize: "13px", color: "#ffffff" },
        formatter: function (this: any) {
          const date = Highcharts.dateFormat("%Y-%m-%d", this.x);
          let tooltip = `<div style="padding: 4px 0;"><b style="color: #60A5FA; font-size: 14px;">${date}</b></div><br/>`;
          this.points?.forEach((point: any) => {
            const seriesName = point.series.name;
            const value = point.y?.toFixed(2);
            const isMainSeries = seriesName === displayName;
            const isAvgSeries = seriesName.includes('Avg') && !seriesName.includes('%');
            
            let nameColor = "#9ca3af";
            let valueColor = "#ffffff";
            
            if (isMainSeries) {
              nameColor = "#60A5FA";
              valueColor = "#60A5FA";
            } else if (isAvgSeries) {
              nameColor = "#A78BFA";
              valueColor = "#A78BFA";
            }
            
            tooltip += `<span style="color:${point.color}; font-size: 16px;">●</span> <span style="color: ${nameColor}; font-weight: 500;">${seriesName}</span>: <span style="color: ${valueColor}; font-weight: bold;">${value}</span><br/>`;
          });
          return tooltip;
        },
      },
      legend: {
        enabled: true,
        align: "center",
        verticalAlign: "bottom",
        layout: "horizontal",
        itemStyle: { 
          fontSize: "14px",
          color: "#F3F4F6",
          fontWeight: "600"
        },
        itemHoverStyle: {
          color: "#60A5FA"
        },
        symbolHeight: 12,
        symbolWidth: 24,
        symbolRadius: 3,
        backgroundColor: "rgba(0, 0, 0, 0.9)",
        borderWidth: 1,
        borderColor: "rgba(75, 85, 99, 0.6)",
        borderRadius: 8,
        shadow: true,
        itemDistance: 20,
        padding: 12,
        width: "100%",
        height: 50,
        itemWidth: 150,
        useHTML: false,
        floating: false,
        x: 0,
        y: 0,
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
        outlineWidth: 0,
        outlineColor: "transparent",
        handles: {
          backgroundColor: "rgba(96, 165, 250, 0.8)",
          borderColor: "rgba(96, 165, 250, 1)",
          lineColor: "rgba(96, 165, 250, 0.5)",
          rifleColor: "rgba(96, 165, 250, 0.8)",
        },
        xAxis: {
          gridLineColor: "rgba(0, 0, 0, 0.4)",
          lineColor: "rgba(75, 85, 99, 0.6)",
          tickColor: "rgba(75, 85, 99, 0.4)",
          labels: {
            style: {
              color: "#9ca3af",
              fontSize: "10px",
            },
          },
        },
      },
      scrollbar: {
        enabled: true,
        barBackgroundColor: "rgba(75, 85, 99, 0.5)",
        barBorderColor: "rgba(75, 85, 99, 0.8)",
        buttonBackgroundColor: "rgba(55, 65, 81, 0.8)",
        buttonBorderColor: "rgba(75, 85, 99, 0.8)",
        buttonArrowColor: "#9ca3af",
        rifleColor: "rgba(96, 165, 250, 0.8)",
        trackBackgroundColor: "rgba(31, 41, 55, 0.3)",
        trackBorderColor: "rgba(75, 85, 99, 0.3)",
      },
      rangeSelector: {
        enabled: true,
        selected: 0, // 6m button
        inputEnabled: false,
        buttonTheme: {
          fill: "rgba(0, 0, 0, 0.9)",
          stroke: "rgba(75, 85, 99, 0.6)",
          r: 8,
          states: {
            hover: {
              fill: "rgba(31, 41, 55, 0.9)",
              style: {
                color: "#ffffff",
              },
            },
            select: {
              fill: "rgba(96, 165, 250, 0.8)",
              style: {
                color: "#ffffff",
                fontWeight: "bold",
              },
            },
          },
          style: {
            color: "#9ca3af",
            fontSize: "12px",
            fontWeight: "500",
          },
        },
        buttons: [
          { type: "month", count: 6, text: "6m" },
          { type: "year", count: 1, text: "1y" },
          { type: "year", count: 3, text: "3y" },
          { type: "year", count: 5, text: "5y" },
          { type: "all", text: "All" },
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
      series,
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
    } as unknown as Highcharts.Options;
  }, [
    displayName,
    color,
    nYears,
    rollingStats, // depend on the full rollingStats object
    showStdDevLines,
    showPercentageLines,
    chartConfig, // depend on the full chartConfig object
    peData?.data, // depend on the actual data array
  ]); // Optimized dependencies using full objects and values

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

  if (isCalculating && !rollingStats) {
    return (
      <div className="chart-container">
        <LoadingSpinner text="Calculating statistics..." />
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
      <div className="chart-header py-1">
        <div className="flex items-center justify-between">
          <h2 className="chart-title text-lg" style={{ color }}>
            {displayName}
          </h2>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm font-medium text-text-primary">
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
            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer text-text-primary">
              <input
                type="checkbox"
                checked={showStdDevLines}
                onChange={(e) => setShowStdDevLines(e.target.checked)}
              />
              Std Dev Lines
            </label>
            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer text-text-primary">
              <input
                type="checkbox"
                checked={showPercentageLines}
                onChange={(e) => setShowPercentageLines(e.target.checked)}
              />
              Percentage Lines
            </label>
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
      </div>
      
      {peData && (
        <div className="chart-stats py-0.5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-1">
            <div className="chart-stat">
              <div className="chart-stat-label text-xs leading-tight">Current PE</div>
              <div className="chart-stat-value text-sm leading-tight">{peData.stats.current_pe.toFixed(2)}</div>
            </div>
            <div className="chart-stat">
              <div className="chart-stat-label text-xs leading-tight">{nYears}-Year Avg</div>
              <div className="chart-stat-value text-sm leading-tight">
                {rollingStats?.avg && rollingStats.avg.length > 0 && rollingStats.avg[rollingStats.avg.length - 1]?.[1] 
                  ? rollingStats.avg[rollingStats.avg.length - 1][1]?.toFixed(2)
                  : peData.stats.avg_20y.toFixed(2)
                }
              </div>
            </div>
            <div className="chart-stat">
              <div className="chart-stat-label text-xs leading-tight">Range</div>
              <div className="chart-stat-value text-xs leading-tight">
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
              </div>
            </div>
            <div className="chart-stat">
              <div className="chart-stat-label text-xs leading-tight">vs {nYears}Y Avg</div>
              <div className={`chart-stat-value text-sm leading-tight ${
                peData.stats.current_pe > (rollingStats?.avg && rollingStats.avg.length > 0 && rollingStats.avg[rollingStats.avg.length - 1]?.[1] || peData.stats.avg_20y) ? 'text-danger-400' : 'text-success-400'
              }`}>
                {((peData.stats.current_pe / (rollingStats?.avg && rollingStats.avg.length > 0 && rollingStats.avg[rollingStats.avg.length - 1]?.[1] || peData.stats.avg_20y) - 1) * 100).toFixed(1)}%
              </div>
            </div>
          </div>
        </div>
      )}
      
      <div className="mt-1">
        <HighchartsReact
          highcharts={Highcharts}
          options={chartOptions}
          callback={chartCallback}
        />
      </div>
    </div>
  );
});

MarketPeChart.displayName = 'MarketPeChart';

export default MarketPeChart;
