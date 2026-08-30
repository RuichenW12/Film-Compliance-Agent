"use client";

import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import styles from "@/app/review-flow.module.css";
import { ApiError } from "@/lib/api";
import {
  confirmReview,
  createIdeaReview,
  createScriptReview,
  getReview,
  reanalyzeReview,
  retryReviewIntake,
  type ConfirmedReviewDetails,
  type ReviewView,
} from "@/lib/reviews-api";
import { ConfirmStep } from "./confirm-step";
import { ResultsStep } from "./results-step";
import { UploadStep } from "./upload-step";


type Step = 1 | 2 | 3;

const STEP_LABELS = ["Upload", "Confirm details", "Review results"] as const;

function serverStepFor(review: ReviewView | null): Step {
  if (!review) return 1;
  if (["ANALYZING", "COMPLETE"].includes(review.state)) return 3;
  return 2;
}

function ProgressSteps({
  selected,
  furthest,
  disabled,
  onSelect,
}: {
  selected: Step;
  furthest: Step;
  disabled: boolean;
  onSelect: (step: Step) => void;
}) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  function moveFrom(step: Step, event: KeyboardEvent<HTMLButtonElement>) {
    const available = STEP_LABELS.map((_, index) => (index + 1) as Step).filter(
      (candidate) => candidate <= furthest
    );
    let destination: Step | undefined;
    if (event.key === "Home") destination = available[0];
    if (event.key === "End") destination = available.at(-1);
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      destination = available[(available.indexOf(step) + 1) % available.length];
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      destination = available[(available.indexOf(step) - 1 + available.length) % available.length];
    }
    if (!destination) return;
    event.preventDefault();
    onSelect(destination);
    tabRefs.current[destination - 1]?.focus();
  }

  return (
    <div className={styles.progress} role="tablist" aria-label="Review progress">
      {STEP_LABELS.map((label, index) => {
        const step = (index + 1) as Step;
        return (
          <button
            key={label}
            ref={(node) => { tabRefs.current[index] = node; }}
            id={`review-step-tab-${step}`}
            type="button"
            role="tab"
            aria-controls="review-step-panel"
            aria-selected={selected === step}
            tabIndex={selected === step ? 0 : -1}
            className={step <= furthest ? styles.progressActive : ""}
            disabled={disabled || step > furthest}
            onClick={() => onSelect(step)}
            onKeyDown={(event) => moveFrom(step, event)}
          >
            <span>{String(step).padStart(2, "0")}</span>{label}
          </button>
        );
      })}
    </div>
  );
}


