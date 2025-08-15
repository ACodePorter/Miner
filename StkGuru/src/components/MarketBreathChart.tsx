import React, { useEffect, useState, useCallback, useMemo } from "react";
import Highcharts from "highcharts/highstock";
import HighchartsReact from "highcharts-react-official";
import LoadingSpinner from "./LoadingSpinner";
import ErrorMessage from "./ErrorMessage";

export interface SectorScore {
  sector_key: string;
  score: number;
}

export interface MarketBreadthData {
  index_name: string;
  trade_date: string; // "2024,07,23,00,00,00,000000"
  score_sma20: number;
  score_sma50: number;
  score_sma200: number;
  sector_score20: SectorScore[];
  sector_score50: SectorScore[];
  sector_score200: SectorScore[];
}

interface MarketBreathChartProps {
  indexId: string; // e.g., 'spx', 'qqq', etc.
}

// Memoized constants to prevent recreation on every render
const SMA_OPTIONS = [
  { key: "score_sma20", label: "SMA 20", sector: "sector_score20" },
  { key: "score_sma50", label: "SMA 50", sector: "sector_score50" },
  { key: "score_sma200", label: "SMA 200", sector: "sector_score200" },
];

const COLORS = [
  "#F92672", // Pink - main series
  "#A6E22E", // Green
  "#FD971F", // Orange
  "#AE81FF", // Purple
  "#66D9EF", // Cyan
  "#E6DB74", // Yellow
  "#F92672", // Pink
  "#A6E22E", // Green
  "#FD971F", // Orange
  "#AE81FF", // Purple
  "#66D9EF", // Cyan
  "#E6DB74", // Yellow
  "#F92672", // Pink
  "#A6E22E", // Green
  "#FD971F", // Orange
  "#AE81FF", // Purple
  "#66D9EF", // Cyan
  "#E6DB74", // Yellow
  "#F92672", // Pink
  "#A6E22E", // Green
];

function parseTradeDate(trade_date: string): number {
  // "2024,07,23,00,00,00,000000" => timestamp (ms)
  const [year, month, day] = trade_date.split(",");
  return new Date(Number(year), Number(month) - 1, Number(day)).getTime();
}

