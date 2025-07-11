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

interface MarketBreadthCardProps {
  indexId: string; // e.g., 'spx', 'qqq', etc.
}

function parseTradeDate(trade_date: string): number {
  // "2024,07,23,00,00,00,000000" => timestamp (ms)
  const [year, month, day] = trade_date.split(",");
  return new Date(Number(year), Number(month) - 1, Number(day)).getTime();
}

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

const MarketBreadthCard: React.FC<MarketBreadthCardProps> = ({ indexId }) => {
  const [data, setData] = useState<MarketBreadthData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSMA, setSelectedSMA] = useState(0); // 0: SMA20, 1: SMA50, 2: SMA200
  const [nYears, setNYears] = useState<number>(3); // N-year window for zoom
  const [showSectorLines, setShowSectorLines] = useState(false); // Show/hide sector lines
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/mbs?market_index=${indexId}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then((arr) => {
        if (Array.isArray(arr) && arr.length > 0) {
          setData(arr);
        } else {
          setData([]);
          setError("No market breadth data available");
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(`Failed to load market breadth: ${err.message}`);
        setLoading(false);
      });
  }, [indexId]);

  // Handle manual refresh
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    setError(null);
    fetch(`/api/mbs?market_index=${indexId}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then((arr) => {
        if (Array.isArray(arr) && arr.length > 0) {
          setData(arr);
        } else {
          setData([]);
          setError("No market breadth data available");
        }
        setIsRefreshing(false);
      })
      .catch((err) => {
        setError(`Failed to load market breadth: ${err.message}`);
        setIsRefreshing(false);
      });
  }, [indexId]);

  // Handle N-year change
  const handleNYearsChange = useCallback((value: number) => {
    setNYears(Math.max(1, Math.min(20, value)));
  }, []);

  // Calculate chart statistics
  const chartStats = useMemo(() => {
    if (!data || data.length === 0) return null;
    
    const smaOption = SMA_OPTIONS[selectedSMA];
    const scores = data.map(d => d[smaOption.key as keyof MarketBreadthData] as number);
    
    const currentScore = scores[scores.length - 1];
    const avgScore = scores.reduce((sum, score) => sum + score, 0) / scores.length;
    const minScore = Math.min(...scores);
    const maxScore = Math.max(...scores);
    
    // Calculate 20-period average
    const recentScores = scores.slice(-20);
    const avg20Period = recentScores.reduce((sum, score) => sum + score, 0) / recentScores.length;
    
    return {
      current: currentScore,
      average: avgScore,
      min: minScore,
      max: maxScore,
      avg20Period: avg20Period,
      period: smaOption.label
    };
  }, [data, selectedSMA]);

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

  // Prepare chart data
  const smaOption = SMA_OPTIONS[selectedSMA];
  const xData = data.map((d) => parseTradeDate(d.trade_date));
  // Generic score series
  const genericSeries = {
    name: smaOption.label,
    data: data.map((d, i) => [
      xData[i],
      d[smaOption.key as keyof MarketBreadthData] as number,
    ]),
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
    // no stacking property
  };
  // Collect all unique sector keys (from the first non-empty sector array)
  let sectorKeys: string[] = [];
  for (const d of data) {
    const arr = d[smaOption.sector as keyof MarketBreadthData] as SectorScore[];
    if (arr && arr.length > 0) {
      sectorKeys = arr.map((s) => s.sector_key);
      break;
    }
  }
  // Sector series
  const sectorSeries = sectorKeys.map((sector, idx) => ({
    name: sector,
    data: data.map((d, i) => {
      const arr = d[
        smaOption.sector as keyof MarketBreadthData
      ] as SectorScore[];
      const found = arr?.find((s) => s.sector_key === sector);
      return [xData[i], found ? found.score : null];
    }),
    color: COLORS[(idx + 1) % COLORS.length],
    type: "area" as const,
    zIndex: 1,
    lineWidth: 1,
    visible: showSectorLines, // controlled by checkbox
    marker: { enabled: false },
    stacking: "normal" as const,
  }));

  // Compact chart options
  const chartOptions: Highcharts.Options = {
    chart: {
      type: "line", // This will be overridden by individual series types
      height: 500,
      backgroundColor: "transparent",
      spacing: [10, 12, 10, 12],
      style: { fontFamily: "inherit" },
      panning: {
        enabled: true,
        type: "x",
      },
      plotBackgroundColor: "transparent",
      plotBorderWidth: 0,
      plotShadow: false,
    },
    title: {
      text: "",
    },
    // Calculate default xAxis min and max for last N years
    xAxis: {
      type: "datetime",
      title: {
        text: "Date",
        style: { fontSize: "16px", fontWeight: "700", color: "#E5E7EB" },
      },
      labels: { 
        format: "{value:%Y-%m-%d}", 
        style: { fontSize: "14px", color: "#D1D5DB", fontWeight: "500" } 
      },
      tickLength: 6,
      tickWidth: 2,
      minTickInterval: 24 * 3600 * 1000 * 7, // at least 1 week
      min:
        xData.length > 0
          ? xData[Math.max(0, xData.length - nYears * 365)]
          : undefined, // N years ago
      max: xData.length > 0 ? xData[xData.length - 1] : undefined, // latest data
      gridLineWidth: 2,
      gridLineColor: "rgba(107, 114, 128, 0.4)",
      lineColor: "rgba(156, 163, 175, 0.6)",
      tickColor: "rgba(156, 163, 175, 0.6)",
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
      backgroundColor: "rgba(17, 24, 39, 0.8)",
      borderWidth: 1,
      borderColor: "rgba(75, 85, 99, 0.5)",
      borderRadius: 8,
      shadow: true,
      itemDistance: 20,
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
          const isMainSeries = seriesName === smaOption.label;
          
          let nameColor = "#9ca3af";
          let valueColor = "#ffffff";
          
          if (isMainSeries) {
            nameColor = "#60A5FA";
            valueColor = "#60A5FA";
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
    series: [genericSeries, ...sectorSeries],
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
        gridLineColor: "rgba(75, 85, 99, 0.3)",
        lineColor: "rgba(75, 85, 99, 0.5)",
        tickColor: "rgba(75, 85, 99, 0.3)",
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
      selected: 2, // 3y button
      inputEnabled: false,
      buttonTheme: {
        fill: "rgba(31, 41, 55, 0.8)",
        stroke: "rgba(75, 85, 99, 0.5)",
        r: 8,
        states: {
          hover: {
            fill: "rgba(55, 65, 81, 0.8)",
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
        { type: "year", count: 1, text: "1y" },
        { type: "year", count: 2, text: "2y" },
        { type: "year", count: 3, text: "3y" },
        { type: "all", text: "All" },
      ],
    },
  };

  return (
    <div className="chart-container">
      <div className="chart-header">
        <div className="flex items-center justify-between">
          <h2 className="chart-title">
            {data[0].index_name.toUpperCase()} Market Breadth
          </h2>
          <div className="flex items-center gap-2 text-sm text-gray-600">
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
                    ? "text-blue-400 font-semibold" 
                    : "text-gray-400 hover:text-gray-300"
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
            
            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={showSectorLines}
                onChange={(e) => setShowSectorLines(e.target.checked)}
              />
              Sector Lines
            </label>
          </div>
        </div>
      </div>
      
      {chartStats && (
        <div className="chart-stats">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="chart-stat">
              <div className="chart-stat-label">Current {chartStats.period}</div>
              <div className="chart-stat-value">{chartStats.current.toFixed(0)}</div>
            </div>
            <div className="chart-stat">
              <div className="chart-stat-label">20-Period Avg</div>
              <div className="chart-stat-value">{chartStats.avg20Period.toFixed(0)}</div>
            </div>
            <div className="chart-stat">
              <div className="chart-stat-label">All-Time Avg</div>
              <div className="chart-stat-value">{chartStats.average.toFixed(0)}</div>
            </div>
            <div className="chart-stat">
              <div className="chart-stat-label">Min</div>
              <div className="chart-stat-value">{chartStats.min.toFixed(0)}</div>
            </div>
            <div className="chart-stat">
              <div className="chart-stat-label">Max</div>
              <div className="chart-stat-value">{chartStats.max.toFixed(0)}</div>
            </div>
          </div>
        </div>
      )}
      
      <div className="mt-6">
        <HighchartsReact highcharts={Highcharts} options={chartOptions} />
      </div>
    </div>
  );
};

export default MarketBreadthCard;
