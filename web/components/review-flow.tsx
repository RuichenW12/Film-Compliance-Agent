"use client";

import { useEffect, useState } from "react";

import styles from "@/app/review-flow.module.css";
import { ApiError } from "@/lib/api";
import {
  confirmReview,
  createIdeaReview,
  createScriptReview,
  getReview,
  retryReviewIntake,
  type ConfirmedReviewDetails,
  type ReviewView,
} from "@/lib/reviews-api";
import { ConfirmStep } from "./confirm-step";
import { ResultsStep } from "./results-step";
import { UploadStep } from "./upload-step";


function ProgressSteps({ active }: { active: number }) {
  return (
    <ol className={styles.progress} aria-label="Review progress">
      {["Upload", "Confirm details", "Review results"].map((label, index) => (
        <li key={label} className={index + 1 <= active ? styles.progressActive : ""} aria-current={index + 1 === active ? "step" : undefined}>
          <span>{String(index + 1).padStart(2, "0")}</span>{label}
        </li>
      ))}
    </ol>
  );
}


export function ReviewFlow({ initialReviewId }: { initialReviewId?: string }) {
  const [review, setReview] = useState<ReviewView | null>(null);
  const [busy, setBusy] = useState<"restore" | "upload" | "analyze" | "retry" | null>(initialReviewId ? "restore" : null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!initialReviewId) return;
    let active = true;
    getReview(initialReviewId)
      .then((value) => { if (active) setReview(value); })
      .catch((caught) => { if (active) setError(messageFor(caught)); })
      .finally(() => { if (active) setBusy(null); });
    return () => { active = false; };
  }, [initialReviewId]);

  function remember(value: ReviewView) {
    setReview(value);
    const url = new URL(window.location.href);
    url.search = "";
    url.searchParams.set("review", value.review_id);
    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }

  async function run(action: () => Promise<ReviewView>, pending: typeof busy) {
    setBusy(pending);
    setError(null);
    try {
      remember(await action());
    } catch (caught) {
      setError(messageFor(caught));
    } finally {
      setBusy(null);
    }
  }

  const activeStep = review?.state === "COMPLETE" || busy === "analyze" ? 3 : review ? 2 : 1;

  return (
    <div className={styles.flowShell}>
      <ProgressSteps active={activeStep} />
      {error ? <div className={styles.error} role="alert"><strong>We couldn’t continue.</strong>{error}</div> : null}
      {busy === "restore" ? <div className={styles.processing} role="status">Restoring your review…</div> : null}
      {busy === "analyze" ? (
        <section className={styles.processingPanel} aria-live="polite">
          <span className={styles.processingMark} aria-hidden="true">◎</span>
          <h1>Classifying project and reviewing scenes…</h1>
          <p>Preparing the risk summary and review files from your confirmed details.</p>
        </section>
      ) : review?.state === "COMPLETE" ? (
        <ResultsStep review={review} />
      ) : review?.state === "AWAITING_CONFIRMATION" ? (
        <ConfirmStep
          key={review.review_id}
          review={review}
          onConfirm={(details: ConfirmedReviewDetails) => run(() => confirmReview(review.review_id, details), "analyze")}
          onRetry={() => run(() => retryReviewIntake(review.review_id), "retry")}
        />
      ) : !review && busy !== "restore" ? (
        <UploadStep
          busy={busy === "upload"}
          onUpload={(file) => run(() => createScriptReview(file), "upload")}
          onIdea={() => run(createIdeaReview, "upload")}
        />
      ) : review ? (
        <section className={styles.processingPanel} aria-live="polite">
          <h1>Preparing your review…</h1>
          <p>The saved session is still being processed.</p>
        </section>
      ) : null}
    </div>
  );
}


function messageFor(caught: unknown): string {
  if (caught instanceof ApiError) return caught.message;
  return caught instanceof Error ? caught.message : String(caught);
}
