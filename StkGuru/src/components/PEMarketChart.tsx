import React, { useState, useEffect } from "react";
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
}

const PEMarketChart: React.FC<PEMarketChartProps> = ({
  indexId,
  displayName,
  color = "#2E86AB",
}) => {
  const [peData, setPeData] = useState<PEData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nYears, setNYears] = useState<number>(10); // N-year window

  useEffect(() => {
    const fetchPEData = async (index: string): Promise<PEData> => {
      const response = await fetch(`/api/market_pe?index=${index}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch ${index} PE data`);
      }
      return response.json();
    };
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchPEData(indexId);
        setPeData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load PE data");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [indexId]);

  // Helper to get N-year window data (assume data is sorted by date ascending)
  const getNYearWindowData = () => {
    if (!peData || !peData.data.length) return [];
    // Each data point: [timestamp, value]
    const msPerYear = 365.25 * 24 * 3600 * 1000;
    const cutoff = peData.data[peData.data.length - 1][0] - nYears * msPerYear;
    return peData.data.filter(([ts]) => ts >= cutoff);
  };

  // Calculate rolling N-year average and stddev for each point in history
  const getRollingStats = () => {
    if (!peData || !peData.data.length)
      return { avg: [], plus2: [], minus2: [], pctLines: [] };
    const msPerYear = 365.25 * 24 * 3600 * 1000;
    const resultAvg: [number, number | null][] = [];
    const resultPlus2: [number, number | null][] = [];
    const resultMinus2: [number, number | null][] = [];
    // For percentage lines: array of arrays, one for each pct
    const pctPercents = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6];
    const pctLinesAbove: [number, number | null][][] = pctPercents.map(
      () => []
    );
    const pctLinesBelow: [number, number | null][][] = pctPercents.map(
      () => []
    );
    for (let i = 0; i < peData.data.length; ++i) {
      const [ts, v] = peData.data[i];
      // Find all points within the N-year window ending at ts
      const cutoff = ts - nYears * msPerYear;
      const window = [];
      for (let j = i; j >= 0; --j) {
        if (peData.data[j][0] >= cutoff) window.push(peData.data[j][1]);
        else break;
      }
      if (window.length > 1) {
        const avg = window.reduce((a, b) => a + b, 0) / window.length;
        const std = Math.sqrt(
          window.reduce((sum, x) => sum + (x - avg) ** 2, 0) / window.length
        );
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
  };

  const rollingStats = getRollingStats();

  const pctColors = [
    "#1abc9c",
    "#3498db",
    "#9b59b6",
    "#e67e22",
    "#e74c3c",
    "#34495e",
  ];
  const pctDashStyles = [
    "ShortDash",
    "ShortDot",
    "ShortDashDot",
    "Dash",
    "Dot",
    "DashDot",
  ];

  const pctPercents = rollingStats.pctPercents || [];
  const pctLinesAbove = rollingStats.pctLinesAbove || [];
  const pctLinesBelow = rollingStats.pctLinesBelow || [];

  // Find the two percentage lines (above or below) closest to the current value
  let visiblePctIdxs: number[] = [];
  if (peData && peData.data.length && pctPercents.length) {
    const lastIdx = peData.data.length - 1;
    const currentPE = peData.data[lastIdx][1];
    // Find the rolling avg at the last point
    const avgAtLast = rollingStats.avg[lastIdx]?.[1];
    if (avgAtLast !== null && avgAtLast !== undefined) {
      // Build all percentage lines' last values
      const aboveVals = pctLinesAbove.map((line) => line[lastIdx]?.[1]);
      const belowVals = pctLinesBelow.map((line) => line[lastIdx]?.[1]);
      // Build array of {idx, val, type} for all lines
      const allLines = [
        ...aboveVals.map((val, idx) => ({ idx, val, type: "above" })),
        ...belowVals.map((val, idx) => ({ idx, val, type: "below" })),
      ].filter((x) => x.val !== null && x.val !== undefined);
      // Sort by absolute distance to currentPE
      allLines.sort(
        (a, b) =>
          Math.abs((a.val ?? 0) - currentPE) -
          Math.abs((b.val ?? 0) - currentPE)
      );
      // Pick the two closest
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
    // Ensure min is not before first data point
    if (xAxisMin < peData.data[0][0]) xAxisMin = peData.data[0][0];
  }

  const chartOptions = {
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
    series: [
      {
        name: displayName,
        data: peData?.data || [],
        color: color,
        type: "line",
        zIndex: 3,
      },
      {
        name: `${nYears}Y Avg`,
        data: rollingStats.avg,
        color: "#888",
        dashStyle: "Dash",
        type: "line",
        zIndex: 2,
      },
      {
        name: `+2 Std`,
        data: rollingStats.plus2,
        color: "#b8860b",
        dashStyle: "Dot",
        type: "line",
        zIndex: 1,
      },
      {
        name: `-2 Std`,
        data: rollingStats.minus2,
        color: "#b8860b",
        dashStyle: "Dot",
        type: "line",
        zIndex: 1,
      },
      // Add percentage lines above
      ...pctPercents.map((pct, idx) => ({
        name: `+${Math.round(pct * 100)}% Avg`,
        data: pctLinesAbove[idx],
        color: pctColors[idx],
        dashStyle: pctDashStyles[idx],
        type: "line",
        zIndex: 0,
        visible: visiblePctIdxs.includes(idx),
      })),
      // Add percentage lines below
      ...pctPercents.map((pct, idx) => ({
        name: `-${Math.round(pct * 100)}% Avg`,
        data: pctLinesBelow[idx],
        color: pctColors[idx],
        dashStyle: pctDashStyles[idx],
        type: "line",
        zIndex: 0,
        visible: visiblePctIdxs.includes(idx + pctPercents.length),
      })),
    ].filter(Boolean) as Highcharts.SeriesOptionsType[],
    credits: {
      enabled: false,
    },
  } as Highcharts.Options;

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
      </div>
    );
  }

  return (
    <div className="chart-container">
      <div className="chart-header">
        <h2 className="chart-title" style={{ color }}>
          {displayName}
        </h2>
        <div className="chart-controls">
          <label className="flex items-center gap-2 text-sm font-medium">
            N-year:
            <input
              type="number"
              min={1}
              max={100}
              value={nYears}
              onChange={(e) => setNYears(Number(e.target.value))}
              className="input-field w-16 text-center"
              aria-label="N-year window"
            />
          </label>
        </div>
      </div>
      
      {peData && (
        <div className="chart-stats">
          <div className="chart-stat">
            <span className="chart-stat-label">Current PE</span>
            <span className="chart-stat-value">{peData.stats.current_pe.toFixed(2)}</span>
          </div>
          <div className="chart-stat">
            <span className="chart-stat-label">20-Year Average</span>
            <span className="chart-stat-value">{peData.stats.avg_20y.toFixed(2)}</span>
          </div>
          <div className="chart-stat">
            <span className="chart-stat-label">Range</span>
            <span className="chart-stat-value">
              {peData.stats.min_pe.toFixed(2)} - {peData.stats.max_pe.toFixed(2)}
            </span>
          </div>
        </div>
      )}
      
      <div className="mt-6">
        <HighchartsReact
          highcharts={Highcharts}
          options={chartOptions}
        />
      </div>
    </div>
  );
};

export default PEMarketChart;