const MarketBreathChart: React.FC<MarketBreathChartProps> = React.memo(({ indexId }) => {
  const [data, setData] = useState<MarketBreadthData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSMA, setSelectedSMA] = useState(0); // 0: SMA20, 1: SMA50, 2: SMA200
  const [nYears, setNYears] = useState<number>(3); // N-year window for zoom
  const [showSectorLines, setShowSectorLines] = useState(false); // Show/hide sector lines
  const [isRefreshing, setIsRefreshing] = useState(false);
  


  // Memoized fetch function
  const fetchMarketBreadthData = useCallback(async (index: string): Promise<MarketBreadthData[]> => {
    const response = await fetch(`/api/mbs/${index}.json`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const arr = await response.json();
    if (Array.isArray(arr) && arr.length > 0) {
      return arr;
    } else {
      throw new Error("No market breadth data available");
    }
  }, []);

  // Memoized data loading function
  const loadData = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      setIsRefreshing(true);
      setError(null);
      const arr = await fetchMarketBreadthData(indexId);
      setData(arr);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load market breadth data");
      setData([]);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [fetchMarketBreadthData, indexId]);

  // Initial data load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle manual refresh
  const handleRefresh = useCallback(() => {
    loadData(false);
  }, [loadData]);

  // Handle N-year change
  const handleNYearsChange = useCallback((value: number) => {
    setNYears(Math.max(1, Math.min(20, value)));
  }, []);

  // Memoized data transformations
  const processedData = useMemo(() => {
    if (!data || data.length === 0) return null;
    
    const smaOption = SMA_OPTIONS[selectedSMA];
    
    // Sort data by date to ensure proper time series
    const sortedData = [...data].sort((a, b) => parseTradeDate(a.trade_date) - parseTradeDate(b.trade_date));
    
    const xData = sortedData.map((d) => parseTradeDate(d.trade_date));
    const scores = sortedData.map(d => d[smaOption.key as keyof MarketBreadthData] as number);
    

    
    // Collect all unique sector keys (from the first non-empty sector array)
    let sectorKeys: string[] = [];
    for (const d of sortedData) {
      const arr = d[smaOption.sector as keyof MarketBreadthData] as SectorScore[];
      if (arr && arr.length > 0) {
        sectorKeys = arr.map((s) => s.sector_key);
        break;
      }
    }

    // Single-pass calculation for min, max, and average
    let sum = 0;
    let minScore = scores[0];
    let maxScore = scores[0];
    
    for (let i = 0; i < scores.length; i++) {
      const score = scores[i];
      sum += score;
      if (score < minScore) minScore = score;
      if (score > maxScore) maxScore = score;
    }
    
    const avgScore = sum / scores.length;
    
    // Calculate 20-period average efficiently
    const last20Scores = scores.slice(-20);
    const avg20Period = last20Scores.reduce((sum, score) => sum + score, 0) / last20Scores.length;
    
    return {
      xData,
      scores,
      sectorKeys,
      smaOption,
      sortedData,
      currentScore: scores[scores.length - 1],
      avgScore,
      minScore,
      maxScore,
      avg20Period
    };
  }, [data, selectedSMA]);

  // Memoized chart statistics
  const chartStats = useMemo(() => {
    if (!processedData) return null;
    
    return {
      current: processedData.currentScore,
      average: processedData.avgScore,
      min: processedData.minScore,
      max: processedData.maxScore,
      avg20Period: processedData.avg20Period,
      period: processedData.smaOption.label
    };
  }, [
    processedData?.currentScore,
    processedData?.avgScore,
    processedData?.minScore,
    processedData?.maxScore,
    processedData?.avg20Period,
    processedData?.smaOption?.label,
  ]);

  // Memoized chart series data
  const chartSeries = useMemo(() => {
    if (!processedData) return { genericSeries: null, highlightSeries: null, sectorSeries: [], horizontalLines: [] };
    
    const { xData, scores, sectorKeys, smaOption, sortedData } = processedData;
    
    // Generic score series
    const genericSeries = {
      name: smaOption.label,
      data: xData.map((x, i) => [x, scores[i]]),
      color: "#F92672",
      type: "line" as const,
      zIndex: 2,
      lineWidth: 2,
      marker: { 
        enabled: false,
        states: {
          hover: { enabled: true, radius: 6, lineWidth: 2, lineColor: COLORS[0] }
        }
      },
      // Ensure this series is used for rangeSelector calculations
      id: 'main-series',
    };

    // Highlight series for extreme values
    const highlightAbove950Series = {
      name: `${smaOption.label} (Above 950)`,
      data: xData.map((x, i) => [x, scores[i] > 950 ? scores[i] : null]),
      color: "#FFD700",
      type: "line" as const,
      zIndex: 3,
      lineWidth: 0,
      marker: {
        enabled: true,
        radius: 6,
        symbol: "circle",
        fillColor: "#FF6B6B",
        lineColor: "#FFD700",
        lineWidth: 2,
        states: {
          hover: {
            enabled: true,
            radius: 8,
            lineWidth: 3,
            lineColor: "#FFD700"
          }
        }
      },
      enableMouseTracking: true,
      stickyTracking: false,
      showInLegend: false
    };

    const highlightBelow200Series = {
      name: `${smaOption.label} (Below 200)`,
      data: xData.map((x, i) => [x, scores[i] < 200 ? scores[i] : null]),
      color: "#4ECDC4",
      type: "line" as const,
      zIndex: 3,
      lineWidth: 0,
      marker: {
        enabled: true,
        radius: 6,
        symbol: "circle",
        fillColor: "#4ECDC4",
        lineColor: "#FFD700",
        lineWidth: 2,
        states: {
          hover: {
            enabled: true,
            radius: 8,
            lineWidth: 3,
            lineColor: "#FFD700"
          }
        }
      },
      enableMouseTracking: true,
      stickyTracking: false,
      showInLegend: false
    };

    // Sector series
    const sectorSeries = sectorKeys.map((sector, idx) => ({
      name: sector,
      data: xData.map((x, i) => {
        const arr = sortedData[i][smaOption.sector as keyof MarketBreadthData] as SectorScore[];
        const found = arr?.find((s) => s.sector_key === sector);
        return [x, found ? found.score : null];
      }),
      color: COLORS[(idx + 1) % COLORS.length],
      type: "area" as const,
      zIndex: 1,
      lineWidth: 1,
      visible: showSectorLines,
      marker: { enabled: false },
      stacking: "normal" as const,
    }));

    // Horizontal reference lines
    const horizontalLines = [
      {
        name: "950 Level",
        data: xData.map(x => [x, 950]),
        color: "#FF6B6B",
        type: "line" as const,
        zIndex: 0,
        lineWidth: 2,
        dashStyle: "Dash" as const,
        marker: { enabled: false },
        showInLegend: false,
        enableMouseTracking: false,
        stickyTracking: false,
      },
      {
        name: "200 Level",
        data: xData.map(x => [x, 200]),
        color: "#4ECDC4",
        type: "line" as const,
        zIndex: 0,
        lineWidth: 2,
        dashStyle: "Dash" as const,
        marker: { enabled: false },
        showInLegend: false,
        enableMouseTracking: false,
        stickyTracking: false,
      }
    ];

    return {
      genericSeries,
      highlightAbove950Series,
      highlightBelow200Series,
      sectorSeries,
      horizontalLines
    };
  }, [processedData, showSectorLines, selectedSMA]);

  // Memoized chart options
  const chartOptions = useMemo(() => {
    if (!processedData || !chartSeries) return null;

    // const { xData } = processedData; // Unused variable removed
    const { genericSeries, highlightAbove950Series, highlightBelow200Series, sectorSeries, horizontalLines } = chartSeries;

    return {
      chart: {
        type: "line",
        height: 650,
        backgroundColor: "rgba(0, 0, 0, 0.3)",
        zoomType: "x",
        spacing: [5, 5, 5, 5], // Reduced spacing: [top, right, bottom, left]
        style: { fontFamily: "inherit" },
        panning: {
          enabled: true,
          type: "x",
        },
        plotBackgroundColor: "rgba(0, 0, 0, 0.2)",
        plotBorderWidth: 0,
        plotShadow: false,
      },
      title: {
        text: "",
      },
      xAxis: {
        type: "datetime",
        title: {
          text: "",
          style: { fontSize: "16px", fontWeight: "700", color: "#E5E7EB" },
        },
        labels: { 
          format: "{value:%Y-%m-%d}", 
          style: { fontSize: "14px", color: "#D1D5DB", fontWeight: "500" } 
        },
        tickLength: 6,
        tickWidth: 2,
        minTickInterval: 24 * 3600 * 1000 * 7, // at least 1 week
        gridLineWidth: 2,
        gridLineColor: "rgba(107, 114, 128, 0.4)",
        lineColor: "rgba(156, 163, 175, 0.6)",
        tickColor: "rgba(156, 163, 175, 0.6)",
        crosshair: {
          color: 'rgba(96, 165, 250, 0.7)',
          width: 2,
          dashStyle: 'shortdot'
        }
      },
      yAxis: {
        title: { 
          text: "Score",
          style: { fontSize: "16px", fontWeight: "700", color: "#E5E7EB" },
        },
        labels: { 
          format: "{value}", 
          style: { fontSize: "14px", color: "#D1D5DB", fontWeight: "500" } 
        },
        min: 0,
        max: 1100,
        gridLineWidth: 2,
        gridLineColor: "rgba(107, 114, 128, 0.4)",
        lineColor: "rgba(156, 163, 175, 0.6)",
        tickColor: "rgba(75, 85, 99, 0.3)",
        crosshair: {
          color: 'rgba(96, 165, 250, 0.7)',
          width: 2,
          dashStyle: 'shortdot'
        }
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
        margin: 8,
        padding: 12,
        backgroundColor: "rgba(0, 0, 0, 0.9)",
        borderWidth: 1,
        borderColor: "rgba(75, 85, 99, 0.6)",
        borderRadius: 8,
        shadow: true,
        itemDistance: 20,
        width: "100%", // Align width with chart area
        x: 0, // Align to left edge of chart area
        useHTML: false,
        floating: false,
      },
      tooltip: {
        shared: true,
        backgroundColor: "rgba(17, 24, 39, 0.98)",
        borderWidth: 0,
        shadow: true,
        borderRadius: 8,
        style: { fontSize: "13px", color: "#ffffff" },
        formatter: function (this: any) {
          const date = Highcharts.dateFormat("%Y-%m-%d", this.x as number);
          let tooltip = `<div style="padding: 4px 0;"><b style="color: #60A5FA; font-size: 14px;">${date}</b></div><br/>`;
          this.points?.forEach((point: any) => {
            const seriesName = point.series.name;
            const value = point.y;
            const isMainSeries = seriesName === processedData.smaOption.label;
            const isHorizontalLine = seriesName === "950 Level" || seriesName === "200 Level";
            
            // Skip horizontal reference lines in tooltip
            if (isHorizontalLine) {
              return;
            }
            
            let nameColor = "#9ca3af";
            let valueColor = "#ffffff";
            
            if (isMainSeries) {
              nameColor = "#60A5FA";
              valueColor = "#60A5FA";
            } else if (seriesName.includes("Above 950")) {
              nameColor = "#FF6B6B";
              valueColor = "#FF6B6B";
            } else if (seriesName.includes("Below 200")) {
              nameColor = "#4ECDC4";
              valueColor = "#4ECDC4";
            }
            
            tooltip += `<span style="color:${point.color}; font-size: 16px;">●</span> <span style="color: ${nameColor}; font-weight: 500;">${seriesName}</span>: <span style="color: ${valueColor}; font-weight: bold;">${value}</span><br/>`;
          });
          return tooltip;
        },
      },
      plotOptions: {
        line: {
          marker: { enabled: false },
          lineWidth: 2,
        },
        area: {
          marker: { enabled: false },
          lineWidth: 1,
          fillOpacity: 0.6,
        },
        series: {
          animation: { duration: 600 },
        },
      },
      series: [genericSeries, highlightAbove950Series, highlightBelow200Series, ...sectorSeries, ...horizontalLines],
      credits: { enabled: false },
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
              stroke: 'rgba(75, 85, 99, 0.5)'
            }
          }
        }
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
          { type: "year", count: 2, text: "2y" },
          { type: "year", count: 3, text: "3y" },
          { type: "all", text: "All" },
        ],
        events: {
          click: function(e: any) {
            // Handle range selector button clicks (development only)
            if (import.meta.env.DEV) {
              console.log('Range selector clicked:', e);
            }
          }
        }
      },
    } as unknown as Highcharts.Options;
  }, [processedData, chartSeries, showSectorLines, nYears, selectedSMA]);

  if (loading) {
    return (
      <div className="chart-container">
        <LoadingSpinner text="Loading Market Breadth..." />
      </div>
    );
  }


  
  if (error) {
    return (
      <div className="chart-container">
        <ErrorMessage message={`Error: ${error}`} />
      </div>
    );
  }
  
  if (!data || data.length === 0) {
    return null;
  }

  return (
    <div className="chart-container">
      <div className="chart-header py-1">
        <div className="flex items-center justify-between">
          <h2 className="chart-title text-lg">
            {data[0].index_name.toUpperCase()} Market Breadth
          </h2>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm font-medium text-text-primary">
              N-year:
              <input
                type="number"
                min={1}
                max={20}
                value={nYears}
                onChange={(e) => handleNYearsChange(Number(e.target.value))}
                className="input-field w-16 text-center"
                aria-label="N-year window"
              />
            </label>
            
            {SMA_OPTIONS.map((opt, idx) => (
              <label
                key={opt.key}
                className={`flex items-center gap-2 cursor-pointer transition-colors duration-200 ${
                  idx === selectedSMA 
                    ? "text-primary-400 font-semibold" 
                    : "text-text-tertiary hover:text-text-secondary"
                }`}
              >
                <input
                  type="radio"
                  name="sma"
                  value={String(idx)}
                  checked={selectedSMA === idx}
                  onChange={(e) => setSelectedSMA(Number(e.target.value))}
                  aria-label={`Select ${opt.label}`}
                />
                <span className="text-sm font-medium">{opt.label}</span>
              </label>
            ))}
            
            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer text-text-primary">
              <input
                type="checkbox"
                checked={showSectorLines}
                onChange={(e) => setShowSectorLines(e.target.checked)}
              />
              Sector Lines
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
      
      {chartStats && (
        <div className="chart-stats py-0.5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {/* Progress Bar */}
            <div className="chart-stat flex flex-col justify-center">
              <div className="chart-stat-label text-center text-xs leading-tight">Score</div>
              <div className="flex flex-col items-center py-1">
                {/* Progress bar */}
                <div className="w-full bg-bg-tertiary rounded-full h-3 mb-1 relative">
                  {/* Background with extreme value markers */}
                  <div className="absolute inset-0 rounded-full overflow-hidden">
                    {/* Below 200 zone */}
                    <div 
                      className="absolute left-0 h-full bg-danger-900/50 border-r border-danger-600/70"
                      style={{ width: `${(200 / 1100) * 100}%` }}
                    ></div>
                    {/* Above 950 zone */}
                    <div 
                      className="absolute right-0 h-full bg-danger-900/40 border-l border-danger-600/60"
                      style={{ 
                        width: `${((1100 - 950) / 1100) * 100}%`,
                        left: `${(950 / 1100) * 100}%`
                      }}
                    ></div>
                  </div>
                  
                  {/* Progress fill */}
                  <div 
                    className="h-full rounded-full transition-all duration-500 relative"
                    style={{
                      width: `${Math.min(100, Math.max(0, (chartStats.current / 1100) * 100))}%`,
                      background: chartStats.current > 950 
                        ? 'linear-gradient(90deg, #FF6B6B, #FFD700)' 
                        : chartStats.current < 200 
                        ? 'linear-gradient(90deg, #4ECDC4, #FFD700)'
                        : 'linear-gradient(90deg, #3B82F6, #8B5CF6, #EC4899)'
                    }}
                  >
                    {/* Current value indicator */}
                    <div 
                      className="absolute right-0 top-1/2 transform translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full border-2 border-white"
                      style={{
                        background: chartStats.current > 950 ? "#FF6B6B" : chartStats.current < 200 ? "#4ECDC4" : "#3B82F6"
                      }}
                    ></div>
                  </div>
                  
                  {/* Extreme value labels */}
                  <div className="absolute -top-5 left-0 text-xs text-text-tertiary">0</div>
                  <div className="absolute -top-5 left-0 text-xs text-danger-400" style={{ left: `${(200 / 1100) * 100}%` }}>200</div>
                  <div className="absolute -top-5 right-0 text-xs text-danger-400" style={{ right: `${((1100 - 950) / 1100) * 100}%` }}>950</div>
                  <div className="absolute -top-5 right-0 text-xs text-text-tertiary">1100</div>
                </div>
                
                {/* Current value display */}
                <div className="text-sm font-bold text-text-primary leading-tight">
                  {chartStats.current.toFixed(0)} / 1100
                </div>
              </div>
            </div>

            {/* Top 3 Sectors - Enhanced */}
            <div className="chart-stat md:col-span-2 flex flex-col justify-center">
              <div className="grid grid-cols-3 gap-2 py-1">
                {(() => {
                  if (!processedData) {
                    return <div className="text-text-tertiary text-xs col-span-3 text-center">No sector data</div>;
                  }

                  const { smaOption } = processedData;
                  const currentData = data[data.length - 1];
                  const sectorScores = currentData[smaOption.sector as keyof MarketBreadthData] as SectorScore[];
                  
                  if (!sectorScores || sectorScores.length === 0) {
                    return <div className="text-text-tertiary text-xs col-span-3 text-center">No sector data</div>;
                  }

                  // Sort by score and get top 3
                  const topSectors = sectorScores
                    .sort((a, b) => b.score - a.score)
                    .slice(0, 3);

                  return topSectors.map((sector, idx) => (
                    <div key={sector.sector_key} className="text-center flex flex-col items-center bg-bg-tertiary rounded-lg p-2 border border-border-secondary">
                      <div className="flex items-center gap-1 mb-1">
                        <div 
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ backgroundColor: COLORS[(idx + 1) % COLORS.length] }}
                        ></div>
                        <span className="font-semibold text-text-primary text-xs whitespace-nowrap leading-tight">
                          {sector.sector_key}
                        </span>
                      </div>
                      <div className="font-bold text-text-primary text-lg leading-tight">
                        {sector.score.toFixed(0)}
                      </div>
                    </div>
                  ));
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
            callback={(chart: Highcharts.Chart) => {
              // Initialize chart if needed
              if (chart) {
                // Chart is ready - rangeSelector should work automatically
                if (import.meta.env.DEV) {
                  console.log('Chart initialized with rangeSelector');
                }
              }
            }}
          />
        )}
      </div>
    </div>
  );
});

MarketBreathChart.displayName = 'MarketBreathChart';

export default MarketBreathChart;
