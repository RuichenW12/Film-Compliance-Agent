"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  getRun,
  listPendingProposals,
  listSnapshots,
  type PolicyRun,
  type ProposalSummary,
  type SnapshotSummary,
  startCrawl,
} from "@/lib/policy-api";


const SOURCE_ID = "nrta_micro_drama";
const TERMINAL_STATUSES = new Set([
  "no_change",
  "proposal_created",
  "failed",
]);


function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}


function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Policy request failed";
}


export function PolicyAdminPage({
  pollDelayMs = 1000,
}: {
  pollDelayMs?: number;
}) {
  const [proposals, setProposals] = useState<ProposalSummary[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [currentRun, setCurrentRun] = useState<PolicyRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [crawling, setCrawling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const resolveTimerRef = useRef<(() => void) | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [nextProposals, nextSnapshots] = await Promise.all([
        listPendingProposals(),
        listSnapshots(),
      ]);
      if (!mountedRef.current) return;
      setProposals(nextProposals);
      setSnapshots(nextSnapshots);
      setError(null);
    } catch (loadError) {
      if (mountedRef.current) setError(errorMessage(loadError));
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  const waitForPoll = useCallback(
    () =>
      new Promise<void>((resolve) => {
        resolveTimerRef.current = resolve;
        timerRef.current = setTimeout(() => {
          timerRef.current = null;
          resolveTimerRef.current = null;
          resolve();
        }, pollDelayMs);
      }),
    [pollDelayMs],
  );

  useEffect(() => {
    mountedRef.current = true;
    void loadData();
    return () => {
      mountedRef.current = false;
      if (timerRef.current !== null) clearTimeout(timerRef.current);
      timerRef.current = null;
      resolveTimerRef.current?.();
      resolveTimerRef.current = null;
    };
  }, [loadData]);

  async function handleCrawl() {
    setCrawling(true);
    setError(null);
    try {
      const started = await startCrawl(SOURCE_ID);
      while (mountedRef.current) {
        const run = await getRun(started.run_id);
        if (!mountedRef.current) return;
        setCurrentRun(run);
        if (TERMINAL_STATUSES.has(run.status)) {
          if (run.status === "failed") {
            throw new Error(run.error ?? "Policy crawl failed");
          }
          await loadData();
          return;
        }
        await waitForPoll();
      }
    } catch (crawlError) {
      if (mountedRef.current) setError(errorMessage(crawlError));
    } finally {
      if (mountedRef.current) setCrawling(false);
    }
  }

  return (
    <main className="page-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">Policy loop · Gate 3</p>
          <h1>Policy Administration</h1>
          <p className="page-intro">
            Review deterministic policy changes before publishing a new
            snapshot.
          </p>
        </div>
        <span className="fixture-badge">Synthetic local fixture</span>
      </header>

      {error ? (
        <p role="alert" className="alert error-alert">
          {error}
        </p>
      ) : null}

      <section className="panel" aria-labelledby="crawl-heading">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Manual refresh</p>
            <h2 id="crawl-heading">Fixture crawl</h2>
          </div>
          <button
            className="primary-button"
            type="button"
            disabled={crawling || loading}
            onClick={() => void handleCrawl()}
          >
            {crawling ? "Running crawl…" : "Run fixture crawl"}
          </button>
        </div>
        {currentRun ? (
          <dl className="status-grid">
            <div>
              <dt>Run</dt>
              <dd>{currentRun.run_id}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <span className={`status status-${currentRun.status}`}>
                  {currentRun.status}
                </span>
              </dd>
            </div>
            <div>
              <dt>Finished</dt>
              <dd>
                {currentRun.finished_at
                  ? formatDate(currentRun.finished_at)
                  : "In progress"}
              </dd>
            </div>
          </dl>
        ) : (
          <p className="muted">No manual crawl has run in this process.</p>
        )}
      </section>

      <section className="panel" aria-labelledby="proposal-heading">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Human confirmation required</p>
            <h2 id="proposal-heading">Pending proposals</h2>
          </div>
          <span className="count-badge">{proposals.length}</span>
        </div>
        {loading ? <p className="muted">Loading proposals…</p> : null}
        {!loading && proposals.length === 0 ? (
          <p className="empty-state">No pending proposals.</p>
        ) : null}
        <div className="proposal-list">
          {proposals.map((proposal) => (
            <article className="proposal-card" key={proposal.proposal_id}>
              <div>
                <p className="item-id">{proposal.proposal_id}</p>
                <h3>{proposal.summary}</h3>
                <p className="muted">
                  Effective {formatDate(proposal.effective_from)}
                </p>
              </div>
              <div className="proposal-meta">
                <div className="chip-row" aria-label="Impact nodes">
                  {proposal.impact.map((node) => (
                    <span className="chip" key={node}>
                      {node}
                    </span>
                  ))}
                </div>
                <Link
                  className="text-link"
                  href={`/admin/policy/proposals/${proposal.proposal_id}`}
                >
                  Review proposal
                </Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel" aria-labelledby="snapshot-heading">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Version history</p>
            <h2 id="snapshot-heading">Published snapshots</h2>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Effective</th>
                <th>Publisher</th>
                <th>Thresholds</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((snapshot) => (
                <tr key={snapshot.version}>
                  <td>
                    <strong>{snapshot.version}</strong>
                  </td>
                  <td>{formatDate(snapshot.effective_from)}</td>
                  <td>{snapshot.published_by}</td>
                  <td>
                    {snapshot.thresholds_published
                      ? "Published"
                      : "Not published"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
