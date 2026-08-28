"use client";

import { useEffect, useRef, useState } from "react";

import { FieldHelp } from "../../components/field-help";
import { ClassificationCard } from "../../components/classification-card";
import { GenrePicker } from "../../components/genre-picker";
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



type ProductionStage = "idea" | "script_ready" | "shooting" | "finished" | "unknown";
const STAGES: ProductionStage[] = [
  "unknown",
  "idea",
  "script_ready",
  "shooting",
  "finished"
];

export default function WizardPage() {
  const [title, setTitle] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [stage, setStage] = useState<ProductionStage>("unknown");
  const [genres, setGenres] = useState("");
  const [episodeCount, setEpisodeCount] = useState("24");
  const [episodeMinutes, setEpisodeMinutes] = useState("3");
  // "unknown", not a range. A creator who never opened this dropdown has not
  // told us anything about their budget, and picking one for them would invent
  // the fact the tier rests on. Handled properly downstream: the stricter tier
  // is assumed, `budget_unknown` is flagged, and a three-tier comparison card
  // comes back.
  const [amountBracket, setAmountBracket] = useState<AmountBracket>("unknown");
  const [investmentAmount, setInvestmentAmount] = useState("");
  const [isAiGenerated, setIsAiGenerated] = useState(true);
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

  return (
    <section>
      <h1>{t("wizard.intent.title")}</h1>
      <form onSubmit={onSubmit} className="card">
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
        <label>
          <span>AI generated content</span>
          <FieldHelp field="is_ai_generated" label="AI generated content" />
          <input
            type="checkbox"
            checked={isAiGenerated}
            onChange={(event) => setIsAiGenerated(event.target.checked)}
          />
        </label>
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
                  : /* The figures follow the AI checkbox: the same range means
                       a different tier, and showing live-action numbers to
                       someone making an AI drama would be worse than showing
                       none. */
                    BRACKET_LABELS[isAiGenerated ? "ai" : "live_action"][
                      bracket
                    ]}
              </option>
            ))}
          </select>
        </label>
        <p className="muted">{t("wizard.amount_bracket.hint")}</p>
        <label>
          <span>{t("wizard.investment_amount_rmb")}</span>
          <FieldHelp field="investment_amount_rmb" label="Investment amount (RMB)" />
          <input
            type="number"
            min={0}
            step={1}
            value={investmentAmount}
            onChange={(event) => setInvestmentAmount(event.target.value)}
          />
        </label>
        <label>
          <span>Episodes</span>
          <FieldHelp field="episode_count" label="Episodes" />
          <input
            type="number"
            min={1}
            value={episodeCount}
            onChange={(event) => setEpisodeCount(event.target.value)}
          />
        </label>
        <label>
          <span>Minutes per episode</span>
          <FieldHelp field="episode_minutes" label="Minutes per episode" />
          <input
            type="number"
            min={0.5}
            step={0.5}
            value={episodeMinutes}
            onChange={(event) => setEpisodeMinutes(event.target.value)}
          />
        </label>
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
