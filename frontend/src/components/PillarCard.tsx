import type { PillarScore } from "../lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const PILLAR_LABELS: Record<string, string> = {
  E: "Environmental",
  S: "Social",
  G: "Governance",
};

const PILLAR_COLORS: Record<string, string> = {
  E: "#22c55e",
  S: "#3b82f6",
  G: "#8b5cf6",
};

interface Props {
  pillarKey: string;
  pillar: PillarScore;
}

export function PillarCard({ pillarKey, pillar }: Props) {
  const chartData = pillar.metric_scores
    .filter((m) => m.score > 0)
    .map((m) => ({ name: m.metric_id, score: Math.round(m.score), outcome: m.outcome_based }));

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div>
          <span className="text-xs font-bold text-gray-400 tracking-widest uppercase">
            {pillarKey}
          </span>
          <h3 className="text-lg font-semibold text-gray-900">{PILLAR_LABELS[pillarKey]}</h3>
        </div>
        <div className="text-right">
          <div
            className="text-3xl font-bold"
            style={{ color: PILLAR_COLORS[pillarKey] }}
          >
            {pillar.score.toFixed(0)}
          </div>
          <div className="text-xs text-gray-400">
            {(pillar.confidence * 100).toFixed(0)}% confidence
          </div>
        </div>
      </div>

      {pillar.greenwash_risk > 0.25 && (
        <div className="mb-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700 font-medium">
          ⚠ Greenwash risk: {(pillar.greenwash_risk * 100).toFixed(0)}%
        </div>
      )}

      {chartData.length > 0 && (
        <div className="mt-2" style={{ height: 120 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 8 }}>
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={36} />
              <Tooltip
                formatter={(v: number) => [`${v}`, "Score"]}
                labelFormatter={(l) => `Metric: ${l}`}
              />
              <Bar dataKey="score" radius={3}>
                {chartData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.outcome ? PILLAR_COLORS[pillarKey] : "#d1d5db"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="mt-2 text-xs text-gray-400">
        <span className="inline-block w-3 h-3 rounded-sm mr-1" style={{ background: PILLAR_COLORS[pillarKey] }} />
        Outcome-based &nbsp;
        <span className="inline-block w-3 h-3 rounded-sm mr-1 bg-gray-300" />
        Policy/disclosure
      </p>
    </div>
  );
}
