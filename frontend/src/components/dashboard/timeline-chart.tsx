"use client";

import { useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis, Tooltip } from "recharts";
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
  ChartLegend,
  ChartLegendContent,
} from "@/components/ui/chart";
import type { DataPoint } from "@/lib/api";
import { ChartSkeleton } from "@/components/ui/chart-skeleton";

const config = {
  store_count: { label: "Visible Stores", color: "var(--chart-1)" },
  rolling_avg_30m: { label: "30m Average", color: "var(--chart-3)" },
} satisfies ChartConfig;

function fmtNum(n: number) {
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return String(n);
}

function fmtDate(ts: string) {
  return new Date(ts).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function fmtDateTime(ts: string) {
  const d = new Date(ts);
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ dataKey: string; value: number; color: string; payload: DataPoint }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const date = new Date(d.timestamp);
  return (
    <div className="rounded-lg border bg-card px-3 py-2 text-xs shadow-md">
      <p className="font-medium mb-1.5">
        {date.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
        {" "}
        {date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })}
      </p>
      <div className="space-y-0.5">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full shrink-0" style={{ background: "var(--chart-1)" }} />
          <span className="text-muted-foreground">Visible Stores:</span>
          <span className="font-medium tabular-nums">{d.store_count.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full shrink-0" style={{ background: "var(--chart-3)" }} />
          <span className="text-muted-foreground">30m Average:</span>
          <span className="font-medium tabular-nums">{d.rolling_avg_30m.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Daily %:</span>
          <span className="font-medium tabular-nums">{d.daily_pct}%</span>
        </div>
      </div>
      {d.is_anomaly && (
        <p className="mt-1.5 pt-1.5 border-t text-destructive font-medium">
          Anomaly (z-score: {d.z_score})
        </p>
      )}
    </div>
  );
}

export function TimelineChart({ data }: { data: DataPoint[] }) {
  const [selected, setSelected] = useState<string>("all");

  const dates = useMemo(
    () => [...new Set(data.map((d) => d.timestamp.split("T")[0]))].sort(),
    [data],
  );

  const filteredData = useMemo(
    () => selected === "all" ? data : data.filter((d) => d.timestamp.startsWith(selected)),
    [data, selected],
  );

  if (!data.length) return <ChartSkeleton height="h-[440px]" label="Loading timeline..." />;

  const isSingleDay = selected !== "all";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Store Availability Timeline</CardTitle>
        <CardDescription>
          {filteredData.length.toLocaleString()} observations · Click a day below to zoom in, or view all
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Day filter buttons */}
        <div className="flex gap-1.5 flex-wrap">
          <button
            onClick={() => setSelected("all")}
            className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
              selected === "all"
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-muted/50 text-muted-foreground border-transparent hover:bg-muted"
            }`}
          >
            All days
          </button>
          {dates.map((date) => {
            const d = new Date(date + "T12:00:00");
            const label = d.toLocaleDateString("en-US", {
              weekday: "short",
              month: "short",
              day: "numeric",
            });
            return (
              <button
                key={date}
                onClick={() => setSelected(date)}
                className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                  selected === date
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-muted/50 text-muted-foreground border-transparent hover:bg-muted"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        <ChartContainer config={config} className="h-[320px] w-full">
          <AreaChart data={filteredData} margin={{ left: 0, right: 12, top: 12, bottom: 4 }}>
            <defs>
              <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-store_count)" stopOpacity={0.15} />
                <stop offset="100%" stopColor="var(--color-store_count)" stopOpacity={0.01} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="timestamp"
              tickLine={false}
              axisLine={false}
              tickFormatter={isSingleDay ? fmtDateTime : fmtDate}
              minTickGap={50}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tickFormatter={fmtNum}
              width={48}
            />
            <Tooltip content={<CustomTooltip />} />
            <ChartLegend content={<ChartLegendContent />} />
            <Area
              type="monotone"
              dataKey="store_count"
              stroke="var(--color-store_count)"
              fill="url(#grad)"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="rolling_avg_30m"
              stroke="var(--color-rolling_avg_30m)"
              fill="none"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              strokeOpacity={0.5}
              dot={false}
              isAnimationActive={false}
            />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
