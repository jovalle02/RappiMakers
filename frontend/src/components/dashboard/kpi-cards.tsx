"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Store, TrendingUp, AlertTriangle, Clock, Loader2 } from "lucide-react";
import type { Stats } from "@/lib/api";

function fmt(n: number) {
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return n.toLocaleString();
}

function MetricCard({
  title,
  value,
  desc,
  icon,
}: {
  title: string;
  value: string;
  desc: string;
  icon: React.ReactNode;
}) {
  return (
    <Card size="sm">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1">
        <CardTitle className="text-xs font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-xl font-bold">{value}</div>
        <p className="text-[11px] text-muted-foreground">{desc}</p>
      </CardContent>
    </Card>
  );
}

export function KpiCards({ stats }: { stats: Stats | null }) {
  if (!stats)
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} size="sm" className="flex items-center justify-center h-[100px]">
            <Loader2 className="size-4 animate-spin text-muted-foreground" />
          </Card>
        ))}
      </div>
    );

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <MetricCard
        title="Peak Availability"
        value={fmt(stats.peak)}
        desc={`Average: ${fmt(stats.avg)}`}
        icon={<Store className="h-4 w-4 text-muted-foreground" />}
      />
      <MetricCard
        title="Data Points"
        value={fmt(stats.total_points)}
        desc={`${stats.total_days} days monitored`}
        icon={<TrendingUp className="h-4 w-4 text-muted-foreground" />}
      />
      <MetricCard
        title="Anomalies"
        value={stats.anomaly_count.toLocaleString()}
        desc={`${((stats.anomaly_count / stats.total_points) * 100).toFixed(1)}% anomaly rate`}
        icon={<AlertTriangle className="h-4 w-4 text-muted-foreground" />}
      />
      <MetricCard
        title="Uptime (8am–10pm)"
        value={`${stats.uptime_pct}%`}
        desc="Above 50% daily capacity"
        icon={<Clock className="h-4 w-4 text-muted-foreground" />}
      />
    </div>
  );
}
