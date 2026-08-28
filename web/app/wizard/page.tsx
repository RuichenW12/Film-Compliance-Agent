"use client";

import { useEffect, useRef, useState } from "react";

import { PolicyVerificationBanner } from "../../components/policy-verification-banner";
import {
  ApiError,
  apiFetch,
  type PolicyVerificationStatus,
} from "../../lib/api";
import { BudgetBand } from "../../lib/enums";
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

const BANDS: BudgetBand[] = ["band_a", "band_b", "band_c", "unknown"];

export default function WizardPage() {
  const [logline, setLogline] = useState("");
  const [genres, setGenres] = useState("");
  const [episodeCount, setEpisodeCount] = useState("24");
  const [episodeMinutes, setEpisodeMinutes] = useState("3");
  // Not "band_b". A creator who never opened this dropdown has not told us their
// budget is medium, and defaulting to one invents the fact the tier rests on.
// "unknown" is handled properly downstream: it assumes the stricter tier, flags
// budget_unknown, and returns a three-tier comparison card.
  const [budgetBand, setBudgetBand] = useState<BudgetBand>("unknown");
  const [investmentAmount, setInvestmentAmount] = useState("");
  const [isAiGenerated, setIsAiGenerated] = useState(true);
  // 广电办发〔2024〕35号: platform promotion and voluntary declaration each make
  // a project 重点微短剧 on their own, whatever the investment amount says.
  const [platformPromoted, setPlatformPromoted] = useState(false);
  const [voluntaryKey, setVoluntaryKey] = useState(false);
  // Empty, not "hongguo,douyin". Prefilling names a distribution plan the
  // creator never stated, and a first-time creator often does not have one yet.
  const [platforms, setPlatforms] = useState("");

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
        body: JSON.stringify({ title_working: null })
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
          logline,
          episode_count: Number(episodeCount),
          episode_minutes: Number(episodeMinutes),
          budget_band: budgetBand,
          ...(investmentAmount === ""
            ? {}
            : { investment_amount_rmb: Number(investmentAmount) }),
          is_ai_generated: isAiGenerated,
          platform_promoted: platformPromoted,
          voluntary_key_declaration: voluntaryKey
        })
      });

      await apiFetch(`/v1/projects/${created.project_id}/channels`, {
        method: "POST",
        body: JSON.stringify({
          domestic_platforms: platforms
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
          overseas: []
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
          <span>Logline</span>
          <input
            value={logline}
            onChange={(event) => setLogline(event.target.value)}
            size={60}
            required
          />
        </label>
        <label>
          <span>Genre keywords (comma separated)</span>
          <input
            value={genres}
            onChange={(event) => setGenres(event.target.value)}
            size={40}
          />
        </label>
        <label>
          <span>Episodes</span>
          <input
            type="number"
            min={1}
            value={episodeCount}
            onChange={(event) => setEpisodeCount(event.target.value)}
          />
        </label>
        <label>
          <span>Minutes per episode</span>
          <input
            type="number"
            min={0.5}
            step={0.5}
            value={episodeMinutes}
            onChange={(event) => setEpisodeMinutes(event.target.value)}
          />
        </label>
        <label>
          <span>{t("wizard.investment_amount_rmb")}</span>
          <input
            type="number"
            min={0}
            step={1}
            value={investmentAmount}
            onChange={(event) => setInvestmentAmount(event.target.value)}
          />
        </label>
        <label>
          <span>{t("wizard.budget_band")}</span>
          <select
            value={budgetBand}
            onChange={(event) => setBudgetBand(event.target.value as BudgetBand)}
          >
            {BANDS.map((band) => (
              <option key={band} value={band}>
                {t(`budget_band.${band}`)}
              </option>
            ))}
          </select>
        </label>
        <p className="muted">{t("wizard.budget_band.hint")}</p>
        <label>
          <span>AI generated content</span>
          <input
            type="checkbox"
            checked={isAiGenerated}
            onChange={(event) => setIsAiGenerated(event.target.checked)}
          />
        </label>
        <label>
          <span>{t("wizard.platform_promoted")}</span>
          <input
            type="checkbox"
            checked={platformPromoted}
            onChange={(event) => setPlatformPromoted(event.target.checked)}
          />
        </label>
        <label>
          <span>{t("wizard.voluntary_key")}</span>
          <input
            type="checkbox"
            checked={voluntaryKey}
            onChange={(event) => setVoluntaryKey(event.target.checked)}
          />
        </label>
        <p className="muted">{t("wizard.key_conditions_note")}</p>
        <p className="muted">{t("wizard.key_conditions_guidance")}</p>
        <h2>{t("wizard.channels.title")}</h2>
        <label>
          <span>{t("wizard.domestic_platforms")}</span>
          <input
            value={platforms}
            onChange={(event) => setPlatforms(event.target.value)}
            size={40}
          />
        </label>
        <p className="muted">{t("wizard.domestic_platforms.hint")}</p>
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
        <section className="card" ref={resultRef}>
          <h2>Classification</h2>
          <PolicyVerificationBanner
            status={result.classification?.policy_verification_status}
          />
          {result.exit ? (
            <p>{t(result.exit.card_key)}</p>
          ) : (
            <>
              <p>
                <span className="badge">{result.classification?.form_type}</span>
                <span className="badge">
                  {t("classification.tier")} {result.classification?.tier}
                </span>
                {result.classification?.tier_provisional ? (
                  <span className="badge">
                    {t("classification.provisional")}
                  </span>
                ) : null}
                {result.classification?.co_review_required ? (
                  <span className="badge">{t("classification.co_review")}</span>
                ) : null}
              </p>
              <h3>Why</h3>
              <ul>
                {result.classification?.matched_rules.map((rule) => (
                  <li key={rule.rule_id}>
                    <code>{rule.rule_id}</code>: “{rule.quote}”
                  </li>
                ))}
                {result.classification?.evidence_refs.map((ref) => (
                  <li key={ref.clause_id}>
                    Clause <code>{ref.clause_id}</code> (snapshot{" "}
                    {ref.snapshot_version})
                  </li>
                ))}
              </ul>
              {result.classification?.pending_flags.length ? (
                <p>
                  {result.classification.pending_flags.map((flag) => (
                    <span className="badge" key={flag}>
                      {flag}
                    </span>
                  ))}
                </p>
              ) : null}
              {result.classification?.pending_flags.includes(
                "clause_not_yet_in_force"
              ) ? (
                <p className="alert warning-alert">
                  {t("flag.clause_not_yet_in_force")}
                </p>
              ) : null}
              {result.classification?.filing_route ? (
                <>
                  <h3>{t("filing.heading")}</h3>
                  <ul>
                    <li>
                      {t("filing.authority")}:{" "}
                      <strong>
                        {t(
                          `filing.authority.${result.classification.filing_route.authority}`
                        )}
                      </strong>
                    </li>
                    <li>
                      {t("filing.pre_shoot")}:{" "}
                      {t(
                        `filing.pre_shoot.${result.classification.filing_route.pre_shoot_filing}`
                      )}
                    </li>
                    <li>
                      {t("filing.result_document")}:{" "}
                      {t(
                        `filing.document.${result.classification.filing_route.result_document}`
                      )}
                    </li>
                  </ul>
                  {/* The one line that changes what a creator does next. */}
                  <p
                    className={
                      result.classification.filing_route
                        .blocks_release_until_granted
                        ? "alert warning-alert"
                        : "alert"
                    }
                  >
                    {result.classification.filing_route
                      .blocks_release_until_granted
                      ? t("filing.blocks_release")
                      : t("filing.no_block")}
                  </p>
                </>
              ) : null}
              <p>Roadmap template: {result.roadmap_preview?.template ?? "—"}</p>
            </>
          )}
          <p>
            Project <code>{projectId}</code> is now in state{" "}
            <code>{result.state}</code>.
          </p>
        </section>
      ) : null}
    </section>
  );
}
