"use client";

import { CartesianGrid, Line, LineChart, XAxis, YAxis, Tooltip } from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
} from "@/components/ui/chart";
import type { DailyPoint } from "@/lib/api";
import { ChartSkeleton } from "@/components/ui/chart-skeleton";

const PALETTE: Record<string, string> = {
  Sunday: "#ef4444",
  Monday: "#f97316",
  Tuesday: "#eab308",
  Wednesday: "#22c55e",
  Thursday: "#3b82f6",
  Friday: "#8b5cf6",
  Saturday: "#ec4899",
};

function fmtTime(m: number) {
  return `${Math.floor(m / 60).toString().padStart(2, "0")}:${(m % 60).toString().padStart(2, "0")}`;
}

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  const sorted = [...payload].filter(e => e.value != null).sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  return (
    <div className="rounded-lg border bg-card px-3 py-2 text-xs shadow-md max-h-[300px] overflow-y-auto">
      <p className="font-medium mb-1.5">{label}</p>
      <div className="space-y-0.5">
        {sorted.map((entry, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full shrink-0" style={{ background: entry.color }} />
            <span className="text-muted-foreground">{entry.name}:</span>
            <span className="font-medium tabular-nums">{entry.value?.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DayOverlayChart({ data }: { data: DailyPoint[] }) {
  if (!data.length) return <ChartSkeleton height="h-[380px]" label="Loading day comparison..." />;

  const dates = [...new Set(data.map((d) => d.date))].sort();
  const dayNames = new Map<string, string>();
  for (const d of data) dayNames.set(d.date, d.day_of_week);

  const timeMap = new Map<number, Record<string, number | string>>();
  for (const d of data) {
    const mins = d.hour * 60 + d.minute;
    if (!timeMap.has(mins)) timeMap.set(mins, { m: mins, t: fmtTime(mins) });
    timeMap.get(mins)![`${d.day_of_week.slice(0, 3)} ${d.date.slice(5)}`] = d.avg_daily_pct;
  }
  const rows = [...timeMap.values()].sort((a, b) => (a.m as number) - (b.m as number));
  const keys = dates.map((d) => `${dayNames.get(d)?.slice(0, 3)} ${d.slice(5)}`);

  const cfg: ChartConfig = {};
  keys.forEach((k, i) => {
    const dn = dayNames.get(dates[i]) ?? "";
    cfg[k] = { label: k, color: PALETTE[dn] ?? "#94a3b8" };
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Day-over-Day Comparison</CardTitle>
        <CardDescription>Each line is one day, normalized to its peak. Overlapping lines reveal consistent daily rhythms; diverging lines highlight unusual days</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={cfg} className="h-[280px] w-full">
          <LineChart data={rows} margin={{ left: 0, right: 12, top: 8 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="t" tickLine={false} axisLine={false} minTickGap={50} />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(v) => `${v}%`}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip content={<CustomTooltip />} />
            {keys.map((k) => (
              <Line
                key={k}
                type="monotone"
                dataKey={k}
                stroke={cfg[k].color}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
