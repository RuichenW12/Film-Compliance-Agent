import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PolicyAdminPage } from "@/components/policy/policy-admin-page";
import {
  getRun,
  listPendingProposals,
  listSnapshots,
  startCrawl,
} from "@/lib/policy-api";


vi.mock("@/lib/policy-api", () => ({
  getRun: vi.fn(),
  listPendingProposals: vi.fn(),
  listSnapshots: vi.fn(),
  startCrawl: vi.fn(),
}));


const mockedGetRun = vi.mocked(getRun);
const mockedListPendingProposals = vi.mocked(listPendingProposals);
const mockedListSnapshots = vi.mocked(listSnapshots);
const mockedStartCrawl = vi.mocked(startCrawl);

const PROPOSAL = {
  proposal_id: "proposal_001",
  summary: "分类标准正式公布",
  impact: ["D1c" as const],
  effective_from: "2026-08-22T00:00:00+08:00",
  status: "pending" as const,
};

const SNAPSHOT = {
  version: "v1",
  published_at: "2026-08-22T00:05:00+08:00",
  effective_from: "2026-08-22T00:00:00+08:00",
  published_by: "admin_seed",
  thresholds_published: false,
};


beforeEach(() => {
  vi.clearAllMocks();
  mockedListPendingProposals.mockResolvedValue([]);
  mockedListSnapshots.mockResolvedValue([]);
});


describe("PolicyAdminPage", () => {
  it("shows the fixture label, pending proposals, and snapshots", async () => {
    mockedListPendingProposals.mockResolvedValue([PROPOSAL]);
    mockedListSnapshots.mockResolvedValue([SNAPSHOT]);

    render(<PolicyAdminPage />);

    expect(screen.getByText("Synthetic local fixture")).toBeInTheDocument();
    expect(await screen.findByText(PROPOSAL.summary)).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("Not published")).toBeInTheDocument();
  });

  it("runs a crawl to terminal state and reloads proposals", async () => {
    mockedStartCrawl.mockResolvedValue({ run_id: "run_001" });
    mockedGetRun.mockResolvedValue({
      run_id: "run_001",
      source_id: "nrta_micro_drama",
      status: "proposal_created",
      started_at: "2026-08-23T20:30:00+08:00",
      finished_at: "2026-08-23T20:30:00+08:00",
      previous_sha256: "old",
      current_sha256: "new",
      proposal_id: "proposal_001",
      error: null,
    });
    mockedListPendingProposals
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([PROPOSAL]);

    render(<PolicyAdminPage pollDelayMs={0} />);
    await waitFor(() => {
      expect(mockedListPendingProposals).toHaveBeenCalledTimes(1);
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Run fixture crawl" }),
    );

    expect(await screen.findByText("proposal_created")).toBeInTheDocument();
    expect(await screen.findByText(PROPOSAL.summary)).toBeInTheDocument();
    expect(mockedListPendingProposals).toHaveBeenCalledTimes(2);
  });

  it("shows API failures inline", async () => {
    mockedListPendingProposals.mockRejectedValue(
      new Error("policy API unavailable"),
    );

    render(<PolicyAdminPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "policy API unavailable",
    );
  });
});
