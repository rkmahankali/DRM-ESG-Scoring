import { RadialBarChart, RadialBar, ResponsiveContainer, PolarAngleAxis } from "recharts";

interface Props {
  score: number;
  label: string;
  size?: number;
}

function scoreColor(s: number) {
  if (s >= 70) return "#22c55e";
  if (s >= 45) return "#f59e0b";
  return "#ef4444";
}

export function ScoreGauge({ score, label, size = 160 }: Props) {
  const data = [{ value: score, fill: scoreColor(score) }];
  return (
    <div className="flex flex-col items-center gap-1">
      <div style={{ width: size, height: size }} className="relative">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            innerRadius="70%"
            outerRadius="100%"
            data={data}
            startAngle={180}
            endAngle={0}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar dataKey="value" cornerRadius={6} background={{ fill: "#e5e7eb" }} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pt-6">
          <span className="text-3xl font-bold text-gray-900">{score.toFixed(0)}</span>
          <span className="text-xs text-gray-500">/ 100</span>
        </div>
      </div>
      <span className="text-sm font-medium text-gray-700">{label}</span>
    </div>
  );
}
