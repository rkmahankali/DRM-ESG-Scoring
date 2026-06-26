const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  scoreCompany: (body: unknown) =>
    request<ScoreResponse>("/score", { method: "POST", body: JSON.stringify(body) }),

  getHistory: (companyId: string) =>
    request<HistoryResponse>(`/score/${companyId}/history`),

  getAuditTrail: (scoreId: string) =>
    request<AuditResponse>(`/audit/${scoreId}`),

  getMetrics: (sector = "*") =>
    request<MetricsResponse>(`/metrics?sector=${sector}`),

  getOntology: () =>
    request<OntologyResponse>("/ontology/pillars"),

  ingestDocument: (body: unknown) =>
    request<IngestResult>("/ingest/document", { method: "POST", body: JSON.stringify(body) }),

  ingestQuestionnaire: (body: unknown) =>
    request<IngestResult>("/ingest/questionnaire", { method: "POST", body: JSON.stringify(body) }),

  getSupplyChainRisk: (companyId: string) =>
    request<SupplyChainRisk>(`/graph/supply-chain/${companyId}`),
};

// --- Types ---

export interface PillarScore {
  pillar: "E" | "S" | "G";
  score: number;
  confidence: number;
  greenwash_risk: number;
  metric_scores: MetricScore[];
}

export interface MetricScore {
  metric_id: string;
  metric_name: string;
  pillar: string;
  category: string;
  score: number;
  confidence: number;
  data_coverage: number;
  peer_percentile: number | null;
  outcome_based: boolean;
}

export interface ESGScore {
  id: string;
  company_id: string;
  composite_score: number;
  pillar_scores: Record<string, PillarScore>;
  confidence: number;
  data_coverage: number;
  greenwash_risk: number;
  scored_at: string;
  evidence_count: number;
  audit_log_id: string;
}

export interface GreenwashAlert {
  id: string;
  pillar: string;
  metric_id: string;
  claim: string;
  counter_evidence: string;
  divergence_score: number;
}

export interface ScoreResponse {
  score: ESGScore;
  alerts: GreenwashAlert[];
  audit_id: string;
}

export interface HistoryResponse {
  company_id: string;
  history: AuditEntry[];
}

export interface AuditEntry {
  id: string;
  event_type: string;
  score_value: number;
  confidence: number;
  greenwash_risk: number;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface AuditResponse {
  score_id: string;
  audit_trail: AuditEntry[];
}

export interface MetricsResponse {
  sector: string;
  count: number;
  metrics: MetricDef[];
}

export interface MetricDef {
  id: string;
  name: string;
  pillar: string;
  category: string;
  unit: string;
  outcome_based: boolean;
  gri: string | null;
  sfdr_pai: string | null;
  csrd: string | null;
}

export interface OntologyResponse {
  [pillar: string]: {
    name: string;
    weight: number;
    categories: { id: string; name: string; weight: number; metric_count: number }[];
  };
}

export interface IngestResult {
  score_id: string;
  audit_id: string;
  composite_score: number;
  alert_count: number;
}

export interface SupplyChainRisk {
  company_id: string;
  supply_chain_risks: { supplier_id: string; name: string; score: number; greenwash_risk: number }[];
}
