"use client";

import { useState } from "react";

import {
  type FormDraft,
  type GateResult,
  confirmField,
  deferField,
  freezeForm,
  getForm,
  getGate,
  passGate,
} from "@/lib/api";
import { format, t } from "@/lib/i18n";

/** Fields the filing company supplies rather than the creator.
 *
 *  `applicant_entity` is the case this exists for: a 备案 is filed by a company
 *  holding the 广播电视节目制作经营许可证, so an individual creator has nothing
 *  to put there and should not invent one. Offering the button everywhere would
 *  turn a narrow, defensible gap into a way around every question. */
const DEFERRABLE = ["applicant_entity", "investment_structure"];

/** A gap item is a form field key or a material id; name whichever it is.
 *
 *  Material ids arrive as `mat_synopsis` while the bundle keys them
 *  `material.synopsis`, so the prefix has to come off. Falling through to the
 *  raw key is the defect D-040 fixed on the result card, and it reappeared
 *  here the moment a second surface rendered the same data. */
function nameGapItem(item: string): string {
  const asField = t(`field.${item}`);
  if (asField !== `field.${item}`) return asField;
  const asMaterial = t(`material.${item.replace(/^mat_/, "")}`);
  if (!asMaterial.startsWith("material.")) return asMaterial;
  return item;
}

/**
 * The 备案 form, what still blocks it, and the lock at the end.
 *
 * Two things this deliberately does not do. It does not hide the gate behind
 * the freeze button -- a creator who cannot finish should be able to read why
 * in a sentence rather than by pressing something and getting a 409. And it
 * does not let a field be typed into once the form is frozen: a frozen form is
 * a record of what was approved, so editing it is a new draft, not an edit.
 */
export function FilingForm({
  projectId,
  form,
  gate,
  onChange,
  onError,
}: {
  projectId: string;
  form: FormDraft | null;
  gate: GateResult | null;
  onChange: (form: FormDraft, gate: GateResult) => void;
  onError: (message: string | null) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  if (!form) return null;

  async function run(label: string, work: () => Promise<unknown>) {
    setBusy(label);
    onError(null);
    try {
      await work();
      const [nextForm, nextGate] = await Promise.all([
        getForm(projectId),
        getGate(projectId),
      ]);
      onChange(nextForm, nextGate);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  const entries = Object.entries(form.fields).sort(([a], [b]) =>
    a.localeCompare(b)
  );
  const blocking = entries.filter(([, field]) => field.status === "pending");

  return (
    <section className="card">
      <h2>{t("form.title")}</h2>

      {form.frozen ? (
        <p className="alert">
          {format("form.frozen", { hash: (form.hash ?? "").slice(0, 12) })}
        </p>
      ) : (
        <p className="muted">{t("form.intro")}</p>
      )}

      <table className="form-table">
        <tbody>
          {entries.map(([key, field]) => {
            const filled = field.status === "filled";
            const declared = field.status === "pending_institution";
            return (
              <tr key={key}>
                <td>{t(`field.${key}`)}</td>
                <td>
                  {filled ? (
                    String(field.value)
                  ) : (
                    <span className="muted">{t("form.pending")}</span>
                  )}
                  {declared ? (
                    <span className="badge"> {t("form.declared")}</span>
                  ) : null}
                  {field.status === "conflict" ? (
                    <span className="badge"> {t("form.conflict")}</span>
                  ) : null}
                </td>
                <td>
                  {form.frozen || filled || declared ? null : (
                    <>
                      <input
                        value={drafts[key] ?? ""}
                        placeholder={t("form.answer_placeholder")}
                        onChange={(event) =>
                          setDrafts({ ...drafts, [key]: event.target.value })
                        }
                        size={18}
                      />
                      <button
                        type="button"
                        disabled={busy !== null || !(drafts[key] ?? "").trim()}
                        onClick={() =>
                          run(`confirm:${key}`, () =>
                            confirmField(projectId, key, drafts[key].trim())
                          )
                        }
                      >
                        {t("form.confirm")}
                      </button>
                      {DEFERRABLE.includes(key) ? (
                        <button
                          type="button"
                          disabled={busy !== null}
                          title={t(`form.defer.why.${key}`)}
                          onClick={() =>
                            run(`defer:${key}`, () =>
                              deferField(projectId, key, t(`form.defer.why.${key}`))
                            )
                          }
                        >
                          {t("form.defer")}
                        </button>
                      ) : null}
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Why the form will not close, in words, before anyone presses anything. */}
      {gate && !gate.passed ? (
        <>
          <h3>{t("form.blocked")}</h3>
          <ul>
            {gate.gaps.map((gap) => (
              <li key={gap.check}>
                {t(`check.${gap.check}`)}
                {gap.items.length ? (
                  <span className="muted">
                    {" — "}
                    {gap.items.map(nameGapItem).join(", ")}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
          {blocking.length ? (
            <p className="muted">{t("form.blocked.hint")}</p>
          ) : null}
        </>
      ) : null}

      {form.frozen ? null : (
        <p>
          <button
            type="button"
            className="primary-button"
            /* Disabled rather than allowed-then-refused: the gaps are listed
               above, so a creator reads why instead of discovering it as a
               409. */
            disabled={busy !== null || !gate?.passed}
            onClick={() =>
              run("freeze", async () => {
                // The gate is already open by computation; this records the
                // transition. Already-passed is not an error worth surfacing.
                await passGate(projectId).catch(() => undefined);
                await freezeForm(projectId);
              })
            }
          >
            {busy === "freeze" ? t("form.freezing") : t("form.freeze")}
          </button>
        </p>
      )}
      <p className="muted">{t("form.freeze.hint")}</p>
    </section>
  );
}
