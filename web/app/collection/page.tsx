"use client";

import { useCallback, useState } from "react";

import {
  ApiError,
  AssetVersion,
  ExtractResult,
  FactRecord,
  Finding,
  MaterialCard,
  PolicyVerificationStatus,
  RoadmapView,
  ReviewResult,
  attachMaterial,
  confirmRoadmap,
  extractFacts,
  getProject,
  getRoadmap,
  listAssets,
  listFacts,
  listFindings,
  listMaterials,
  requestUploadUrl,
  runReview,
  uploadBytes,
  validateMaterial,
  waiveMaterial
} from "../../lib/api";
import { PolicyVerificationBanner } from "../../components/policy-verification-banner";
import { latestAssetOfKind } from "../../lib/assets";
import { t } from "../../lib/i18n";

const KINDS = [
  "script",
  "synopsis",
  "prompts",
  "final_film",
  "subtitle_sheet",
  "supporting_document"
];

// Flags the API returns when a pack or a model backend is missing. Rendered as
// visible gaps rather than hidden, so a demo never reads as a clean result.
const FLAG_KEYS: Record<string, string> = {
  roadmap_template_pending: "flag.roadmap_template_pending",
  classification_pending: "flag.classification_pending",
  fact_extraction_pending: "flag.fact_extraction_pending",
  script_semantic_check_pending: "flag.script_semantic_check_pending",
  clause_not_yet_in_force: "flag.clause_not_yet_in_force"
};

function Flags({ flags }: { flags: string[] }) {
  if (!flags.length) {
    return null;
  }
  return (
    <p className="alert warning-alert">
      {flags.map((flag) => t(FLAG_KEYS[flag] ?? flag)).join(" · ")}
    </p>
  );
}

