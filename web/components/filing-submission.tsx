"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type Institution,
  type InstitutionReview,
  listInstitutions,
  readReview,
  resumeAfterReturn,
  submitToInstitution,
} from "@/lib/api";
import { format, t } from "@/lib/i18n";

/**
 * Sending the locked form to a filing company, and what came back.
 *
 * This lived on `/institution`, which was wrong twice over. It is the creator's
 * act -- `submit_to_institution` calls `_assert_owner`, so a reviewer switching
 * roles could not perform it at all -- and it stranded the creator at the lock,
 * with the next step on a page belonging to someone else.
 *
 * `resume` is here for the same reason: taking a returned project back into
 * revision is the creator answering the reviewer, not the reviewer acting again.
 */
export function FilingSubmission({
  projectId,
  frozen,
  state,
  onChange,
  onError,
}: {
  projectId: string;
  frozen: boolean;
  state: string | null;
  onChange: () => void;
  onError: (message: string | null) => void;
}) {
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [chosen, setChosen] = useState("");
  const [review, setReview] = useState<InstitutionReview | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [listed, current] = await Promise.all([
        listInstitutions(),
        readReview(projectId).catch(() => null),
      ]);
      setInstitutions(listed);
      setReview(current);
      setChosen((existing) => existing || listed[0]?.institution_id || "");
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : String(caught));
    }
    // `onError` is a setState function, stable for the life of the page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (frozen) void load();
  }, [frozen, load]);

  async function run(label: string, work: () => Promise<unknown>) {
    setBusy(label);
    onError(null);
    try {
      await work();
      await load();
      onChange();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  // Before the lock there is nothing to send, and saying so would only add a
  // dead control to a screen that already has plenty.
  if (!frozen) return null;

  const returned = state === "INSTITUTION_RETURNED";
  const underReview = state === "INSTITUTION_REVIEW";
  const accepted = state === "READY_FOR_EXTERNAL_FILING";
  const filed = state === "FILED";

  return (
    <section className="card">
      <h2>{t("send.title")}</h2>

      {filed ? (
        <p className="alert">{t("send.filed")}</p>
      ) : accepted ? (
        <p className="alert">{t("send.accepted")}</p>
      ) : underReview ? (
        <p className="alert">{t("send.under_review")}</p>
      ) : returned ? (
        <>
          <p className="alert warning-alert">{t("send.returned")}</p>
          {/* The reviewer's own words, not a paraphrase of them. */}
          {review?.return_comments ? (
            <blockquote className="review-comments">
              {review.return_comments}
            </blockquote>
          ) : null}
          <p>
            <button
              type="button"
              className="primary-button"
              disabled={busy !== null}
              onClick={() => run("resume", () => resumeAfterReturn(projectId))}
            >
              {busy === "resume" ? t("send.resuming") : t("send.fix_it")}
            </button>
          </p>
          <p className="muted">{t("send.resume_hint")}</p>
        </>
      ) : (
        <>
          <p className="muted">{t("send.intro")}</p>
          {institutions.length === 0 ? (
            <p className="muted">{t("send.no_institutions")}</p>
          ) : (
            <>
              <label>
                <span>{t("send.choose")}</span>
                <select
                  value={chosen}
                  onChange={(event) => setChosen(event.target.value)}
                >
                  {institutions.map((institution) => (
                    <option
                      key={institution.institution_id}
                      value={institution.institution_id}
                    >
                      {institution.name}
                    </option>
                  ))}
                  {/* Carried over from the reviewer's page so the failing
                      licence path stays demonstrable from the one screen that
                      can now submit. Labelled as what it is, not offered as a
                      real choice. */}
                  <option value="inst_not_in_registry">
                    {t("send.unknown_option")}
                  </option>
                </select>
              </label>
              <p>
                <button
                  type="button"
                  className="primary-button"
                  disabled={busy !== null || !chosen}
                  onClick={() =>
                    run("submit", () => submitToInstitution(projectId, chosen))
                  }
                >
                  {busy === "submit" ? t("send.sending") : t("send.send")}
                </button>
              </p>
            </>
          )}
        </>
      )}

      {/* The licence check is a demo, and every surface that shows it says so. */}
      {review?.license_check ? (
        <p className="muted">
          {review.license_check.reasons.length === 0
            ? t("send.licence_ok")
            : format("send.licence_failed", {
                reasons: review.license_check.reasons
                  .map((reason) => t(`licence.${reason}`))
                  .join("; "),
              })}
        </p>
      ) : null}
    </section>
  );
}
