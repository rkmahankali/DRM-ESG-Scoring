"""
GraphRAG Synthesizer — turns retrieved graph context into structured
narrative explanations.

Two modes:
  1. Template-based (default, zero dependencies): deterministic, fast, always available.
  2. LLM-enhanced (optional): uses Claude claude-sonnet-4-6 via Anthropic API when
     ANTHROPIC_API_KEY is set, generating richer analysis from the same context.

Both modes return the same ExplanationResult structure.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from src.rag.graph_retriever import RetrievedContext
from src.semantic.concept_layer import CONFLICTS_WITH, REINFORCES, SIMILAR_TO

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY","")


@dataclass
class ExplanationResult:
    metric_id: str
    metric_name: str
    score: float
    grade: str
    headline: str                     # one-line summary
    narrative: str                    # 2-3 paragraph explanation
    evidence_quality: str             # "High" / "Medium" / "Low"
    evidence_summary: str
    peer_insight: str
    regulatory_insight: str
    risk_flags: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    confidence_note: str = ""
    generated_by: str = "template"   # "template" | "llm"


GRADE_MAP = [(80,"A"),(65,"B"),(50,"C"),(35,"D"),(0,"F")]
REL_LABELS = {SIMILAR_TO:"similar to", REINFORCES:"reinforces", CONFLICTS_WITH:"conflicts with"}
QUALITY_THRESHOLDS = {"High":0.80, "Medium":0.60, "Low":0.0}


def _grade(score: float) -> str:
    for threshold, grade in GRADE_MAP:
        if score >= threshold:
            return grade
    return "F"


def _quality_label(avg_conf: float, has_verified: bool) -> str:
    if avg_conf >= 0.80 and has_verified:
        return "High"
    if avg_conf >= 0.60:
        return "Medium"
    return "Low"


class Synthesizer:

    def explain(self, ctx: RetrievedContext, use_llm: bool = True) -> ExplanationResult:
        if use_llm and ANTHROPIC_API_KEY:
            try:
                return self._llm_explain(ctx)
            except Exception:
                pass
        return self._template_explain(ctx)

    # ── template synthesis ──────────────────────────────────────────────────

    def _template_explain(self, ctx: RetrievedContext) -> ExplanationResult:
        grade = _grade(ctx.metric_score)
        pillar_long = {"E":"Environmental","S":"Social","G":"Governance"}.get(ctx.pillar, ctx.pillar)

        # Evidence quality
        verified = [e for e in ctx.evidence_items if e.get("verified")]
        unverified = [e for e in ctx.evidence_items if not e.get("verified")]
        avg_conf = (sum(e.get("confidence",0) for e in ctx.evidence_items)/len(ctx.evidence_items)
                    if ctx.evidence_items else 0)
        eq = _quality_label(avg_conf, bool(verified))

        # Headline
        direction = "strong" if ctx.metric_score >= 70 else ("moderate" if ctx.metric_score >= 50 else "weak")
        headline = (f"{ctx.company_name} shows {direction} {pillar_long} performance on "
                    f"{ctx.metric_id} ({ctx.metric_name}) — scored {ctx.metric_score}/100 ({grade})")

        # Evidence summary paragraph
        src_types = list({e.get("source","") for e in ctx.evidence_items})
        ev_para = ""
        if ctx.evidence_items:
            v_count = len(verified); sr_count = len(unverified)
            ev_para = (
                f"Score is backed by {len(ctx.evidence_items)} evidence item(s) "
                f"from {', '.join(src_types)} "
                f"({v_count} verified / {sr_count} self-reported), "
                f"with an average confidence of {round(avg_conf*100)}%. "
            )
            if ctx.greenwash_conflict:
                gw = ctx.greenwash_conflict
                ev_para += (
                    f"⚠ Self-reported value ({round(gw['self_reported_avg']*100,1)}%) diverges "
                    f"from measured outcome ({round(gw['measured_avg']*100,1)}%) "
                    f"by {gw['divergence_pct']}% — "
                    f"{'this triggers a greenwash alert.' if gw['is_greenwash_alert'] else 'worth monitoring.'}"
                )
            else:
                ev_para += "Evidence sources are internally consistent — no greenwash divergence detected."
        else:
            ev_para = "No direct evidence items were found for this metric in this scoring run. Score is inferred from related metrics or defaults to zero."

        # Peer insight
        peer_para = ""
        if ctx.peer_scores:
            avg_peer = sum(p["score"] for p in ctx.peer_scores)/len(ctx.peer_scores)
            vs = "above" if ctx.metric_score > avg_peer else ("equal to" if ctx.metric_score == avg_peer else "below")
            pct_str = f" (ranked {ctx.peer_percentile}th percentile)" if ctx.peer_percentile else ""
            peers_named = ", ".join(f"{p['company']} ({p['score']})" for p in ctx.peer_scores[:3])
            peer_para = (
                f"{ctx.company_name}'s {ctx.metric_id} score of {ctx.metric_score} is {vs} "
                f"the portfolio average of {round(avg_peer,1)}{pct_str}. "
                f"Comparable companies: {peers_named}."
            )
        else:
            peer_para = "No peer companies have been scored yet — add more companies to enable benchmarking."

        # Related metrics insight
        reinforcers = [r for r in ctx.related_metrics if r["rel_type"]==REINFORCES and r["score"] is not None]
        conflicts   = [r for r in ctx.related_metrics if r["rel_type"]==CONFLICTS_WITH and r["score"] is not None]
        rel_note = ""
        if reinforcers:
            good = [r for r in reinforcers if r["score"] and r["score"]>=65]
            bad  = [r for r in reinforcers if r["score"] and r["score"]<50]
            if good:
                rel_note += f"Strong scores on reinforcing metrics "
                rel_note += ", ".join(f"{r['metric_id']} ({r['score']})" for r in good[:2])
                rel_note += " lend credibility to this result. "
            if bad:
                rel_note += f"However, low scores on "
                rel_note += ", ".join(f"{r['metric_id']} ({r['score']})" for r in bad[:2])
                rel_note += " create tension and warrant investigation. "
        if conflicts and ctx.greenwash_conflict:
            rel_note += (f"The CONFLICTS_WITH relationship to "
                         f"{', '.join(r['metric_id'] for r in conflicts[:2])} "
                         f"corroborates the evidence divergence flagged above.")

        narrative = f"{ev_para}\n\n{peer_para}"
        if rel_note:
            narrative += f"\n\n{rel_note}"
        if ctx.outcome_based:
            narrative += "\n\nThis metric is classified as **outcome-based**: it measures real-world impact, not just policy commitment, and carries a 1.2× premium in the scoring engine."
        else:
            narrative += "\n\nThis metric measures **policy or disclosure** (not direct outcomes). Upgrading to outcome-based evidence would increase its weighting and score validity."

        # Regulatory insight
        reg = ctx.regulatory
        reg_para = ""
        if reg:
            refs = []
            if reg.get("gri"):      refs.append(f"GRI {', '.join(reg['gri'][:2])}")
            if reg.get("sfdr_pai"): refs.append(f"SFDR PAI {', '.join(reg['sfdr_pai'][:2])}")
            if reg.get("csrd_esrs"):refs.append(f"CSRD {reg['csrd_esrs'][0]}")
            if reg.get("issb_ifrs"):refs.append(f"ISSB {reg['issb_ifrs'][0][:20]}")
            mand = reg.get("mandatory_jurisdictions",[])
            reg_para = (
                f"Metric {ctx.metric_id} is referenced in: {', '.join(refs)}. "
                f"Mandatory disclosure required in: {', '.join(mand) if mand else 'no mandatory jurisdictions yet'}. "
                f"Material under double-materiality lens for: {ctx.company_sector}."
            )
            if ctx.materiality >= 0.9:
                reg_para += f" Materiality rating: HIGH ({round(ctx.materiality*100)}%) — this is a priority metric for this sector."
            elif ctx.materiality >= 0.7:
                reg_para += f" Materiality rating: MEDIUM ({round(ctx.materiality*100)}%)."
            else:
                reg_para += f" Materiality rating: LOW ({round(ctx.materiality*100)}%) for this sector."
        else:
            reg_para = "No regulatory mapping found for this metric."

        # Risk flags
        risks = []
        opps  = []
        if ctx.metric_score < 50:
            risks.append(f"Score {ctx.metric_score} is below threshold — regulatory scrutiny likely for {ctx.metric_id}")
        if ctx.greenwash_conflict and ctx.greenwash_conflict["is_greenwash_alert"]:
            risks.append(f"Greenwash risk: {ctx.greenwash_conflict['divergence_pct']}% divergence between self-reported and measured evidence")
        if avg_conf < 0.60:
            risks.append(f"Low evidence confidence ({round(avg_conf*100)}%) — consider independent verification")
        if not verified:
            risks.append("All evidence is self-reported — third-party verification would strengthen this score")
        if ctx.metric_score >= 80:
            opps.append(f"Score {ctx.metric_score} qualifies for SFDR Art. 9 'sustainable investment' designation")
        if ctx.materiality >= 0.9 and ctx.metric_score >= 70:
            opps.append(f"High-materiality metric with strong score — investible for ESG-mandated funds")
        if reinforcers and all(r.get("score",0)>=70 for r in reinforcers[:2]):
            opps.append("Consistent high scores across reinforcing metrics supports narrative coherence")

        return ExplanationResult(
            metric_id=ctx.metric_id,
            metric_name=ctx.metric_name,
            score=ctx.metric_score,
            grade=grade,
            headline=headline,
            narrative=narrative,
            evidence_quality=eq,
            evidence_summary=ev_para,
            peer_insight=peer_para,
            regulatory_insight=reg_para,
            risk_flags=risks,
            opportunities=opps,
            confidence_note=f"Average evidence confidence: {round(avg_conf*100)}% across {len(ctx.evidence_items)} items",
            generated_by="template",
        )

    # ── LLM synthesis ────────────────────────────────────────────────────────

    def _llm_explain(self, ctx: RetrievedContext) -> ExplanationResult:
        """Use Claude claude-sonnet-4-6 to generate richer analysis."""
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        # Build concise context for LLM
        ev_lines = "\n".join(
            f"  - [{e['type'].upper()}] {e['source']}: "
            f"norm_value={e['value']}, conf={round((e['confidence'] or 0)*100)}%, "
            f"verified={e['verified']}"
            for e in ctx.evidence_items
        ) or "  (none)"

        peer_lines = "\n".join(
            f"  - {p['company']} ({p['sector']}): {p['score']}"
            for p in ctx.peer_scores[:4]
        ) or "  (no peers scored yet)"

        rel_lines = "\n".join(
            f"  - {r['metric_id']} [{r['rel_type']}] score={r['score']} — {r['description']}"
            for r in ctx.related_metrics[:5]
        ) or "  (none)"

        reg = ctx.regulatory
        reg_summary = (
            f"GRI {', '.join(reg.get('gri',[]))[:60]} | "
            f"SFDR PAI {', '.join(reg.get('sfdr_pai',[]))[:20]} | "
            f"CSRD {', '.join(reg.get('csrd_esrs',[]))[:40]}"
        ) if reg else "(no regulatory mapping)"

        gw_note = ""
        if ctx.greenwash_conflict:
            g = ctx.greenwash_conflict
            gw_note = (f"⚠ GREENWASH SIGNAL: self-reported avg {round(g['self_reported_avg']*100,1)}% "
                       f"vs measured {round(g['measured_avg']*100,1)}% "
                       f"→ {g['divergence_pct']}% divergence "
                       f"{'(ALERT)' if g['is_greenwash_alert'] else '(monitor)'}")

        prompt = f"""You are an expert ESG analyst for private markets. Provide a concise, professional
