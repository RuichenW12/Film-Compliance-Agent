"use client";

import { useEffect, useRef, useState } from "react";

import styles from "@/app/review-flow.module.css";
import type {
  AmountBracket,
  CandidateValue,
  ConfirmedReviewDetails,
  ReviewView,
} from "@/lib/reviews-api";


interface ConfirmStepProps {
  review: ReviewView;
  autoFocus?: boolean;
  onConfirm: (details: ConfirmedReviewDetails) => Promise<void>;
  onRetry: () => Promise<void>;
}


function textValue(candidate: CandidateValue | null | undefined): string {
  return typeof candidate?.value === "string" ? candidate.value : "";
}

function numberValue(candidate: CandidateValue | null | undefined): string {
  return typeof candidate?.value === "number" ? String(candidate.value) : "";
}

function tagsValue(candidate: CandidateValue | null | undefined): string {
  return Array.isArray(candidate?.value) ? candidate.value.join(", ") : "";
}

function SourceBadge({
  candidate,
  confirmed,
}: {
  candidate: CandidateValue | null | undefined;
  confirmed: boolean;
}) {
  if (confirmed) return <span className={styles.confirmedBadge}>Last confirmed</span>;
  if (!candidate) return <span className={styles.manualBadge}>Manual entry</span>;
  return (
    <span className={candidate.origin === "extracted" ? styles.extractedBadge : styles.suggestedBadge}>
      {candidate.origin === "extracted" ? "Extracted from script" : "AI suggested"}
    </span>
  );
}


export function ConfirmStep({ review, autoFocus = true, onConfirm, onRetry }: ConfirmStepProps) {
  const candidates = review.candidates;
  const confirmed = review.confirmed;
  const [title, setTitle] = useState(confirmed?.title ?? textValue(candidates?.title));
  const [tags, setTags] = useState(confirmed?.tags.join(", ") ?? tagsValue(candidates?.tags));
  const [synopsis, setSynopsis] = useState(confirmed?.synopsis ?? textValue(candidates?.synopsis));
  const [episodeCount, setEpisodeCount] = useState(
    confirmed ? String(confirmed.episode_count) : numberValue(candidates?.episode_count)
  );
  const [episodeMinutes, setEpisodeMinutes] = useState(
    confirmed ? String(confirmed.episode_minutes) : numberValue(candidates?.episode_minutes)
  );
  const [amountBracket, setAmountBracket] = useState(
    confirmed?.amount_bracket ?? textValue(candidates?.amount_bracket) as AmountBracket | ""
  );
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) titleRef.current?.focus();
  }, [autoFocus]);

  const structure = candidates?.structure;
  const extractionNeedsHelp = ["unavailable", "partial"].includes(review.intake_status);

  return (
    <section className={styles.confirmPanel} aria-labelledby="confirm-heading">
      <div className={styles.sectionHeader}>
        <div>
          <p className={styles.eyebrow}>Your confirmation gate</p>
          <h1 id="confirm-heading">Review the extracted details.</h1>
          <p className={styles.lede}>
            Edit anything that looks wrong. These values—not the AI draft—will
            be used for classification and risk analysis.
          </p>
        </div>
        {review.source_filename ? (
          <span className={styles.sourceFile}>{review.source_filename}</span>
        ) : null}
      </div>

      {extractionNeedsHelp ? (
        <div className={styles.warning} role="status">
          <strong>{review.intake_status === "partial" ? "Some suggestions are missing." : "Analysis unavailable."}</strong> Enter or edit the essential details manually.
          <button type="button" onClick={() => void onRetry()}>Retry extraction</button>
        </div>
      ) : review.mode === "idea" ? (
        <p className={styles.manualNotice}>Enter the essential details manually.</p>
      ) : null}

      {structure ? (
        <div className={styles.structureCard}>
          <span>Source script structure</span>
          <strong>
            {structure.source_episode_count ?? "—"} episode · {structure.source_total_minutes ?? "—"} min · {structure.source_scene_count} scenes
          </strong>
          <small>The adaptation suggestion below does not replace this source evidence.</small>
        </div>
      ) : null}

      <form
        className={styles.confirmForm}
        onSubmit={(event) => {
          event.preventDefault();
          void onConfirm({
            title: title.trim(),
            tags: tags.split(",").map((item) => item.trim()).filter(Boolean),
            synopsis: synopsis.trim(),
            episode_count: Number(episodeCount),
            episode_minutes: Number(episodeMinutes),
            amount_bracket: amountBracket as AmountBracket,
          });
        }}
      >
        <label className={styles.fieldWide}>
          <span className={styles.fieldLabel}>Project title <SourceBadge candidate={candidates?.title} confirmed={Boolean(confirmed)} /></span>
          <input ref={titleRef} aria-label="Project title" required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label className={styles.fieldWide}>
          <span className={styles.fieldLabel}>Tags <SourceBadge candidate={candidates?.tags} confirmed={Boolean(confirmed)} /></span>
          <input aria-label="Tags" required value={tags} onChange={(event) => setTags(event.target.value)} aria-describedby="tags-hint" />
          <small id="tags-hint">Separate up to eight tags with commas.</small>
        </label>
        <label className={styles.fieldWide}>
          <span className={styles.fieldLabel}>Synopsis <SourceBadge candidate={candidates?.synopsis} confirmed={Boolean(confirmed)} /></span>
          <textarea aria-label="Synopsis" required rows={5} maxLength={4000} value={synopsis} onChange={(event) => setSynopsis(event.target.value)} />
        </label>
        <label>
          <span className={styles.fieldLabel}>Episode count <SourceBadge candidate={candidates?.episode_count} confirmed={Boolean(confirmed)} /></span>
          <input aria-label="Episode count" required type="number" min="1" max="500" value={episodeCount} onChange={(event) => setEpisodeCount(event.target.value)} />
        </label>
        <label>
          <span className={styles.fieldLabel}>Minutes per episode <SourceBadge candidate={candidates?.episode_minutes} confirmed={Boolean(confirmed)} /></span>
          <input aria-label="Minutes per episode" required type="number" min="0.1" max="60" step="0.1" value={episodeMinutes} onChange={(event) => setEpisodeMinutes(event.target.value)} />
        </label>
        <label className={styles.fieldWide}>
          <span className={styles.fieldLabel}>Investment band <SourceBadge candidate={candidates?.amount_bracket} confirmed={Boolean(confirmed)} /></span>
          <select aria-label="Investment band" required value={amountBracket} onChange={(event) => setAmountBracket(event.target.value as AmountBracket | "")}>
            <option value="" disabled>Select an estimated investment band</option>
            {review.amount_options.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          {candidates?.amount_bracket?.explanation ? <small>{candidates.amount_bracket.explanation}</small> : null}
        </label>
        <div className={styles.confirmAction}>
          <div>
            <strong>Nothing runs until you confirm.</strong>
            <span>You can edit every field above.</span>
          </div>
          <button className={styles.primaryAction} type="submit">
            {review.state === "COMPLETE" ? "Confirm changes & reanalyze" : "Confirm & analyze risks"}
          </button>
        </div>
      </form>
    </section>
  );
}
