"use client";

import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
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
import type { HourlyStats } from "@/lib/api";
import { ChartSkeleton } from "@/components/ui/chart-skeleton";

const config = {
  avg_count: { label: "Average", color: "var(--chart-1)" },
  range: { label: "P25–P75 range", color: "var(--chart-2)" },
} satisfies ChartConfig;

function fmtNum(n: number) {
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return String(n);
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: HourlyStats & { rangeBottom: number } }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border bg-card px-3 py-2 text-xs shadow-md">
      <p className="font-medium mb-1">
        {d.hour.toString().padStart(2, "0")}:00 –{" "}
        {d.hour.toString().padStart(2, "0")}:59
      </p>
      <div className="space-y-0.5">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full shrink-0" style={{ background: "var(--chart-1)" }} />
          <span className="text-muted-foreground">Average:</span>
          <span className="font-medium tabular-nums">
            {d.avg_count.toLocaleString()}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full shrink-0" style={{ background: "var(--chart-2)" }} />
          <span className="text-muted-foreground">P25–P75:</span>
          <span className="font-medium tabular-nums">
            {d.p25.toLocaleString()} – {d.p75.toLocaleString()}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Min–Max:</span>
          <span className="font-medium tabular-nums">
            {d.min_count.toLocaleString()} – {d.max_count.toLocaleString()}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Std Dev:</span>
          <span className="font-medium tabular-nums">
            {d.std_dev.toLocaleString()}
          </span>
        </div>
      </div>
    </div>
  );
}

export function DistributionChart({ data }: { data: HourlyStats[] }) {
  if (!data.length) return <ChartSkeleton height="h-[380px]" label="Loading distribution..." />;

  // For the area range, we use p25 as base and stack (p75 - p25) on top
  const chartData = data.map((d) => ({
    ...d,
    rangeBottom: d.p25,
    rangeSpan: d.p75 - d.p25,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Hourly Store Distribution</CardTitle>
        <CardDescription>
          Average store count per hour with interquartile range (P25–P75 shaded). Wide bands mean high volatility at that hour
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={config} className="h-[280px] w-full">
          <ComposedChart
            data={chartData}
            margin={{ left: 0, right: 12, top: 12, bottom: 4 }}
          >
            <defs>
              <linearGradient id="rangeGrad" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor="var(--color-range)"
                  stopOpacity={0.25}
                />
                <stop
                  offset="100%"
                  stopColor="var(--color-range)"
                  stopOpacity={0.05}
                />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="hour"
              tickLine={false}
              axisLine={false}
              tickFormatter={(h) => `${h}h`}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tickFormatter={fmtNum}
              width={48}
            />
            <Tooltip content={<CustomTooltip />} />
            <ChartLegend content={<ChartLegendContent />} />
            {/* IQR range band: stacked area (invisible base + visible span) */}
            <Area
              type="monotone"
              dataKey="rangeBottom"
              stackId="range"
              stroke="none"
              fill="none"
              legendType="none"
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="rangeSpan"
              stackId="range"
              stroke="var(--color-range)"
              strokeWidth={1}
              strokeOpacity={0.4}
              fill="url(#rangeGrad)"
              isAnimationActive={false}
              name="P25–P75 range"
            />
            {/* Average line */}
            <Line
              type="monotone"
              dataKey="avg_count"
              stroke="var(--color-avg_count)"
              strokeWidth={2}
              dot={{ r: 3, fill: "var(--color-avg_count)" }}
              isAnimationActive={false}
              name="Average"
            />
          </ComposedChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
