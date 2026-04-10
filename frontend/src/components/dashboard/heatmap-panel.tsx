"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { HeatmapPoint } from "@/lib/api";
import { ChartSkeleton } from "@/components/ui/chart-skeleton";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;
const SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function color(pct: number) {
  if (pct <= 0) return "hsl(0 0% 96%)";
  const a = Math.min(pct / 100, 1);
  return `oklch(${0.9 - a * 0.35} ${a * 0.2} 29)`;
}

export function HeatmapPanel({ data }: { data: HeatmapPoint[] }) {
  if (!data.length) return <ChartSkeleton height="h-[380px]" label="Loading heatmap..." />;

  const map = new Map<string, HeatmapPoint>();
  for (const d of data) map.set(`${d.day_of_week}-${d.hour}`, d);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Weekly Heatmap</CardTitle>
        <CardDescription>Darker cells = higher availability. Look for off-hour dips (maintenance windows) and weekend patterns</CardDescription>
      </CardHeader>
      <CardContent>
        {/* hours */}
        <div className="flex gap-px mb-px pl-10">
          {HOURS.filter((h) => h % 3 === 0).map((h) => (
            <span key={h} className="flex-1 text-center text-[10px] text-muted-foreground">
              {h}h
            </span>
          ))}
        </div>

        {DAYS.map((day, di) => (
          <div key={day} className="flex gap-px mb-px">
            <span className="w-10 shrink-0 text-[11px] text-muted-foreground leading-8">
              {SHORT[di]}
            </span>
            {HOURS.map((hour) => {
              const pt = map.get(`${day}-${hour}`);
              const pct = pt?.avg_daily_pct ?? 0;
              return (
                <div
                  key={hour}
                  title={`${SHORT[di]} ${hour}:00 — ${pct.toFixed(1)}%${pt ? ` (${pt.avg_count.toLocaleString()})` : ""}`}
                  className="flex-1 rounded-[3px]"
                  style={{ background: color(pct), height: 28 }}
                />
              );
            })}
          </div>
        ))}

        <div className="mt-1 flex items-center justify-end gap-1">
          <span className="text-[9px] text-muted-foreground">Low</span>
          {[0, 50, 100].map((p) => (
            <div key={p} className="h-2 w-4 rounded-sm" style={{ background: color(p) }} />
          ))}
          <span className="text-[9px] text-muted-foreground">High</span>
        </div>
      </CardContent>
    </Card>
  );
}
