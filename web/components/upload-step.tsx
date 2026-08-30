"use client";

import { useEffect, useRef, useState } from "react";

import styles from "@/app/review-flow.module.css";
import type { ReviewView } from "@/lib/reviews-api";


interface UploadStepProps {
  busy: boolean;
  currentReview?: ReviewView;
  autoFocus?: boolean;
  onContinue?: () => void;
  onUpload: (file: File) => Promise<void>;
  onIdea: () => Promise<void>;
}


export function UploadStep({
  busy,
  currentReview,
  autoFocus = true,
  onContinue,
  onUpload,
  onIdea,
}: UploadStepProps) {
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  return (
    <section className={styles.stepPanel} aria-labelledby="upload-heading">
      <div className={styles.stepCopy}>
        <p className={styles.eyebrow}>Upload-first review</p>
        <h1 id="upload-heading">Upload a script. Skip the questionnaire.</h1>
        <p className={styles.lede}>
          We extract project details first. Compliance analysis starts only
          after you review and confirm them.
        </p>
      </div>

      <form
        className={styles.uploadCard}
        aria-label="Script upload"
        aria-busy={busy}
        onSubmit={(event) => {
          event.preventDefault();
          if (file) void onUpload(file);
        }}
      >
        {currentReview?.source_filename ? (
          <div className={styles.currentSource} aria-label="Current script">
            <span>Current script</span>
            <strong>{currentReview.source_filename}</strong>
            <small>
              Checksum {currentReview.source_sha256 ?? "Unavailable"}
            </small>
            {onContinue ? (
              <button type="button" onClick={onContinue} disabled={busy}>
                Continue with current script
              </button>
            ) : null}
          </div>
        ) : null}
        <label className={styles.filePicker}>
          <span className={styles.fileIcon} aria-hidden="true">↑</span>
          <span className={styles.fileTitle}>Choose a script</span>
          <span className={styles.fileHint}>Markdown, UTF-8 text, or DOCX · up to 5 MB</span>
          <input
            ref={inputRef}
            type="file"
            aria-label="Choose a script"
            accept=".md,.txt,.docx"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        {file ? (
          <p className={styles.selectedFile} role="status" aria-live="polite">
            {busy ? (
              <>Reading script… {file.name}</>
            ) : (
              <><span aria-hidden="true">✓</span> {file.name}</>
            )}
          </p>
        ) : null}
        <button className={styles.primaryAction} type="submit" disabled={!file || busy}>
          {busy ? "Reading script…" : "Extract project details"}
        </button>
        <p className={styles.trustLine}>
          <span aria-hidden="true">◇</span> Your original file is never modified.
        </p>
      </form>

      <div className={styles.secondaryPath}>
        <span>Starting from scratch?</span>
        <button type="button" onClick={() => void onIdea()} disabled={busy}>
          I only have an idea
        </button>
      </div>
    </section>
  );
}
