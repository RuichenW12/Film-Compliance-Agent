"use client";

import { useState } from "react";

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
  const [budgetBand, setBudgetBand] = useState<BudgetBand>("band_b");
  const [investmentAmount, setInvestmentAmount] = useState("");
  const [isAiGenerated, setIsAiGenerated] = useState(true);
  const [platforms, setPlatforms] = useState("hongguo,douyin");

  const [busy, setBusy] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [result, setResult] = useState<ClassifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          is_ai_generated: isAiGenerated
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
          <span>Budget band</span>
          <select
            value={budgetBand}
            onChange={(event) => setBudgetBand(event.target.value as BudgetBand)}
          >
            {BANDS.map((band) => (
              <option key={band} value={band}>
                {band}
              </option>
            ))}
          </select>
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
          <span>AI generated content</span>
          <input
            type="checkbox"
            checked={isAiGenerated}
            onChange={(event) => setIsAiGenerated(event.target.checked)}
          />
        </label>
        <h2>{t("wizard.channels.title")}</h2>
        <label>
          <span>Domestic platforms</span>
          <input
            value={platforms}
            onChange={(event) => setPlatforms(event.target.value)}
            size={40}
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Running…" : t("wizard.classify")}
        </button>
      </form>

      {error ? <p role="alert">{error}</p> : null}

      {result ? (
        <section className="card">
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
