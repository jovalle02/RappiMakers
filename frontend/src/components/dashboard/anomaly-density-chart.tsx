"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis, Tooltip, Cell } from "recharts";
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
import type { AnomalyDensity } from "@/lib/api";
import { ChartSkeleton } from "@/components/ui/chart-skeleton";

const config = {
  anomaly_count: { label: "Anomalies", color: "var(--chart-1)" },
} satisfies ChartConfig;

// Rappi orange palette, darker = more anomalies
function barColor(count: number, max: number) {
  if (max === 0) return "#FDDCB5";
  const ratio = count / max;
  if (ratio > 0.7) return "#FC4C02";  // Rappi primary orange
  if (ratio > 0.45) return "#FF6D2E";  // strong orange
  if (ratio > 0.25) return "#FF9A5C";  // medium orange
  if (ratio > 0.1) return "#FFB885";   // light orange
  return "#FDDCB5";                    // pale orange
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: AnomalyDensity }>;
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
          <span className="text-muted-foreground">Anomalies:</span>
          <span className="font-medium tabular-nums">{d.anomaly_count}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Total points:</span>
          <span className="font-medium tabular-nums">
            {d.total_count.toLocaleString()}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Anomaly rate:</span>
          <span className="font-medium tabular-nums">{d.anomaly_pct}%</span>
        </div>
      </div>
    </div>
  );
}

export function AnomalyDensityChart({ data }: { data: AnomalyDensity[] }) {
  if (!data.length) return <ChartSkeleton height="h-[380px]" label="Loading anomaly density..." />;

  const max = Math.max(...data.map((d) => d.anomaly_count));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Anomaly Density by Hour</CardTitle>
        <CardDescription>
          When do anomalies (|z-score| &gt; 2) concentrate? Spikes reveal
          systematic instability at specific hours. Darker bars flag the worst
          offenders
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={config} className="h-[280px] w-full">
          <BarChart
            data={data}
            margin={{ left: 0, right: 12, top: 12, bottom: 4 }}
          >
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="hour"
              tickLine={false}
              axisLine={false}
              tickFormatter={(h) => `${h}h`}
            />
            <YAxis tickLine={false} axisLine={false} width={40} />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--muted)", opacity: 0.3 }} />
            <Bar dataKey="anomaly_count" radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {data.map((entry, i) => (
                <Cell key={entry.hour} fill={barColor(entry.anomaly_count, max)} />
              ))}
            </Bar>
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
