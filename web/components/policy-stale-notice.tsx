"use client";

import { useState } from "react";

import { reclassifyProject } from "@/lib/api";
import { format, t } from "@/lib/i18n";

// Once a form is locked and sent, its class is part of what the filing company
// is reviewing. Redoing it in place would make the document they hold describe
// a different project, so the API refuses -- and the card says so rather than
// offering a button that returns an error.
const SENT_STATES = [
  "FORM_FROZEN",
  "INSTITUTION_REVIEW",
  "INSTITUTION_RETURNED",
  "READY_FOR_EXTERNAL_FILING",
  "FILED",
];

/**
 * "The rules changed" — and what to do about it.
 *
 * A policy update marks a project stale and notifies its creator. Threshold
 * changes recalculate the tier on their own; subject-rule changes deliberately
 * do not, because re-deciding a subject match needs the whole chain and a
 * person who asked for it. That left the creator holding a notice about their
 * answer being out of date with no way to get a new one.
 */
export function PolicyStaleNotice({
  projectId,
  stale,
  state,
  currentTier,
  onChange,
  onError,
}: {
  projectId: string;
  stale: boolean;
  state: string | null;
  /** Read before the re-run, so the card can say whether the answer moved. */
  currentTier: string | null;
  onChange: () => void;
  onError: (message: string | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<string | null>(null);

  if (!stale) return null;

  const sent = state !== null && SENT_STATES.includes(state);

  async function rerun() {
    const previousTier = currentTier;
    setBusy(true);
    onError(null);
    try {
      const result = await reclassifyProject(projectId);
      const nextTier = result.classification?.tier ?? null;
      setOutcome(
        previousTier && nextTier && previousTier !== nextTier
          ? format("stale.changed", {
              from: t(`tier.${previousTier}.name`),
              to: t(`tier.${nextTier}.name`),
            })
          : t("stale.unchanged")
      );
      onChange();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>{t("stale.title")}</h2>
      <p className="alert warning-alert">{t("stale.body")}</p>

      {sent ? (
        <p className="muted">{t("stale.locked")}</p>
      ) : (
        <>
          <p>
            <button
              type="button"
              className="primary-button"
              disabled={busy}
              onClick={() => void rerun()}
            >
              {busy ? t("stale.working") : t("stale.action")}
            </button>
          </p>
          <p className="muted">{t("stale.hint")}</p>
        </>
      )}

      {outcome ? <p className="alert">{outcome}</p> : null}
    </section>
  );
}
