"use client";

import { type Finding } from "@/lib/api";
import { format, t } from "@/lib/i18n";

/**
 * The scenes worth watching again, once the work is made.
 *
 * The script pre-check already knows where it found something: `Locator`
 * carries an episode and a scene number. Until now that showed as "ep 3 sc 2"
 * beside a raw category, which is a debug line rather than an instruction.
 *
 * At the production-complete stage it is the most useful thing the product
 * has. Checking a finished micro-drama frame by frame is expensive and out of
 * scope; checking the four scenes the script already flagged is neither. So
 * this turns findings into a short list of places to look, ordered as the work
 * plays rather than as the checker happened to find them.
 *
 * It deliberately stops there. It says where to look and what the script said;
 * it does not claim to have seen the footage, because nothing here has.
 */
export function SceneChecklist({ findings }: { findings: Finding[] }) {
  // A finding with no episode cannot send anyone to a place in the cut. It is
  // still real -- it shows in the pre-check list above -- but it does not
  // belong in a list whose whole purpose is a location.
  const located = findings
    .filter((finding) => finding.locator.episode !== null)
    .sort((a, b) => {
      const episode = (a.locator.episode ?? 0) - (b.locator.episode ?? 0);
      return episode !== 0
        ? episode
        : (a.locator.scene ?? 0) - (b.locator.scene ?? 0);
    });

  if (!located.length) return null;

  return (
    <section className="card">
      <h2>{t("scenes.title")}</h2>
      <p className="muted">{t("scenes.intro")}</p>

      <ol className="scene-list">
        {located.map((finding) => (
          <li key={finding.finding_id}>
            <strong>
              {finding.locator.scene
                ? format("scenes.at", {
                    episode: finding.locator.episode,
                    scene: finding.locator.scene
                  })
                : format("scenes.at_episode", {
                    episode: finding.locator.episode
                  })}
            </strong>{" "}
            <span className="badge">{t(`category.${finding.category}`)}</span>
            {/* The script's own words, so a creator can find the moment. */}
            <div className="scene-quote">“{finding.locator.quote}”</div>
          </li>
        ))}
      </ol>

      <p className="muted">{t("scenes.footnote")}</p>
    </section>
  );
}
