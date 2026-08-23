"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  discardProposal,
  getProposal,
  type ProposalDetail,
  publishProposal,
} from "@/lib/policy-api";


function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date(value));
}


function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Policy request failed";
}


export function ProposalDetailPage({ proposalId }: { proposalId: string }) {
  const router = useRouter();
  const [proposal, setProposal] = useState<ProposalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<"publish" | "discard" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void getProposal(proposalId)
      .then((nextProposal) => {
        if (active) setProposal(nextProposal);
      })
      .catch((loadError: unknown) => {
        if (active) setError(errorMessage(loadError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [proposalId]);

  const futureEffective = proposal
    ? Date.parse(proposal.effective_from) > Date.now()
    : false;

  async function runAction(nextAction: "publish" | "discard") {
    setAction(nextAction);
    setError(null);
    try {
      if (nextAction === "publish") {
        await publishProposal(proposalId);
      } else {
        await discardProposal(proposalId);
      }
      router.push("/admin/policy");
    } catch (actionError) {
      setError(errorMessage(actionError));
    } finally {
      setAction(null);
    }
  }

  return (
    <main className="page-shell detail-shell">
      <Link className="back-link" href="/admin/policy">
        ← Back to Policy Administration
      </Link>

      <header className="page-header detail-header">
        <div>
          <p className="eyebrow">Proposal review · {proposalId}</p>
          <h1>{proposal?.summary ?? "Policy proposal"}</h1>
          <p className="page-intro">
            Verify the source change and structured pack update before taking a
            human publication action.
          </p>
        </div>
        <span className="fixture-badge">Synthetic local fixture</span>
      </header>

      {error ? (
        <p role="alert" className="alert error-alert">
          {error}
        </p>
      ) : null}

      {loading ? <section className="panel"><p className="muted">Loading proposal…</p></section> : null}

      {!loading && proposal ? (
        <>
          <section className="panel" aria-labelledby="overview-heading">
            <div className="section-heading">
              <div>
                <p className="section-kicker">Review context</p>
                <h2 id="overview-heading">Proposal overview</h2>
              </div>
              <span className="status">{proposal.status}</span>
            </div>
            <dl className="detail-grid">
              <div>
                <dt>Effective from</dt>
                <dd>{formatDate(proposal.effective_from)}</dd>
              </div>
              <div>
                <dt>Impact</dt>
                <dd className="chip-row">
                  {proposal.impact.map((node) => (
                    <span className="chip" key={node}>{node}</span>
                  ))}
                </dd>
              </div>
            </dl>
            {futureEffective ? (
              <p className="alert warning-alert">
                This proposal is not effective yet. Publish remains disabled
                until its effective time.
              </p>
            ) : null}
          </section>

          <section className="panel" aria-labelledby="diff-heading">
            <p className="section-kicker">Deterministic source change</p>
            <h2 id="diff-heading">Source Diff</h2>
            <pre className="diff-block">{proposal.source_diff_text}</pre>
          </section>

          <section className="panel" aria-labelledby="pack-heading">
            <p className="section-kicker">Read-only structured update</p>
            <h2 id="pack-heading">Draft pack updates</h2>
            <details className="json-details" open>
              <summary>JSON preview</summary>
              <pre>{JSON.stringify(proposal.draft_pack_updates, null, 2)}</pre>
            </details>
          </section>

          <section className="panel action-panel" aria-labelledby="action-heading">
            <div>
              <p className="section-kicker">Human decision</p>
              <h2 id="action-heading">Proposal action</h2>
              <p className="muted action-copy">
                Publishing creates the next snapshot. Discarding keeps the
                source archive and Diff but closes this proposal.
              </p>
            </div>
            <div className="action-row">
              <button
                className="secondary-button"
                type="button"
                disabled={action !== null}
                onClick={() => void runAction("discard")}
              >
                {action === "discard" ? "Discarding…" : "Discard"}
              </button>
              <button
                className="primary-button"
                type="button"
                disabled={action !== null || futureEffective}
                onClick={() => void runAction("publish")}
              >
                {action === "publish" ? "Publishing…" : "Publish"}
              </button>
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}
