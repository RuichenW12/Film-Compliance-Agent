"use client";

import { useState } from "react";

import { apiFetch } from "@/lib/api";
import { t } from "@/lib/i18n";

interface HelpResponse {
  answer: string;
  clause_refs: string[];
  snapshot_version: string;
  pending_flags: string[];
}

/**
 * The question mark beside an intake field.
 *
 * Two layers, in order of how often they are enough:
 *
 * 1. A **static hint and an example**, from the locale bundle. No network, no
 *    model, always there — hovering the label shows it, and opening the panel
 *    shows it in full. Most confusion ends here.
 * 2. A **question**, answered from the clauses behind that field. For the cases
 *    a sentence of hint cannot cover: what counts as sponsor-promoted, why the
 *    AI checkbox changes anything.
 *
 * The reply is prose and clause ids. It has no value field and no way to touch
 * the input beside it — the creator answers the form, the model only explains
 * what is being asked.
 */
export function FieldHelp({ field, label }: { field: string; label: string }) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<HelpResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hint = t(`help.${field}`);
  const example = t(`help.${field}.example`);
  const hasHint = hint !== `help.${field}`;
  const hasExample = example !== `help.${field}.example`;

  async function ask() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      setAnswer(
        await apiFetch<HelpResponse>("/v1/intake/explain", {
          method: "POST",
          body: JSON.stringify({ field, question: question.trim(), label }),
        })
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="field-help">
      <button
        type="button"
        className="field-help-toggle"
        aria-expanded={open}
        aria-label={t("help.open").replace("{field}", label)}
        title={hasHint ? hint : undefined}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
      >
        ?
      </button>

      {open ? (
        <div className="field-help-panel">
          {hasHint ? <p className="field-help-hint">{hint}</p> : null}
          {hasExample ? (
            <p className="field-help-example">
              {t("help.example_label")} <code>{example}</code>
            </p>
          ) : null}

          {/* Not a <form>. This panel lives inside the wizard's form, and a
              nested form is invalid: the browser warns, the inner submit reaches
              the outer form, and the page reloads — which it did, wiping the
              answer between the 200 coming back and anything rendering it. */}
          <div className="field-help-ask">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void ask();
                }
              }}
              placeholder={t("help.ask_placeholder")}
              aria-label={t("help.ask_placeholder")}
            />
            <button type="button" onClick={() => void ask()} disabled={busy}>
              {busy ? t("help.asking") : t("help.ask")}
            </button>
          </div>

          {error ? (
            <p className="alert" role="alert">
              {error}
            </p>
          ) : null}

          {answer ? (
            answer.pending_flags.includes("intake_help_pending") ? (
              <p className="muted">{t("help.unavailable")}</p>
            ) : answer.pending_flags.includes("no_clauses_for_field") ? (
              <p className="muted">{t("help.no_clauses")}</p>
            ) : (
              <div className="field-help-answer">
                <p>{answer.answer}</p>
                {answer.clause_refs.length ? (
                  /* Which clauses this was drawn from. An explanation that
                     cannot name its source is the thing this product refuses
                     to produce anywhere else. */
                  <p className="field-help-sources">
                    {t("help.from")}{" "}
                    {answer.clause_refs.map((ref) => (
                      <code key={ref}>{ref}</code>
                    ))}{" "}
                    <span className="muted">
                      ({t("help.snapshot")} {answer.snapshot_version})
                    </span>
                  </p>
                ) : null}
              </div>
            )
          ) : null}
        </div>
      ) : null}
    </span>
  );
}
