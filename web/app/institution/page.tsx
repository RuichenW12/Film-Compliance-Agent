"use client";

import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  Institution,
  InstitutionReview,
  apiFetch,
  decideReview,
  listInstitutions,
  loadInstitutions,
  readReview,
  recordFiling,
  submitToInstitution
} from "../../lib/api";
import { getRole } from "../../lib/demoAuth";
import { t } from "../../lib/i18n";

// Demo entries an administrator can load with one click. Obviously placeholder
// names and licence numbers: nothing here claims a real company exists.
const DEMO_INSTITUTIONS: Institution[] = [
  {
    institution_id: "inst_demo_ok",
    name: "示例持证机构甲 (demo licensed institution A)",
    license_no: "DEMO-LICENSE-0001",
    valid_until: "2030-12-31",
    registered_capital_rmb: 10_000_000,
    has_foreign: false
  },
  {
    institution_id: "inst_demo_foreign",
    name: "示例外资机构乙 (demo foreign-invested institution B)",
    license_no: "DEMO-LICENSE-0002",
    valid_until: "2030-12-31",
    registered_capital_rmb: 10_000_000,
    has_foreign: true
  }
];

const REASON_KEYS: Record<string, string> = {
  institution_not_in_registry: "license.reason.not_in_registry",
  registered_capital_below_threshold: "license.reason.capital",
  foreign_investment: "license.reason.foreign"
};

function LicenceVerdict({ review }: { review: InstitutionReview }) {
  const check = review.license_check;
  if (!check) {
    return null;
  }
  const passed = !check.reasons.length && check.capital_ok && check.no_foreign_ok;
  return (
    <div>
      <p>
        <span className="chip">{passed ? t("license.passed") : t("license.failed")}</span>
        {check.mock ? <span className="chip">{t("license.mock")}</span> : null}
      </p>
      {check.reasons.length ? (
        <ul>
          {check.reasons.map((reason) => (
            <li key={reason}>{t(REASON_KEYS[reason] ?? reason)}</li>
          ))}
        </ul>
      ) : null}
      <p className="muted">{t("license.disclaimer")}</p>
    </div>
  );
}

