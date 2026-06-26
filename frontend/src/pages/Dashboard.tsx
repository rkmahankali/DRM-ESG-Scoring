import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { ScoreGauge } from "../components/ScoreGauge";
import { PillarCard } from "../components/PillarCard";

const DEMO_PAYLOAD = {
  company: {
    id: "demo-co-001",
    name: "Acme Private Co.",
    jurisdiction: "GB",
    sector: "*",
    is_listed: false,
  },
  evidence: [
    { company_id: "demo-co-001", metric_id: "E1.1", source: "api_feed", evidence_type: "quantitative", normalized_value: 0.72, confidence: 0.90, verified: true },
    { company_id: "demo-co-001", metric_id: "E2.1", source: "api_feed", evidence_type: "quantitative", normalized_value: 0.65, confidence: 0.88, verified: true },
    { company_id: "demo-co-001", metric_id: "S1.1", source: "questionnaire", evidence_type: "self_reported", normalized_value: 0.80, confidence: 0.70, verified: false },
    { company_id: "demo-co-001", metric_id: "S1.2", source: "questionnaire", evidence_type: "self_reported", normalized_value: 0.60, confidence: 0.65, verified: false },
    { company_id: "demo-co-001", metric_id: "G1.2", source: "regulatory_filing", evidence_type: "certified", normalized_value: 0.55, confidence: 0.95, verified: true },
    { company_id: "demo-co-001", metric_id: "G2.2", source: "api_feed", evidence_type: "quantitative", normalized_value: 0.90, confidence: 0.92, verified: true },
    // Greenwash signal: self-reported high, measured low
    { company_id: "demo-co-001", metric_id: "E1.3", source: "questionnaire", evidence_type: "self_reported", normalized_value: 0.92, confidence: 0.60, verified: false },
    { company_id: "demo-co-001", metric_id: "E1.3", source: "api_feed", evidence_type: "quantitative", normalized_value: 0.30, confidence: 0.94, verified: true },
  ],
};

export default function Dashboard() {
  const [triggered, setTriggered] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["demo-score"],
    queryFn: () => api.scoreCompany(DEMO_PAYLOAD),
    enabled: triggered,
    staleTime: Infinity,
  });

  const score = data?.score;
  const alerts = data?.alerts ?? [];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-8 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Horison ESG</h1>
          <p className="text-xs text-gray-400">Private Markets · Trustworthy · Auditable</p>
        </div>
        <button
          onClick={() => { setTriggered(true); refetch(); }}
          className="px-5 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-sm font-semibold transition-colors"
        >
          {isLoading ? "Scoring…" : "Run Demo Score"}
        </button>
      </header>

      <main className="max-w-6xl mx-auto px-8 py-8">
        {!triggered && (
          <div className="text-center py-24 text-gray-400">
            <p className="text-lg font-medium">Click "Run Demo Score" to see Acme Private Co. scored</p>
            <p className="text-sm mt-1">Outcome-based · Fully auditable · Greenwash detection included</p>
          </div>
        )}

        {isError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
            API not reachable — start the backend with <code className="font-mono">uvicorn src.api.main:app --reload</code>
          </div>
        )}

        {score && (
          <>
            {/* Composite gauge row */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm mb-6">
              <div className="flex flex-wrap items-center gap-10">
                <ScoreGauge score={score.composite_score} label="ESG Composite" size={180} />
                <div className="flex gap-8">
                  {Object.entries(score.pillar_scores).map(([k, ps]) => (
                    <ScoreGauge key={k} score={ps.score} label={k === "E" ? "Environmental" : k === "S" ? "Social" : "Governance"} size={120} />
                  ))}
                </div>
                <div className="ml-auto text-right text-sm text-gray-500 space-y-1">
                  <div>Confidence: <strong>{(score.confidence * 100).toFixed(0)}%</strong></div>
                  <div>Data coverage: <strong>{(score.data_coverage * 100).toFixed(0)}%</strong></div>
                  <div>Evidence items: <strong>{score.evidence_count}</strong></div>
                  <div className="text-xs text-gray-400 font-mono mt-2">audit: {score.audit_log_id?.slice(0, 8)}…</div>
                </div>
              </div>
            </div>

            {/* Greenwash alerts */}
            {alerts.length > 0 && (
              <div className="mb-6 space-y-2">
                <h2 className="text-sm font-bold text-amber-700 uppercase tracking-wider">⚠ Greenwash Alerts</h2>
                {alerts.map((a) => (
                  <div key={a.id} className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm">
                    <span className="font-semibold text-amber-800">{a.metric_id}</span>
                    <span className="text-amber-600 ml-2">{a.claim}</span>
                    <span className="text-gray-500 mx-2">→</span>
                    <span className="text-red-600">{a.counter_evidence}</span>
                    <span className="ml-3 text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                      divergence {(a.divergence_score * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Pillar cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {Object.entries(score.pillar_scores).map(([k, ps]) => (
                <PillarCard key={k} pillarKey={k} pillar={ps} />
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
