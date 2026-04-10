import { Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";

export function ChartSkeleton({ height = "h-[380px]", label = "Loading chart..." }: { height?: string; label?: string }) {
  return (
    <Card className={`${height} flex items-center justify-center`}>
      <div className="flex flex-col items-center gap-2 text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
        <span className="text-xs">{label}</span>
      </div>
    </Card>
  );
}
