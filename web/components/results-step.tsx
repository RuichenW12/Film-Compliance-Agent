"use client";

import { useEffect, useRef, useState } from "react";

import styles from "@/app/review-flow.module.css";
import { downloadReviewFile, reviewDownloadUrl, type ReviewView } from "@/lib/reviews-api";


function displayValue(value: unknown): string {
  if (typeof value !== "string") return "Route requires confirmation";
  const normalized = value.replaceAll("_", " ");
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}


export function ResultsStep({ review, autoFocus = true }: { review: ReviewView; autoFocus?: boolean }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const result = review.classification;

  useEffect(() => {
    if (autoFocus) headingRef.current?.focus();
  }, [autoFocus]);

  if (!result) return null;

  return (
    <section className={styles.resultsPanel} aria-labelledby="results-heading">
      <div className={styles.resultsHero}>
        <p className={styles.eyebrow}>Analysis complete</p>
        <h1 id="results-heading" ref={headingRef} tabIndex={-1}>Review results</h1>
        {review.confirmed?.title ? (
          <p><strong>{review.confirmed.title}</strong></p>
        ) : null}
        <p>
          Routing support for pre-production review. This is not legal advice or approval.
        </p>
      </div>

      <section className={styles.decisionCard} aria-label="Decision summary">
        <div className={styles.classMark} aria-hidden="true">01</div>
        <div className={styles.decisionMain}>
          <span className={styles.decisionLabel}>Recommended route</span>
          <strong>{result.class_name}</strong>
          <div className={styles.subjectRow}>
            {result.subjects.map((subject) => <span key={subject}>{subject}</span>)}
          </div>
        </div>
        <div className={styles.coReview}>
          <span aria-hidden="true">◆</span>
          <div><strong>{result.co_review_required ? "Co-review required" : "No co-review indicated"}</strong><small>Subject rules take priority over the estimated investment band.</small></div>
        </div>
      </section>

      <section className={styles.warning} aria-label="Routing evidence">
        <strong>{displayValue(result.route?.authority)}</strong>
        <span>{` · Policy snapshot ${result.snapshot_version}`}</span>
        <div className={styles.subjectRow}>
          {result.evidence_refs.length
            ? result.evidence_refs.map((reference) => <span key={`${reference.snapshot_version}-${reference.clause_id}`}>{reference.clause_id}</span>)
            : <span>No clause reference; human confirmation required</span>}
        </div>
      </section>

      {review.semantic_status === "pending" ? (
        <div className={styles.warning} role="status">
          <strong>Semantic review is pending.</strong> Deterministic findings are shown below; this result must not be read as a pass.
        </div>
      ) : null}

      <section className={styles.findingsSection} aria-labelledby="findings-heading">
        <div className={styles.sectionTitleRow}>
          <div><p className={styles.eyebrow}>Scene-level review</p><h2 id="findings-heading">Risk findings</h2></div>
          <span className={styles.countPill}>{review.findings.length} found</span>
        </div>
        {review.findings.length ? (
          <div className={styles.findingList}>
            {review.findings.map((finding) => (
              <article className={styles.findingCard} key={finding.risk_id}>
                <div className={styles.findingMeta}>
                  <strong>{finding.risk_id}</strong>
                  <span>{finding.episode ? `Episode ${finding.episode}` : "Episode —"} · {finding.scene ? `Scene ${finding.scene}` : "Scene —"}</span>
                  <span className={styles.humanStatus}>{finding.status}</span>
                </div>
                <blockquote>{finding.quote}</blockquote>
                <p><strong>Category</strong> {displayValue(finding.category)}</p>
                <p>{finding.explanation ?? "A qualified reviewer should confirm this depiction."}</p>
                <p><strong>Evidence</strong> {finding.evidence_refs.length ? finding.evidence_refs.map((reference) => reference.clause_id).join(", ") : "No clause reference; human confirmation required"}</p>
                {finding.suggestion ? <p className={styles.suggestion}><strong>Next step</strong>{finding.suggestion}</p> : null}
              </article>
            ))}
          </div>
        ) : (
          <p className={styles.emptyState}>No rule-based risks detected.</p>
        )}
      </section>

      <section className={styles.packageSection} aria-label="Review package">
        <div className={styles.sectionTitleRow}>
          <div><p className={styles.eyebrow}>Ready to share</p><h2>Review package</h2></div>
          <span className={styles.readyPill}>Files prepared</span>
        </div>
        {downloadError ? <div className={styles.error} role="alert">{downloadError}</div> : null}
        <div className={styles.downloadGrid}>
          {review.artifacts.map((artifact) => (
            <a key={artifact.artifact_type} href={reviewDownloadUrl(artifact.download_url)} download={artifact.filename} onClick={(event) => {
              event.preventDefault();
              setDownloadError(null);
              void downloadReviewFile(artifact.download_url, artifact.filename).catch((caught) => setDownloadError(caught instanceof Error ? caught.message : String(caught)));
            }}>
              <span className={styles.downloadIcon} aria-hidden="true">↓</span>
              <strong>{artifact.filename}</strong>
              <small>{artifact.artifact_type === "annotated-script" ? "Script copy with adjacent review notes" : "Generated review document"}</small>
            </a>
          ))}
          {review.source_download_url ? (
            <a href={reviewDownloadUrl(review.source_download_url)} download={review.source_filename ?? "source-script"} onClick={(event) => {
              event.preventDefault();
              setDownloadError(null);
              void downloadReviewFile(review.source_download_url!, review.source_filename ?? "source-script").catch((caught) => setDownloadError(caught instanceof Error ? caught.message : String(caught)));
            }}>
              <span className={styles.downloadIcon} aria-hidden="true">↧</span>
              <strong>Original source</strong>
              <small>Unmodified · checksum {review.source_sha256?.slice(0, 10)}…</small>
            </a>
          ) : null}
        </div>
      </section>

      <section className={styles.beyondSection} aria-label="Beyond this demo">
        <div><p className={styles.eyebrow}>Showcase only</p><h2>Beyond this demo</h2><p>These capabilities remain outside the interactive demo flow.</p></div>
        <div className={styles.beyondGrid}>
          <article><span>01</span><strong>Institution collaboration</strong><p>Share a prepared package with a qualified filing institution.</p></article>
          <article><span>02</span><strong>Filing workflow</strong><p>Track institution-supplied fields and official filing outcomes.</p></article>
          <article><span>03</span><strong>Live policy updates</strong><p>Review governed policy changes before they affect classifications.</p></article>
        </div>
      </section>
    </section>
  );
}
