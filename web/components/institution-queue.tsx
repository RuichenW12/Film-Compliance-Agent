"use client";

import { useCallback, useEffect, useState } from "react";

import { type QueueRow, getInstitutionQueue } from "@/lib/api";
import { format, t } from "@/lib/i18n";

/**
 * What is waiting on this institution.
 *
 * The console could previously open a project only if somebody handed over its
 * id, which made it a lookup tool rather than an inbox -- and is why the
 * reviewer side felt unbuilt when every route behind it already worked.
 *
 * Two states appear here. A project in `INSTITUTION_REVIEW` needs a decision.
 * One in `READY_FOR_EXTERNAL_FILING` has been accepted and still needs its
 * registration number, which is also the institution's act; dropping it at
 * acceptance would let a project fall off the screen with the last step
 * undone.
 */
export function InstitutionQueue({
  onOpen,
  reloadKey,
  onError,
}: {
  onOpen: (projectId: string) => void;
  reloadKey: number;
  onError: (message: string | null) => void;
}) {
  const [rows, setRows] = useState<QueueRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  /* Distinguishes "not loaded yet" from "tried and could not". Without it a
     failed load leaves `rows` null forever and the card sits on "Loading…",
     which reads as a hang rather than the 403 it usually is. */
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRows(await getInstitutionQueue());
      setFailed(false);
      onError(null);
    } catch (caught) {
      setFailed(true);
      onError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
    // `onError` is a setState function and stable for the life of the page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reloads when the parent acts on a project, so a decision removes the row
  // it was made on rather than leaving a stale queue on screen.
  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  return (
    <section className="card">
      <h2>{t("queue.title")}</h2>
      <p className="muted">{t("queue.intro")}</p>

      {failed ? (
        <p className="muted">{t("queue.unavailable")}</p>
      ) : rows === null ? (
        <p className="muted">{t("queue.loading")}</p>
      ) : rows.length === 0 ? (
        <p className="muted">{t("queue.empty")}</p>
      ) : (
        <div className="scroll-x">
          <table className="queue-table">
            <thead>
              <tr>
                <th>{t("queue.project")}</th>
                <th>{t("queue.class")}</th>
                <th>{t("queue.waiting_for")}</th>
                <th>{t("queue.licence")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.project_id}>
                  <td>
                    {/* Never invented: an unnamed project says so. */}
                    {row.title_working ?? (
                      <span className="muted">{t("queue.untitled")}</span>
                    )}
                    <br />
                    <code className="muted">{row.project_id}</code>
                  </td>
                  <td>{row.tier ? t(`tier.${row.tier}.name`) : "—"}</td>
                  <td>{t(`queue.state.${row.state}`)}</td>
                  <td>
                    {row.licence_reasons.length === 0 ? (
                      <span className="muted">{t("queue.licence.ok")}</span>
                    ) : (
                      <span className="badge">
                        {row.licence_reasons
                          .map((reason) => t(`licence.${reason}`))
                          .join("; ")}
                      </span>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onOpen(row.project_id)}
                    >
                      {t("queue.open")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p>
        <button
          type="button"
          className="secondary-button"
          disabled={busy}
          onClick={() => void load()}
        >
          {busy ? t("queue.refreshing") : t("queue.refresh")}
        </button>
        {rows ? (
          <span className="muted"> {format("queue.count", { n: rows.length })}</span>
        ) : null}
      </p>
    </section>
  );
}
