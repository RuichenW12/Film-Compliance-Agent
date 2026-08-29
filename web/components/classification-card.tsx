"use client";

import type { Ref } from "react";

import { PolicyVerificationBanner } from "@/components/policy-verification-banner";
import type { PolicyVerificationStatus } from "@/lib/api";
import { format, t } from "@/lib/i18n";

export interface ClassifyResult {
  classification: {
    form_type: string;
    tier: string;
    tier_provisional: boolean;
    special_subject_hit: boolean;
    co_review_required: boolean;
    matched_rules: { rule_id: string; quote: string }[];
    policy_snapshot_version: string;
    policy_verification_status: PolicyVerificationStatus;
    pending_flags: string[];
    evidence_refs: { snapshot_version: string; clause_id: string }[];
    filing_route: {
      authority: string;
      pre_shoot_filing: string;
      content_review: string;
      result_document: string;
      platform_self_review: boolean;
      blocks_release_until_granted: boolean;
      clause_refs: string[];
    } | null;
  } | null;
  exit: { kind: string; obligations: string[]; card_key: string } | null;
  roadmap_preview: { template?: string } | null;
  state: string;
}

/**
 * Flags that change what a creator should do, in the order they matter.
 *
 * `script_verify` is deliberately absent: it marks the script pre-check as the
 * next stage, which the card already says in its own words. Showing it here too
 * would say the same thing twice, once in English and once as a raw key.
 */
const SPEAKABLE_FLAGS = [
  "human_review",
  "filing_due_before_shooting",
  "clause_not_yet_in_force",
  "threshold_boundary_disputed",
  "budget_unknown",
  "thresholds_unavailable",
  "amount_required",
  "amount_official",
  "subject_semantic_check_pending",
  "edge_phrase_check_pending",
  "rules_expert_pending",
];

/** Flags that should stop someone, rather than merely inform them. */
const LOUD_FLAGS = [
  "human_review",
  "filing_due_before_shooting",
  "clause_not_yet_in_force",
  "threshold_boundary_disputed",
];

/**
 * What the classification means, in the order a creator needs it.
 *
 * The card this replaces opened with `micro_drama`, `Tier T3`, a clause id and
 * a roadmap template name, and closed with the project's internal state. Every
 * one of those is true, and none answers "so what do I do?" — while the filing
 * route, the one part that does, sat at the bottom.
 *
 * So: the verdict as a sentence, then the obligations, then the evidence folded
 * away for anyone who wants to check it, then the identifiers for anyone
 * debugging. Nothing is dropped; the order and the wording change.
 */
export function ClassificationCard({
  result,
  projectId,
  sectionRef,
}: {
  result: ClassifyResult;
  projectId: string | null;
  sectionRef?: Ref<HTMLElement>;
}) {
  const c = result.classification;

  if (result.exit) {
    return (
      <section className="card result-card" ref={sectionRef}>
        <h2>{t("result.title")}</h2>
        <p className="result-headline">{t(result.exit.card_key)}</p>
        {result.exit.obligations.length ? (
          <>
            <h3>{t("result.still_applies")}</h3>
            <ul>
              {result.exit.obligations.map((duty) => (
                <li key={duty}>{t(`obligation.${duty}`)}</li>
              ))}
            </ul>
          </>
        ) : null}
        <p className="muted result-disclaimer">{t("result.disclaimer")}</p>
      </section>
    );
  }

  if (!c) return null;

  const route = c.filing_route;
  const flags = c.pending_flags.filter((flag) => SPEAKABLE_FLAGS.includes(flag));

  return (
    <section className="card result-card" ref={sectionRef}>
      <h2>{t("result.title")}</h2>

      {/* The verdict as a sentence, not a pair of enum chips. */}
      <p className="result-headline">
        {format("result.verdict", {
          form: t(`form_type.${c.form_type}`),
          tier: t(`tier.${c.tier}.name`),
        })}
      </p>
      <p className="muted">{t(`tier.${c.tier}.meaning`)}</p>
      {c.tier_provisional ? (
        <p className="muted">{t("classification.provisional")}</p>
      ) : null}

      <PolicyVerificationBanner status={c.policy_verification_status} />

      {route ? (
        <>
          <h3>{t("result.what_to_do")}</h3>
          <ol className="result-steps">
            <li>
              {format("result.step.authority", {
                authority: t(`filing.authority.${route.authority}`),
              })}
            </li>
            <li>{t(`result.step.pre_shoot.${route.pre_shoot_filing}`)}</li>
            <li>
              {format("result.step.document", {
                document: t(`filing.document.${route.result_document}`),
              })}
            </li>
          </ol>
          <p
            className={
              route.blocks_release_until_granted
                ? "alert warning-alert"
                : "alert"
            }
          >
            {route.blocks_release_until_granted
              ? t("filing.blocks_release")
              : t("filing.no_block")}
          </p>
        </>
      ) : null}

      {c.co_review_required ? (
        <p className="alert warning-alert">{t("classification.co_review")}</p>
      ) : null}

      {/* Caveats as sentences. A flag with no copy is not rendered as its key. */}
      {flags.map((flag) => {
        const text = t(`flag.${flag}`);
        if (text === `flag.${flag}`) return null;
        return (
          <p
            key={flag}
            className={LOUD_FLAGS.includes(flag) ? "alert warning-alert" : "muted"}
          >
            {text}
          </p>
        );
      })}

      {/* Checkable, but not in the way. The ground rule says a conclusion
          carries its evidence; it does not say the evidence has to be the
          first thing a creator reads — nor that it has to be shown as the
          identifiers we happen to store it under. */}
      <details className="result-why">
        <summary>{t("result.why")}</summary>
        {c.matched_rules.length ? (
          <>
            <p className="muted">{t("result.why.quote")}</p>
            <ul>
              {c.matched_rules.map((rule) => (
                <li key={rule.rule_id}>“{rule.quote}”</li>
              ))}
            </ul>
          </>
        ) : null}
        {c.evidence_refs.length ? (
          <>
            <p className="muted">{t("result.why.clauses")}</p>
            <ul>
              {c.evidence_refs.map((ref) => (
                <li key={ref.clause_id}>{t(`clause.${ref.clause_id}`)}</li>
              ))}
            </ul>
            <p className="muted">{t("result.why.document")}</p>
          </>
        ) : null}
        <p className="muted">
          {format("result.why.snapshot", {
            version: c.policy_snapshot_version,
          })}
        </p>
      </details>

      <h3>{t("result.next.title")}</h3>
      <p>{t("result.next.body")}</p>
      {projectId ? (
        <p>
          <a className="primary-button" href={`/collection?project=${projectId}`}>
            {t("result.next.cta")}
          </a>
        </p>
      ) : null}
      <p className="muted">{t("result.next.caveat")}</p>

      <p className="muted result-disclaimer">
        {t("result.disclaimer")}
        {projectId ? (
          <>
            {" "}
            {format("result.reference", { id: projectId })}
          </>
        ) : null}
      </p>
    </section>
  );
}
