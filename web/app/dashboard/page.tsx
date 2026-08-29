"use client";

import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  NotificationItem,
  ProjectResponse,
  apiFetch,
  getProject,
  listNotifications,
  markNotificationRead
} from "../../lib/api";
import { format, t } from "../../lib/i18n";
import { PolicyVerificationBanner } from "../../components/policy-verification-banner";

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
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadOnly, setUnreadOnly] = useState(false);

  // The inbox belongs to the signed-in creator, not to a project, so it loads
  // on its own rather than waiting for a project id.
  const loadNotifications = useCallback(async () => {
    try {
      setNotifications(await listNotifications(unreadOnly));
    } catch {
      // An unreachable inbox must not hide the project view.
      setNotifications([]);
    }
  }, [unreadOnly]);

  useEffect(() => {
    void loadNotifications();
  }, [loadNotifications]);

  async function markRead(notificationId: string) {
    await markNotificationRead(notificationId);
    await loadNotifications();
  }

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      setProject(await getProject(projectId));
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
          <PolicyVerificationBanner
            status={project.project.classification?.policy_verification_status}
          />
          <h2>State</h2>
          <p>
            <span className="badge">{project.project.state}</span>
            {project.project.classification ? (
              <span className="badge">
                {project.project.classification.tier}
                {project.project.classification.tier_provisional ? " (provisional)" : ""}
              </span>
            ) : null}
            {project.project.policy_stale ? (
              <span className="badge">{t("dashboard.stale_badge")}</span>
            ) : null}
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

      <section className="card">
        <h2>{t("notifications.title")}</h2>
        <label>
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(event) => setUnreadOnly(event.target.checked)}
          />
          <span>{t("notifications.unread_only")}</span>
        </label>
        {notifications.length ? (
          <ul>
            {notifications.map((item) => (
              <li key={item.notification_id}>
                <strong>{t(item.title_key)}</strong>
                {item.read ? null : <span className="badge">new</span>}
                <br />
                {format(item.body_key, item.params)}
                {item.read ? null : (
                  <>
                    {" "}
                    <button type="button" onClick={() => markRead(item.notification_id)}>
                      {t("notifications.mark_read")}
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p>{t("notifications.empty")}</p>
        )}
      </section>

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
