"use client";

import { type BudgetBand } from "@/lib/api";
import { format, t } from "@/lib/i18n";

/**
 * What each budget level would cost you, before you have picked one.
 *
 * At the idea stage the budget question has no answer, so the product asks it
 * the other way round: here is what each level means, plan against it. That is
 * the one thing a creator with a premise and nothing else can actually act on.
 *
 * Every column is read from the pinned snapshot by `core/comparison.py` —
 * boundaries from the threshold set, authority and filing duty from the filing
 * routes, and "steps you do yourself" counted from the process template rather
 * than scored. Nothing here is an estimate, which is why the deadline column is
 * empty for two of the three classes: the regulation states one only for
 * one-class, and a plausible-looking guess in the other two is a number someone
 * would build a schedule around.
 */
export function BudgetComparison({
  bands,
  currentTier,
  locked,
}: {
  bands: BudgetBand[];
  /** Highlighted as where this project stands today, when it has a class. */
  currentTier?: string | null;
  /** A special subject fixes the class whatever the budget, so the table
   *  becomes a statement rather than a set of options. */
  locked?: boolean;
}) {
  if (!bands.length) return null;

  return (
    <section className="card">
      <h2>{t("compare.title")}</h2>
      <p className="muted">
        {locked ? t("compare.locked") : t("compare.intro")}
      </p>

      <div className="scroll-x">
        <table className="compare-table">
          <thead>
            <tr>
              <th>{t("compare.budget")}</th>
              <th>{t("compare.class")}</th>
              <th>{t("compare.who")}</th>
              <th>{t("compare.before")}</th>
              <th>{t("compare.deadline")}</th>
              <th>{t("compare.effort")}</th>
            </tr>
          </thead>
          <tbody>
            {bands.map((band) => {
              const here = !locked && currentTier === band.tier;
              return (
                <tr key={band.tier} className={here ? "compare-here" : undefined}>
                  <td>
                    {t(`compare.band.${band.amount_bracket}`)
                      .replace("{lower}", band.lower_rmb.toLocaleString())
                      .replace("{upper}", band.upper_rmb.toLocaleString())}
                    {here ? (
                      <span className="badge"> {t("compare.you_are_here")}</span>
                    ) : null}
                  </td>
                  <td>{t(`tier.${band.tier}.name`)}</td>
                  <td>{t(`filing.authority.${band.authority}`)}</td>
                  <td>{t(`compare.before.${band.pre_shoot_filing}`)}</td>
                  <td>
                    {band.statutory_deadline_key ? (
                      t(band.statutory_deadline_key)
                    ) : (
                      /* Not stated in the regulation. Rendered as such rather
                         than as a dash, which reads as "none" or "instant". */
                      <span className="muted">{t("compare.deadline.unstated")}</span>
                    )}
                  </td>
                  <td>
                    {format("compare.steps", {
                      yours: band.steps_yours,
                      total: band.steps_total
                    })}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="muted">{t("compare.footnote")}</p>
    </section>
  );
}