export default function CollectionPage() {
  const [projectId, setProjectId] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [assets, setAssets] = useState<AssetVersion[]>([]);
  const [materials, setMaterials] = useState<MaterialCard[]>([]);
  const [facts, setFacts] = useState<FactRecord[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [roadmap, setRoadmap] = useState<RoadmapView | null>(null);
  const [extraction, setExtraction] = useState<ExtractResult | null>(null);
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [verificationStatus, setVerificationStatus] =
    useState<PolicyVerificationStatus | null>(null);

  const [kind, setKind] = useState("script");
  const [file, setFile] = useState<File | null>(null);

  const refresh = useCallback(async (id: string) => {
    const [
      nextAssets,
      nextMaterials,
      nextFacts,
      nextFindings,
      nextRoadmap,
      nextProject
    ] =
      await Promise.all([
        listAssets(id),
        listMaterials(id),
        listFacts(id),
        listFindings(id),
        getRoadmap(id),
        getProject(id)
      ]);
    setAssets(nextAssets);
    setMaterials(nextMaterials);
    setFacts(nextFacts);
    setFindings(nextFindings);
    setRoadmap(nextRoadmap);
    setVerificationStatus(
      nextProject.project.classification?.policy_verification_status ?? null
    );
    setLoaded(true);
  }, []);

  async function guard(label: string, work: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await work();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? `${caught.code}: ${caught.message}`
          : String(caught)
      );
    } finally {
      setBusy(null);
    }
  }

  async function load(event: React.FormEvent) {
    event.preventDefault();
    await guard("load", async () => {
      await refresh(projectId.trim());
    });
  }

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      return;
    }
    await guard("upload", async () => {
      const ticket = await requestUploadUrl(projectId, kind, file.name);
      await uploadBytes(ticket.upload_url, file);
      setFile(null);
      await refresh(projectId);
    });
  }

  const latestScript = assets.filter((asset) => asset.kind === "script").pop();

  return (
    <section>
      <h1>{t("collection.title")}</h1>
      <p className="page-intro">{t("collection.intro")}</p>

      <form onSubmit={load} className="card">
        <label>
          <span>{t("collection.project_id")}</span>
          <input
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            size={40}
            placeholder="proj_..."
          />
        </label>
        <button type="submit" className="primary-button" disabled={busy !== null}>
          {busy === "load" ? t("collection.loading") : t("collection.load")}
        </button>
      </form>

      {error ? (
        <p className="alert error-alert" role="alert">
          {error}
        </p>
      ) : null}

      {!loaded ? null : (
        <>
          <PolicyVerificationBanner status={verificationStatus} />
          <section className="card">
            <h2>{t("collection.upload")}</h2>
            <form onSubmit={upload}>
              <label>
                <span>{t("collection.kind")}</span>
                <select value={kind} onChange={(event) => setKind(event.target.value)}>
                  {KINDS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>{t("collection.file")}</span>
                <input
                  type="file"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
              </label>
              <button
                type="submit"
                className="primary-button"
                disabled={!file || busy !== null}
              >
                {busy === "upload" ? t("collection.uploading") : t("collection.upload")}
              </button>
            </form>

            {assets.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t("collection.version")}</th>
                      <th>{t("collection.kind")}</th>
                      <th>sha256</th>
                      <th>{t("collection.parent")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {assets.map((asset) => (
                      <tr key={asset.version_id}>
                        <td>
                          <code>{asset.version_id}</code>
                        </td>
                        <td>{asset.kind}</td>
                        <td>
                          <code>{asset.sha256.slice(0, 12)}…</code>
                        </td>
                        <td>
                          {asset.parent_version ? (
                            <code>{asset.parent_version.slice(0, 12)}…</code>
                          ) : (
                            <span className="muted">{t("collection.first_version")}</span>
                          )}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="secondary-button"
                            disabled={busy !== null}
                            onClick={() =>
                              guard("extract", async () => {
                                setExtraction(
                                  await extractFacts(projectId, asset.version_id)
                                );
                                await refresh(projectId);
                              })
                            }
                          >
                            {t("collection.extract")}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty-state">{t("collection.no_assets")}</p>
            )}

            {extraction ? (
              <>
                <Flags flags={extraction.pending_flags} />
                {extraction.discarded.length ? (
                  <p className="muted">
                    {t("collection.discarded")}: {extraction.discarded.join(", ")}
                  </p>
                ) : null}
              </>
            ) : null}
          </section>

          <section className="card">
            <h2>{t("collection.facts")}</h2>
            {facts.length ? (
              <ul>
                {facts.map((fact) => (
                  <li key={fact.fact_id}>
                    <strong>{fact.key}</strong>: {String(fact.value ?? t("field.pending"))}{" "}
                    <span className="chip">{fact.status}</span>
                    {fact.source_ref.locator ? (
                      <div className="muted">
                        {t("collection.quoted")}: “{fact.source_ref.locator}”
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-state">{t("collection.no_facts")}</p>
            )}
          </section>

          <section className="card">
            <h2>{t("collection.materials")}</h2>
            {materials.length ? (
              <ul>
                {materials.map((card) => {
                  const latestMatching = latestAssetOfKind(assets, card.asset_kind);
                  return (
                    <li key={card.material_id}>
                      <strong>{t(card.name_key)}</strong>{" "}
                      <span className="chip">{card.status}</span>
                      {card.required ? null : (
                        <span className="chip">{t("collection.optional")}</span>
                      )}
                      {card.why_clause ? (
                        <span className="muted"> · {card.why_clause.clause_id}</span>
                      ) : (
                        <span className="muted"> · {t("collection.no_clause")}</span>
                      )}
                      {card.invalid_reasons.length ? (
                        <div className="muted">{card.invalid_reasons.join(", ")}</div>
                      ) : null}
                      <div className="button-group">
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={!latestMatching || busy !== null}
                          onClick={() =>
                            guard("attach", async () => {
                              await attachMaterial(
                                projectId,
                                card.material_id,
                                latestMatching!.version_id
                              );
                              await refresh(projectId);
                            })
                          }
                        >
                          {t("collection.attach_latest")}
                        </button>
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={busy !== null}
                        onClick={() =>
                          guard("validate", async () => {
                            await validateMaterial(projectId, card.material_id);
                            await refresh(projectId);
                          })
                        }
                      >
                        {t("collection.validate")}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={busy !== null}
                        onClick={() =>
                          guard("waive", async () => {
                            const reason = window.prompt(t("collection.waive_reason"));
                            if (!reason) {
                              return;
                            }
                            await waiveMaterial(projectId, card.material_id, reason);
                            await refresh(projectId);
                          })
                        }
                      >
                        {t("collection.waive")}
                      </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="empty-state">{t("collection.no_materials")}</p>
            )}
          </section>

          <section className="card">
            <h2>{t("collection.roadmap")}</h2>
            {roadmap ? <Flags flags={roadmap.pending_flags} /> : null}
            {roadmap?.roadmap ? (
              <>
                <p>
                  <span className="badge">{roadmap.roadmap.template}</span>
                  {roadmap.roadmap.confirmed ? (
                    <span className="badge">{t("collection.confirmed")}</span>
                  ) : null}
                </p>
                {roadmap.roadmap.steps.length ? (
                  <ol>
                    {roadmap.roadmap.steps.map((step) => (
                      <li key={step.idx}>
                        {t(step.name)} · {step.owner}
                        {step.est_weeks ? ` · ${step.est_weeks}w` : ""}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="empty-state">{t("collection.no_steps")}</p>
                )}
                <button
                  type="button"
                  className="primary-button"
                  disabled={busy !== null || roadmap.roadmap.confirmed}
                  onClick={() =>
                    guard("roadmap", async () => {
                      setRoadmap(await confirmRoadmap(projectId));
                      await refresh(projectId);
                    })
                  }
                >
                  {t("collection.confirm_roadmap")}
                </button>
              </>
            ) : (
              <p className="empty-state">{t("collection.no_roadmap")}</p>
            )}
          </section>

          <section className="card">
            <h2>{t("collection.review")}</h2>
            <button
              type="button"
              className="primary-button"
              disabled={!latestScript || busy !== null}
              onClick={() =>
                guard("review", async () => {
                  setReview(await runReview(projectId));
                  await refresh(projectId);
                })
              }
            >
              {busy === "review" ? t("collection.reviewing") : t("collection.run_review")}
            </button>
            {!latestScript ? (
              <p className="muted">{t("collection.review_needs_script")}</p>
            ) : null}

            {review ? (
              <>
                <Flags flags={review.pending_flags} />
                {review.discarded.length ? (
                  <p className="muted">
                    {t("collection.discarded")}: {review.discarded.join(", ")}
                  </p>
                ) : null}
              </>
            ) : null}

            {findings.length ? (
              <ul>
                {findings.map((finding) => (
                  <li key={finding.finding_id}>
                    <span className="chip">{finding.severity}</span>{" "}
                    <strong>{finding.category}</strong>
                    {finding.locator.episode ? (
                      <span className="muted">
                        {" "}
                        · ep {finding.locator.episode}
                        {finding.locator.scene ? ` sc ${finding.locator.scene}` : ""}
                      </span>
                    ) : null}
                    <div>“{finding.locator.quote}”</div>
                    {finding.locator.match_lines.length ? (
                      <div className="muted">
                        {finding.locator.match_lines.length > 1
                          ? `${t("finding.matching_lines")}: ${finding.locator.match_lines.join(", ")}`
                          : `${t("finding.line")} ${finding.locator.match_lines[0]}`}
                      </div>
                    ) : null}
                    <div className="muted">
                      {finding.evidence_refs
                        .map((ref) => `${ref.clause_id} @ ${ref.snapshot_version}`)
                        .join(", ")}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-state">{t("collection.no_findings")}</p>
            )}
          </section>

          <p className="disclaimer">{t("app.disclaimer")}</p>
        </>
      )}
    </section>
  );
}
