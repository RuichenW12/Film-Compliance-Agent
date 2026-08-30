"use client";

import { useEffect, useRef, useState } from "react";

import { FieldHelp } from "../../components/field-help";
import { ClassificationCard } from "../../components/classification-card";
import { GenrePicker } from "../../components/genre-picker";
import { LengthPicker } from "../../components/length-picker";
import { PolicyVerificationBanner } from "../../components/policy-verification-banner";
import {
  ApiError,
  apiFetch,
  type PolicyVerificationStatus,
} from "../../lib/api";
import {
  AMOUNT_BRACKETS,
  BRACKET_LABELS,
  type AmountBracket,
} from "../../lib/enums";
import { t } from "../../lib/i18n";

interface ClassifyResponse {
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



type ProductionStage =
  | "idea"
  | "script_ready"
  | "production_complete"
  | "unknown";
/* Ordered as the work actually progresses, with the honest non-answer last.
   "shooting" is gone: an AI micro-drama is generated rather than shot, so
   there is no state between having a script and having a finished work. */
const STAGES: ProductionStage[] = [
  "idea",
  "script_ready",
  "production_complete",
  "unknown"
];

export default function WizardPage() {
  const [title, setTitle] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [stage, setStage] = useState<ProductionStage>("idea");
  /* "Just an idea" and "not sure yet" are the two answers that mean the scale
     questions have no answer yet. Everything past them implies a script, and a
     script implies episodes and running time. */
  const earlyStage = stage === "idea" || stage === "unknown";
  const [genres, setGenres] = useState("");
  const [episodeCount, setEpisodeCount] = useState("24");
  const [episodeMinutes, setEpisodeMinutes] = useState("3");
  // "unknown", not a range. A creator who never opened this dropdown has not
  // told us anything about their budget, and picking one for them would invent
  // the fact the tier rests on. Handled properly downstream: the stricter tier
  // is assumed, `budget_unknown` is flagged, and a three-tier comparison card
  // comes back.
  const [amountBracket, setAmountBracket] = useState<AmountBracket>("unknown");
  // The exact figure is no longer asked for at intake: the bracket settles the
  // tier on its own, and the filing form is where the number is actually
  // needed. The state stays so the POST body keeps the field -- the API
  // contract is unchanged, and the form-freeze stage will supply it. See D-038.
  const [investmentAmount] = useState("");
  /* No longer asked. The product classifies AI micro-dramas only, so the
     answer is a constant -- but the field stays on the wire because the
     regulation genuinely distinguishes the two and the snapshot still carries
     both threshold sets. See the plan note on D-026. */
  const isAiGenerated = true;
  // 广电办发〔2024〕35号: platform promotion and voluntary declaration each make
  // a project 重点微短剧 on their own, whatever the investment amount says.
  const [platformPromoted, setPlatformPromoted] = useState(false);
  const [voluntaryKey, setVoluntaryKey] = useState(false);

  const [busy, setBusy] = useState(false);
  const resultRef = useRef<HTMLElement | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [result, setResult] = useState<ClassifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!result) return;
    resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const created = await apiFetch<{ project_id: string }>("/v1/projects", {
        method: "POST",
        body: JSON.stringify({ title_working: title.trim() || null })
      });
      setProjectId(created.project_id);

      await apiFetch(`/v1/projects/${created.project_id}/intent`, {
        method: "POST",
        body: JSON.stringify({
          form_type_claimed: "micro_drama",
          genre_keywords: genres
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
          synopsis: synopsis.trim() || null,
          production_stage: stage,
          episode_count: Number(episodeCount),
          episode_minutes: Number(episodeMinutes),
          amount_bracket: amountBracket,
          ...(investmentAmount === ""
            ? {}
            : { investment_amount_rmb: Number(investmentAmount) }),
          is_ai_generated: isAiGenerated,
          platform_promoted: platformPromoted,
          voluntary_key_declaration: voluntaryKey
        })
      });


