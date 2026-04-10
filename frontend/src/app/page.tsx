"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { api } from "@/lib/api";
import type { Stats, DataPoint, HeatmapPoint, DailyPoint, AnomalyDensity, HourlyStats } from "@/lib/api";
import { KpiCards } from "@/components/dashboard/kpi-cards";
import { TimelineChart } from "@/components/dashboard/timeline-chart";
import { HeatmapPanel } from "@/components/dashboard/heatmap-panel";
import { DayOverlayChart } from "@/components/dashboard/day-overlay-chart";
import { AnomalyDensityChart } from "@/components/dashboard/anomaly-density-chart";
import { DistributionChart } from "@/components/dashboard/distribution-chart";
import { ChatPanel, ChatTrigger } from "@/components/chat/chat-panel";

export default function Page() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [data, setData] = useState<DataPoint[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapPoint[]>([]);
  const [daily, setDaily] = useState<DailyPoint[]>([]);
  const [anomalyDensity, setAnomalyDensity] = useState<AnomalyDensity[]>([]);
  const [hourlyStats, setHourlyStats] = useState<HourlyStats[]>([]);
  const [chatOpen, setChatOpen] = useState(false);

  useEffect(() => {
    api.stats().then(setStats).catch(console.error);
    api.data(120).then(setData).catch(console.error);
    api.heatmap().then(setHeatmap).catch(console.error);
    api.daily().then(setDaily).catch(console.error);
    api.anomalyDensity().then(setAnomalyDensity).catch(console.error);
    api.hourlyStats().then(setHourlyStats).catch(console.error);
  }, []);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className="border-b shrink-0">
        <div className="mx-auto flex h-14 items-center px-6">
          <div className="flex items-center gap-3">
            <Image
              src="/rappi-logo.png"
              alt="Rappi"
              width={110}
              height={38}
              className="h-9 w-auto"
            />
          </div>
          <div className="ml-auto flex items-center gap-4">
            <ChatTrigger onClick={() => setChatOpen(true)} />
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <main className="flex-1 min-w-0 overflow-y-auto px-6 py-3 space-y-3">
          <KpiCards stats={stats} />
          <TimelineChart data={data} />
          <div className="grid gap-3 lg:grid-cols-2">
            <HeatmapPanel data={heatmap} />
            <DayOverlayChart data={daily} />
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <DistributionChart data={hourlyStats} />
            <AnomalyDensityChart data={anomalyDensity} />
          </div>
        </main>

        <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
      </div>
    </div>
  );
}