export function ReviewFlow({ initialReviewId }: { initialReviewId?: string }) {
  const [review, setReview] = useState<ReviewView | null>(null);
  const [busy, setBusy] = useState<"restore" | "upload" | "analyze" | "retry" | null>(initialReviewId ? "restore" : null);
  const [error, setError] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState<Step>(1);
  const [furthestStep, setFurthestStep] = useState<Step>(1);
  const [focusContent, setFocusContent] = useState(true);

  useEffect(() => {
    if (!initialReviewId) return;
    let active = true;
    getReview(initialReviewId)
      .then((value) => { if (active) remember(value); })
      .catch((caught) => { if (active) setError(messageFor(caught)); })
      .finally(() => { if (active) setBusy(null); });
    return () => { active = false; };
  }, [initialReviewId]);

  useEffect(() => {
    if (!review || !["UPLOADING", "EXTRACTING", "ANALYZING"].includes(review.state)) return;
    let active = true;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const value = await getReview(review.review_id);
        if (!active) return;
        remember(value);
        if (["UPLOADING", "EXTRACTING", "ANALYZING"].includes(value.state)) {
          timer = window.setTimeout(poll, 600);
        }
      } catch (caught) {
        if (!active) return;
        setError(messageFor(caught));
        timer = window.setTimeout(poll, 1200);
      }
    };
    timer = window.setTimeout(poll, 600);
    return () => { active = false; if (timer !== undefined) window.clearTimeout(timer); };
  }, [review?.review_id, review?.state]);

  function remember(value: ReviewView) {
    const serverStep = serverStepFor(value);
    const sameSession = review?.review_id === value.review_id;
    setReview(value);
    setFurthestStep((current) => sameSession ? Math.max(current, serverStep) as Step : serverStep);
    setSelectedStep(serverStep);
    setFocusContent(true);
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

  async function confirm(details: ConfirmedReviewDetails) {
    if (!review) return;
    setBusy("analyze");
    setError(null);
    try {
      const submit = review.state === "COMPLETE" ? reanalyzeReview : confirmReview;
      remember(await submit(review.review_id, details));
    } catch (caught) {
      setError(messageFor(caught));
      try { remember(await getReview(review.review_id)); } catch {}
    } finally {
      setBusy(null);
    }
  }

  function startOver() {
    setReview(null);
    setError(null);
    setSelectedStep(1);
    setFurthestStep(1);
    setFocusContent(true);
    const url = new URL(window.location.href);
    url.searchParams.delete("review");
    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }

  const processing = Boolean(review && ["UPLOADING", "EXTRACTING", "ANALYZING"].includes(review.state));
  const tabsDisabled = busy !== null || processing;

  function selectStep(step: Step, shouldFocusContent = false) {
    if (tabsDisabled || step > furthestStep) return;
    setFocusContent(shouldFocusContent);
    setSelectedStep(step);
  }

  let content = null;
  if (busy === "restore") {
    content = <div className={styles.processing} role="status">Restoring your review…</div>;
  } else if (busy === "analyze" || processing) {
    content = (
      <section className={styles.processingPanel} aria-live="polite">
        <span className={styles.processingMark} aria-hidden="true">◎</span>
        <h1>Classifying project and reviewing scenes…</h1>
        <p>Preparing the risk summary and review files from your confirmed details.</p>
      </section>
    );
  } else if (review?.state === "FAILED") {
    content = (
      <section className={styles.processingPanel} aria-labelledby="failed-heading">
        <span className={styles.processingMark} aria-hidden="true">!</span>
        <h1 id="failed-heading">Review could not be completed.</h1>
        <p>{review.failure_message ?? "Start a new review and upload the source again."}</p>
        <button className={styles.primaryAction} type="button" onClick={startOver}>Start a new review</button>
      </section>
    );
  } else if (selectedStep === 1) {
    content = (
      <UploadStep
        busy={busy === "upload"}
        currentReview={review?.mode === "script" ? review : undefined}
        autoFocus={focusContent}
        onContinue={() => selectStep(furthestStep, true)}
        onUpload={(file) => run(() => createScriptReview(file), "upload")}
        onIdea={() => run(createIdeaReview, "upload")}
      />
    );
  } else if (selectedStep === 2 && review) {
    content = (
      <ConfirmStep
        key={`${review.review_id}-${review.state}`}
        review={review}
        autoFocus={focusContent}
        onConfirm={confirm}
        onRetry={() => run(() => retryReviewIntake(review.review_id), "retry")}
      />
    );
  } else if (selectedStep === 3 && review?.state === "COMPLETE") {
    content = <ResultsStep review={review} autoFocus={focusContent} />;
  } else if (review) {
    content = (
      <section className={styles.processingPanel} aria-live="polite">
        <h1>Preparing your review…</h1>
        <p>The saved session is still being processed.</p>
      </section>
    );
  }

  return (
    <div className={styles.flowShell}>
      <ProgressSteps
        selected={selectedStep}
        furthest={furthestStep}
        disabled={tabsDisabled}
        onSelect={(step) => selectStep(step)}
      />
      {error ? <div className={styles.error} role="alert"><strong>We couldn’t continue.</strong>{error}</div> : null}
      <div
        id="review-step-panel"
        role="tabpanel"
        aria-labelledby={`review-step-tab-${selectedStep}`}
      >
        {content}
      </div>
    </div>
  );
}


function messageFor(caught: unknown): string {
  if (caught instanceof ApiError) return caught.message;
  return caught instanceof Error ? caught.message : String(caught);
}
