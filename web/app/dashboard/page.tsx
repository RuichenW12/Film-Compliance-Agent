"use client";

import { useState } from "react";

import { ApiError, apiFetch } from "../../lib/api";

interface ProjectResponse {
  project: Record<string, unknown> & {
    state: string;
    policy_stale: boolean;
    classification: { tier: string; tier_provisional: boolean } | null;
  };
  counts: { findings_open_block: number; materials_pending: number };
}

interface TimelineEvent {
  event_id: string;
  at: string;
  actor: string;
  event: string;
}

export default function DashboardPage() {
  const [projectId, setProjectId] = useState("");
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [gate, setGate] = useState<{ passed: boolean; gaps: { check: string; items: string[] }[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      setProject(await apiFetch<ProjectResponse>(`/v1/projects/${projectId}`));
      setTimeline(await apiFetch<TimelineEvent[]>(`/v1/projects/${projectId}/timeline`));
      setGate(await apiFetch(`/v1/projects/${projectId}/gate`));
    } catch (caught) {
      setError(caught instanceof ApiError ? `${caught.code}: ${caught.message}` : String(caught));
      setProject(null);
      setTimeline([]);
      setGate(null);
    }
  }

  return (
    <section>
      <h1>Dashboard</h1>
      <form onSubmit={load} className="card">
        <label>
          <span>Project id</span>
          <input value={projectId} onChange={(event) => setProjectId(event.target.value)} size={40} />
        </label>
        <button type="submit">Load</button>
      </form>

      {error ? <p role="alert">{error}</p> : null}

      {project ? (
        <section className="card">
          <h2>State</h2>
          <p>
            <span className="badge">{project.project.state}</span>
            {project.project.classification ? (
              <span className="badge">
                {project.project.classification.tier}
                {project.project.classification.tier_provisional ? " (provisional)" : ""}
              </span>
            ) : null}
            {project.project.policy_stale ? <span className="badge">policy update pending review</span> : null}
          </p>
          <p>
            Open blocking findings: {project.counts.findings_open_block} · Materials pending:{" "}
            {project.counts.materials_pending}
          </p>
          {gate ? (
            <>
              <h3>Pre-shoot gate</h3>
              <p>{gate.passed ? "Open" : "Blocked"}</p>
              <ul>
                {gate.gaps.map((gap) => (
                  <li key={gap.check}>
                    {gap.check}: {gap.items.join(", ")}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      ) : null}

      {timeline.length ? (
        <section className="card">
          <h2>Timeline</h2>
          <ol>
            {timeline.map((event) => (
              <li key={event.event_id}>
                <code>{event.at}</code> · {event.actor} · {event.event}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </section>
  );
}
