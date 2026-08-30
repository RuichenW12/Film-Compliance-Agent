"use client";

import { format, t } from "@/lib/i18n";

/** 总局令第16号 article 2 defines a micro-drama as under twenty minutes an
 *  episode. At or above that line the work is a web film, which follows a
 *  different path entirely and is not what this tool checks. The figure lives
 *  in the snapshot as `episode_max_minutes_exclusive`; it is repeated here
 *  only to draw the line, and the classification is still made server-side. */
const WEB_FILM_MINUTES = 20;

/** Not from the regulation. Article 2 says 剧集 -- a series -- without giving
 *  a number, so this threshold is our own reading and the interface says so
 *  rather than presenting it as law. */
const SERIES_MINIMUM = 3;

/**
 * Episode length, as something you adjust and watch rather than type.
 *
 * These two numbers cannot be skipped: article 2 defines a micro-drama *by*
 * episode length, so without them the chain cannot tell one from a web film.
 * But asking a creator at the idea stage to type a number they have not
 * decided produced the worst of both worlds -- and folding the fields away was
 * worse still, because the form went on submitting its defaults where nobody
 * could see them. A default nobody sees is an invented fact; a suggestion
 * somebody looks at and adjusts is their answer.
 *
 * So the values start somewhere sensible and show their consequence as they
 * move. The line that matters is twenty minutes, and crossing it does not
 * change your class -- it takes you off this path altogether.
 */
export function LengthPicker({
  episodeCount,
  episodeMinutes,
  onCountChange,
  onMinutesChange,
}: {
  episodeCount: string;
  episodeMinutes: string;
  onCountChange: (next: string) => void;
  onMinutesChange: (next: string) => void;
}) {
  const minutes = Number(episodeMinutes) || 0;
  const count = Number(episodeCount) || 0;

  const isWebFilm = minutes >= WEB_FILM_MINUTES;
  const tooFewEpisodes = count > 0 && count < SERIES_MINIMUM;

  return (
    <div className="length-picker">
      <label>
        <span>{t("length.minutes")}</span>
        <input
          type="range"
          min={1}
          max={30}
          step={0.5}
          value={episodeMinutes}
          onChange={(event) => onMinutesChange(event.target.value)}
          aria-describedby="length-verdict"
        />
        <output>{format("length.minutes_value", { minutes })}</output>
      </label>

      {/* The consequence, live. This is the whole point of a slider over a
          number box: you can see the boundary before you cross it. */}
      <p
        id="length-verdict"
        className={isWebFilm ? "alert warning-alert" : "alert"}
      >
        {isWebFilm
          ? t("length.verdict.web_film")
          : format("length.verdict.micro_drama", { minutes })}
      </p>

      <label>
        <span>{t("length.episodes")}</span>
        <input
          type="number"
          min={1}
          value={episodeCount}
          onChange={(event) => onCountChange(event.target.value)}
        />
      </label>

      {tooFewEpisodes ? (
        <p className="muted">
          {format("length.too_few", { minimum: SERIES_MINIMUM })}
        </p>
      ) : null}

      <p className="muted">{t("length.hint")}</p>
    </div>
  );
}
