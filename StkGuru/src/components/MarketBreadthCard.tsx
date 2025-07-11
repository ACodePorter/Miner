import React, { useEffect, useState } from "react";
import Highcharts from "highcharts/highstock";
import HighchartsReact from "highcharts-react-official";

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
  return new Date(
    Number(year),
    Number(month) - 1,
    Number(day)
  ).getTime();
}

const SMA_OPTIONS = [
  { key: "score_sma20", label: "SMA 20", sector: "sector_score20" },
  { key: "score_sma50", label: "SMA 50", sector: "sector_score50" },
  { key: "score_sma200", label: "SMA 200", sector: "sector_score200" },
];

const COLORS = [
  "#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#5C415D", "#1B998B", "#ED217C", "#FF6F59", "#3A86FF", "#8338EC",
  "#FFBE0B", "#FB5607", "#FF006E", "#3A86FF", "#FFB4A2", "#B5838D", "#6D6875", "#FFB703", "#219EBC", "#023047"
];

const MarketBreadthCard: React.FC<MarketBreadthCardProps> = ({ indexId }) => {
  const [data, setData] = useState<MarketBreadthData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSMA, setSelectedSMA] = useState(0); // 0: SMA20, 1: SMA50, 2: SMA200

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/mbs?market_index=${indexId}`)
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(arr => {
        if (Array.isArray(arr) && arr.length > 0) {
          setData(arr);
        } else {
          setData([]);
          setError("No market breadth data available");
        }
        setLoading(false);
      })
      .catch(err => {
        setError(`Failed to load market breadth: ${err.message}`);
        setLoading(false);
      });
  }, [indexId]);

  if (loading) {
    return <div className="text-center">Loading Market Breadth...</div>;
  }
  if (error) {
    return <div className="text-center text-red-600">Error: {error}</div>;
  }
  if (!data || data.length === 0) {
    return null;
  }

  // Prepare chart data
  const smaOption = SMA_OPTIONS[selectedSMA];
  const xData = data.map(d => parseTradeDate(d.trade_date));
  // Generic score series
  const genericSeries = {
    name: smaOption.label,
    data: data.map((d, i) => [xData[i], d[smaOption.key as keyof MarketBreadthData] as number]),
    color: COLORS[0],
    type: "line" as const,
    zIndex: 2,
    marker: { enabled: false },
    // no stacking property
  };
  // Collect all unique sector keys (from the first non-empty sector array)
  let sectorKeys: string[] = [];
  for (const d of data) {
    const arr = d[smaOption.sector as keyof MarketBreadthData] as SectorScore[];
    if (arr && arr.length > 0) {
      sectorKeys = arr.map(s => s.sector_key);
      break;
    }
  }
  // Sector series
  const sectorSeries = sectorKeys.map((sector, idx) => ({
    name: sector,
    data: data.map((d, i) => {
      const arr = d[smaOption.sector as keyof MarketBreadthData] as SectorScore[];
      const found = arr?.find(s => s.sector_key === sector);
      return [xData[i], found ? found.score : null];
    }),
    color: COLORS[(idx + 1) % COLORS.length],
    type: "area" as const,
    zIndex: 1,
    visible: false, // hidden by default
    marker: { enabled: false },
    stacking: 'normal' as const,
  }));

  // Compact chart options
  const chartOptions: Highcharts.Options = {
    chart: {
      type: "line", // This will be overridden by individual series types
      height: 600,
      width: 900,
      backgroundColor: "#fff",
      spacing: [10, 12, 10, 12],
      style: { fontFamily: 'inherit' },
    },
    title: { text: `${data[0].index_name.toUpperCase()} Market Breadth`, style: { fontSize: "1.1rem", fontWeight: "bold" } },
    xAxis: {
      type: "datetime",
      labels: { format: "{value:%Y-%m-%d}", style: { fontSize: "0.85rem" } },
      tickLength: 0,
      minTickInterval: 24 * 3600 * 1000 * 7, // at least 1 week
    },
    yAxis: {
      title: { text: "Score" },
      labels: { format: "{value}", style: { fontSize: "0.85rem" } },
      min: 0,
      max: 1100,
      gridLineWidth: 1,
    },
    legend: {
      enabled: true,
      align: "center",
      verticalAlign: "bottom",
      layout: "horizontal",
      itemStyle: { fontSize: "0.85rem" },
      symbolHeight: 8,
      symbolWidth: 18,
      margin: 4,
      padding: 2,
    },
    tooltip: {
      shared: true,
      formatter: function () {
        const date = Highcharts.dateFormat("%Y-%m-%d", this.x as number);
        let tooltip = `<b>${date}</b><br/>`;
        this.points?.forEach((point: any) => {
          tooltip += `<span style=\"color:${point.color}\">●</span> ${point.series.name}: <b>${point.y}</b><br/>`;
        });
        return tooltip;
      },
      style: { fontSize: "0.95rem" },
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
    navigator: { enabled: false },
    scrollbar: { enabled: false },
    rangeSelector: { enabled: false },
  };

  return (
    <div
      style={{
        padding: "10px 12px",
        background: "#fff",
        borderRadius: "8px",
        boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
        maxWidth: 1000,
        margin: "12px auto",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={{ fontWeight: 600, fontSize: "1rem" }}>{data[0].index_name.toUpperCase()} Market Breadth</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {SMA_OPTIONS.map((opt, idx) => (
            <label key={opt.key} style={{ fontSize: "0.95rem", fontWeight: idx === selectedSMA ? 600 : 400, cursor: "pointer" }}>
              <input
                type="radio"
                name="sma"
                value={String(idx)}
                checked={selectedSMA === idx}
                onChange={e => setSelectedSMA(Number(e.target.value))}
                style={{ marginRight: 2 }}
              />
              {opt.label}
            </label>
          ))}
        </div>
      </div>
      <HighchartsReact
        highcharts={Highcharts}
        options={chartOptions}
      />
    </div>
  );
};

export default MarketBreadthCard;