export default function InstitutionPage() {
  const [projectId, setProjectId] = useState("");
  const [role, setRole] = useState("creator");
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [chosen, setChosen] = useState("");
  const [review, setReview] = useState<InstitutionReview | null>(null);
  const [state, setState] = useState<string | null>(null);
  const [agreement, setAgreement] = useState("blob://demo-agreement");
  const [comments, setComments] = useState("");
  const [registration, setRegistration] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRole(getRole());
  }, []);

  const refreshInstitutions = useCallback(async () => {
    try {
      const listed = await listInstitutions();
      setInstitutions(listed);
      setChosen((current) => current || listed[0]?.institution_id || "");
    } catch {
      setInstitutions([]);
    }
  }, []);

  useEffect(() => {
    void refreshInstitutions();
  }, [refreshInstitutions]);

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

  async function refreshProject(id: string) {
    setReview(await readReview(id));
    const project = await apiFetch<{ project: { state: string } }>(
      `/v1/projects/${id}`
    );
    setState(project.project.state);
  }

  return (
    <section>
      <h1>{t("institution.title")}</h1>
      <p className="page-intro">{t("institution.intro")}</p>

      <section className="card">
        <h2>{t("institution.registry")}</h2>
        {institutions.length ? (
          <ul>
            {institutions.map((entry) => (
              <li key={entry.institution_id}>
                {entry.name} · <code>{entry.license_no}</code>
                {entry.has_foreign ? (
                  <span className="chip">{t("institution.foreign")}</span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty-state">{t("institution.registry_empty")}</p>
        )}
        {role === "admin" ? (
          <>
            <button
              type="button"
              className="secondary-button"
              disabled={busy !== null}
              onClick={() =>
                guard("load", async () => {
                  await loadInstitutions(DEMO_INSTITUTIONS);
                  await refreshInstitutions();
                })
              }
            >
              {t("institution.load_demo")}
            </button>
            <p className="muted">{t("institution.load_demo_note")}</p>
          </>
        ) : (
          <p className="muted">{t("institution.load_demo_admin_only")}</p>
        )}
      </section>

      <form
        className="card"
        onSubmit={(event) => {
          event.preventDefault();
          void guard("load_project", async () => {
            await refreshProject(projectId.trim());
          });
        }}
      >
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
          {t("collection.load")}
        </button>
        {state ? (
          <p>
            <span className="badge">{state}</span>
          </p>
        ) : null}
      </form>

      {error ? (
        <p className="alert error-alert" role="alert">
          {error}
        </p>
      ) : null}

      {state ? (
        <>
          <section className="card">
            <h2>{t("institution.submit")}</h2>
            <p className="muted">{t("institution.submit_note")}</p>
            <label>
              <span>{t("institution.choose")}</span>
              <select value={chosen} onChange={(event) => setChosen(event.target.value)}>
                <option value="">{t("institution.choose_placeholder")}</option>
                {institutions.map((entry) => (
                  <option key={entry.institution_id} value={entry.institution_id}>
                    {entry.name}
                  </option>
                ))}
                <option value="inst_not_in_registry">
                  {t("institution.unknown_option")}
                </option>
              </select>
            </label>
            <button
              type="button"
              className="primary-button"
              disabled={!chosen || busy !== null}
              onClick={() =>
                guard("submit", async () => {
                  const result = await submitToInstitution(projectId, chosen);
                  setReview(result.review);
                  setState(result.state);
                })
              }
            >
              {t("institution.submit")}
            </button>
          </section>

          {review ? (
            <section className="card">
              <h2>{t("institution.review")}</h2>
              <p>
                <span className="chip">{review.decision}</span>
                {review.institution_id ? (
                  <span className="muted"> · {review.institution_id}</span>
                ) : null}
              </p>
              <LicenceVerdict review={review} />
              {review.return_comments ? (
                <p className="alert warning-alert">{review.return_comments}</p>
              ) : null}

              {role === "institution" ? (
                <>
                  <h3>{t("institution.decide")}</h3>
                  <label>
                    <span>{t("institution.agreement")}</span>
                    <input
                      value={agreement}
                      onChange={(event) => setAgreement(event.target.value)}
                      size={32}
                    />
                  </label>
                  <label>
                    <span>{t("institution.comments")}</span>
                    <input
                      value={comments}
                      onChange={(event) => setComments(event.target.value)}
                      size={32}
                    />
                  </label>
                  <div className="button-group">
                    <button
                      type="button"
                      className="primary-button"
                      disabled={busy !== null}
                      onClick={() =>
                        guard("accept", async () => {
                          const result = await decideReview(projectId, {
                            decision: "accept",
                            signed_agreement_uri: agreement
                          });
                          setReview(result.review);
                          setState(result.state);
                        })
                      }
                    >
                      {t("institution.accept")}
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={busy !== null}
                      onClick={() =>
                        guard("return", async () => {
                          const result = await decideReview(projectId, {
                            decision: "return",
                            return_comments: comments
                          });
                          setReview(result.review);
                          setState(result.state);
                        })
                      }
                    >
                      {t("institution.return")}
                    </button>
                  </div>

                  <h3>{t("institution.filing")}</h3>
                  <p className="muted">{t("institution.filing_note")}</p>
                  <label>
                    <span>{t("institution.registration_number")}</span>
                    <input
                      value={registration}
                      onChange={(event) => setRegistration(event.target.value)}
                      size={32}
                      placeholder={t("field.pending")}
                    />
                  </label>
                  <button
                    type="button"
                    className="primary-button"
                    disabled={!registration.trim() || busy !== null}
                    onClick={() =>
                      guard("file", async () => {
                        const result = await recordFiling(projectId, registration);
                        setState(result.state);
                        await refreshProject(projectId);
                      })
                    }
                  >
                    {t("institution.record_filing")}
                  </button>
                </>
              ) : (
                <p className="muted">{t("institution.creator_view_note")}</p>
              )}
            </section>
          ) : null}
        </>
      ) : null}

      <p className="disclaimer">{t("app.disclaimer")}</p>
    </section>
  );
}