      const classified = await apiFetch<ClassifyResponse>(
        `/v1/projects/${created.project_id}/classify`,
        { method: "POST" }
      );
      setResult(classified);
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(`${caught.code}: ${caught.message}`);
      } else {
        setError(String(caught));
      }
    } finally {
      setBusy(false);
    }
  }

  /* Length, adjusted rather than typed. Article 2 defines a micro-drama by
     episode length, so these cannot be skipped -- but a number box asks a
     creator at the idea stage to commit to a figure they have not decided,
     and folding it away just submitted the default invisibly. A suggestion
     that shows its consequence as you move it is neither. */
  const lengthFields = (
    <LengthPicker
      episodeCount={episodeCount}
      episodeMinutes={episodeMinutes}
      onCountChange={setEpisodeCount}
      onMinutesChange={setEpisodeMinutes}
    />
  );

  /* The budget genuinely has no answer at the idea stage, and unlike length
     the chain does not need one -- an unanswered budget produces an honest
     provisional class plus the comparison table. So this is the field that
     folds. */
  const budgetField = (
    <>
      <label>
        <span>{t("wizard.amount_bracket")}</span>
        <FieldHelp field="amount_bracket" label="Budget range" />
        <select
          value={amountBracket}
          onChange={(event) =>
            setAmountBracket(event.target.value as AmountBracket)
          }
        >
          {AMOUNT_BRACKETS.map((bracket) => (
            <option key={bracket} value={bracket}>
              {bracket === "unknown"
                ? t("amount_bracket.unknown")
                : BRACKET_LABELS[bracket]}
            </option>
          ))}
        </select>
      </label>
      <p className="muted">{t("wizard.amount_bracket.hint")}</p>
    </>
  );

  return (
    <section>
      <h1>{t("wizard.intent.title")}</h1>
      <p className="page-intro">{t("wizard.intent.intro")}</p>
      <form onSubmit={onSubmit} className="card">
        {/* Asked first because it decides what else is worth asking. */}
        <label>
          <span>{t("wizard.production_stage")}</span>
          <FieldHelp field="production_stage" label="How far along it is" />
          <select
            value={stage}
            onChange={(event) => setStage(event.target.value as ProductionStage)}
          >
            {STAGES.map((value) => (
              <option key={value} value={value}>
                {t(`production_stage.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <p className="muted">{t(`wizard.stage_hint.${stage}`)}</p>
        <label>
          <span>{t("wizard.title")}</span>
          <FieldHelp field="title" label="Title" />
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            size={40}
          />
        </label>
        <label>
          <span>Genre keywords (comma separated)</span>
          <FieldHelp field="genre_keywords" label="Genre keywords" />
          <GenrePicker value={genres} onChange={setGenres} />
        </label>
        <label>
          <span>{t("wizard.synopsis")}</span>
          <FieldHelp field="synopsis" label="Synopsis" />
          <textarea
            value={synopsis}
            onChange={(event) => setSynopsis(event.target.value)}
            rows={4}
          />
        </label>
        {/* The scale questions. At the idea stage a creator has a premise and
            nothing else -- no budget, no episode count, no running time -- so
            asking outright produced a form demanding answers nobody at that
            stage has. They are folded away instead of removed: somebody who
            does know can still say so, and the backend has always accepted
            "unknown" for all three. */}
        {lengthFields}
        {earlyStage ? (
          <details className="if-you-know">
            <summary>{t("wizard.if_you_know")}</summary>
            <p className="muted">{t("wizard.if_you_know.hint")}</p>
            {budgetField}
          </details>
        ) : (
          budgetField
        )}
        {/* Neither is answerable at intake: platform promotion is settled
            after the film exists, and declaring voluntarily is a strategic
            choice. Kept, because deleting them would let a platform-featured
            500,000 project read as three-class when Circular 35 makes it one
            — but out of the first screen, where they were noise. */}
        <details className="more-conditions">
          <summary>{t("wizard.more_conditions")}</summary>
        <label>
          <span>{t("wizard.platform_promoted")}</span>
          <FieldHelp field="platform_promoted" label="Platform will feature it" />
          <input
            type="checkbox"
            checked={platformPromoted}
            onChange={(event) => setPlatformPromoted(event.target.checked)}
          />
        </label>
        <label>
          <span>{t("wizard.voluntary_key")}</span>
          <FieldHelp field="voluntary_key_declaration" label="Declaring it voluntarily as a key micro-drama" />
          <input
            type="checkbox"
            checked={voluntaryKey}
            onChange={(event) => setVoluntaryKey(event.target.checked)}
          />
        </label>
        <p className="muted">{t("wizard.key_conditions_note")}</p>
        <p className="muted">{t("wizard.key_conditions_guidance")}</p>
        </details>
        <button type="submit" disabled={busy}>
          {busy ? "Running…" : t("wizard.classify")}
        </button>
      </form>

      {error ? <p role="alert">{error}</p> : null}

      {/* A real Gemini call takes 8-12s. Without something in the place the
          answer will appear, the page looks frozen: the only feedback was the
          button's label, and the result card renders below the fold. */}
      {busy ? (
        <section className="card" aria-live="polite">
          <h2>{t("wizard.classifying")}</h2>
          <p className="muted">{t("wizard.classifying.hint")}</p>
        </section>
      ) : null}

      {result ? (
        <ClassificationCard
          result={result}
          projectId={projectId}
          sectionRef={resultRef}
        />
      ) : null}
    </section>
  );
}
