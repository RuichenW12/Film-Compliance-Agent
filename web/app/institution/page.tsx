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
  recordFiling
} from "../../lib/api";
import { InstitutionQueue } from "../../components/institution-queue";
import { getRole } from "../../lib/demoAuth";
import { t } from "../../lib/i18n";

// Demo entries an administrator can load with one click. Obviously placeholder
// names and licence numbers: nothing here claims a real company exists.
const DEMO_INSTITUTIONS: Institution[] = [
  {
    institution_id: "inst_demo_ok",
    name: "Demo Licensed Institution A",
    license_no: "DEMO-LICENSE-0001",
    valid_until: "2030-12-31",
    registered_capital_rmb: 10_000_000,
    has_foreign: false
  },
  {
    institution_id: "inst_demo_foreign",
    name: "Demo Foreign-Invested Institution B",
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
  /* Bumped whenever a decision lands, so the queue reloads and the row just
     acted on disappears rather than lingering as a stale entry. */
  const [queueVersion, setQueueVersion] = useState(0);
  const [role, setRole] = useState("creator");
  const [institutions, setInstitutions] = useState<Institution[]>([]);
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

      <InstitutionQueue
        reloadKey={queueVersion}
        onError={setError}
        onOpen={(id) => {
          setProjectId(id);
          void guard("load_project", async () => {
            await refreshProject(id);
          });
        }}
      />

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
          {/* The submit card used to live here. It is the creator's act --
              `submit_to_institution` calls `_assert_owner` -- and keeping it on
              the reviewer's page stranded the creator at the lock with the next
              step on someone else's screen. It now sits on `/collection`, next
              to the form being sent. See D-047. */}

          {review ? (
            <section className="card">
              <h2>{t("institution.review")}</h2>
              <p>
                <span className="chip">{t(`decision.${review.decision}`)}</span>
                {review.institution_id ? (
                  <span className="muted">
                    {" · "}
                    {/* The company's name, not its id. The registry is right
                        here, so there is no reason to show the key instead. */}
                    {institutions.find(
                      (entry) => entry.institution_id === review.institution_id
                    )?.name ?? review.institution_id}
                  </span>
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
                          // A decision changes what is waiting, so the queue
                          // must not keep showing the row just acted on.
                          setQueueVersion((version) => version + 1);
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
                          // A decision changes what is waiting, so the queue
                          // must not keep showing the row just acted on.
                          setQueueVersion((version) => version + 1);
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
                        setQueueVersion((version) => version + 1);
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