3-paragraph explanation of the following metric score, using exactly the context provided.

COMPANY: {ctx.company_name} | SECTOR: {ctx.company_sector}
METRIC: {ctx.metric_id} — {ctx.metric_name}
SCORE: {ctx.metric_score}/100 ({_grade(ctx.metric_score)}) | PILLAR: {ctx.pillar} | OUTCOME-BASED: {ctx.outcome_based}
MATERIALITY FOR SECTOR: {round(ctx.materiality*100)}%

EVIDENCE ITEMS:
{ev_lines}
{gw_note}

PEER PORTFOLIO COMPARISON (same metric):
{peer_lines}
{"Peer percentile: " + str(ctx.peer_percentile) + "th" if ctx.peer_percentile else ""}

RELATED METRICS (semantic relationships):
{rel_lines}

REGULATORY REQUIREMENTS:
{reg_summary}

Write:
Para 1 (Evidence Assessment): Quality and consistency of evidence. Mention greenwash risk if present.
Para 2 (Performance Context): How this score compares to peers and whether reinforcing/conflicting metrics corroborate it.
Para 3 (Regulatory & Investment Implications): Compliance status, materiality, and what this means for an investor.

Keep each paragraph to 3-4 sentences. Be specific, cite numbers from the context. Avoid generic ESG boilerplate.
"""
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role":"user","content":prompt}],
        )
        narrative = resp.content[0].text.strip()

        # Use template for structured fields, override narrative with LLM
        result = self._template_explain(ctx)
        result.narrative = narrative
        result.generated_by = "llm"
        return result
