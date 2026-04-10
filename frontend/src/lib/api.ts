const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export interface DataPoint {
  timestamp: string;
  store_count: number;
  rolling_avg_30m: number;
  daily_pct: number;
  z_score: number;
  is_anomaly: boolean;
}

export interface Stats {
  peak: number;
  avg: number;
  min: number;
  anomaly_count: number;
  total_points: number;
  date_start: string;
  date_end: string;
  total_days: number;
  uptime_pct: number;
}

export interface HeatmapPoint {
  day_of_week: string;
  day_num: number;
  hour: number;
  avg_count: number;
  avg_daily_pct: number;
}

export interface DailyPoint {
  date: string;
  day_of_week: string;
  hour: number;
  minute: number;
  avg_count: number;
  avg_daily_pct: number;
}

export interface AnomalyDensity {
  hour: number;
  anomaly_count: number;
  total_count: number;
  anomaly_pct: number;
}

export interface HourlyStats {
  hour: number;
  avg_count: number;
  min_count: number;
  max_count: number;
  p25: number;
  p75: number;
  std_dev: number;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export const api = {
  stats: () => get<Stats>("/stats"),
  data: (res = 120) => get<DataPoint[]>(`/data?resolution=${res}`),
  heatmap: () => get<HeatmapPoint[]>("/heatmap"),
  daily: () => get<DailyPoint[]>("/daily-comparison"),
  anomalyDensity: () => get<AnomalyDensity[]>("/anomaly-density"),
  hourlyStats: () => get<HourlyStats[]>("/hourly-stats"),
};
