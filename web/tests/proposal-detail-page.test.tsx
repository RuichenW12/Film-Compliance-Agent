import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProposalDetailPage } from "@/components/policy/proposal-detail-page";
import {
  discardProposal,
  getProposal,
  publishProposal,
} from "@/lib/policy-api";


const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/policy-api", () => ({
  discardProposal: vi.fn(),
  getProposal: vi.fn(),
  publishProposal: vi.fn(),
}));


const mockedDiscardProposal = vi.mocked(discardProposal);
const mockedGetProposal = vi.mocked(getProposal);
const mockedPublishProposal = vi.mocked(publishProposal);

const PROPOSAL_DETAIL = {
  proposal_id: "proposal_001",
  summary: "分类标准正式公布",
  impact: ["D1c" as const],
  effective_from: "2026-08-22T00:00:00+08:00",
  status: "pending" as const,
  source_diff_uri: "file:///private/synthetic-diff.json",
  source_diff_text: "-分类标准尚未公布。\n+分类标准正式公布。",
  draft_pack_updates: {
    p3_tier_thresholds: { thresholds_published: true },
  },
  published_version: null,
};


beforeEach(() => {
  vi.clearAllMocks();
  mockedGetProposal.mockResolvedValue(PROPOSAL_DETAIL);
  mockedPublishProposal.mockResolvedValue({ snapshot_version: "v2" });
  mockedDiscardProposal.mockResolvedValue(undefined);
});


describe("ProposalDetailPage", () => {
  it("shows the reviewed diff, impact, and draft pack JSON", async () => {
    render(<ProposalDetailPage proposalId="proposal_001" />);

    expect(await screen.findByText(PROPOSAL_DETAIL.summary)).toBeInTheDocument();
    expect(screen.getByText("D1c")).toBeInTheDocument();
    expect(screen.getByText(/分类标准尚未公布/)).toBeInTheDocument();
    expect(screen.getByText(/thresholds_published/)).toBeInTheDocument();
  });

  it("disables publish for a future-effective proposal", async () => {
    mockedGetProposal.mockResolvedValue({
      ...PROPOSAL_DETAIL,
      effective_from: "2999-01-01T00:00:00Z",
    });

    render(<ProposalDetailPage proposalId="proposal_001" />);

    expect(await screen.findByText(PROPOSAL_DETAIL.summary)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish" })).toBeDisabled();
    expect(screen.getByText(/not effective yet/i)).toBeInTheDocument();
  });

  it("publishes and returns to the policy list", async () => {
    render(<ProposalDetailPage proposalId="proposal_001" />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Publish" }),
    );

    expect(mockedPublishProposal).toHaveBeenCalledWith("proposal_001");
    expect(push).toHaveBeenCalledWith("/admin/policy");
  });

  it("discards and returns to the policy list", async () => {
    render(<ProposalDetailPage proposalId="proposal_001" />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Discard" }),
    );

    expect(mockedDiscardProposal).toHaveBeenCalledWith("proposal_001");
    expect(push).toHaveBeenCalledWith("/admin/policy");
  });

  it("keeps the page and shows action failures inline", async () => {
    mockedPublishProposal.mockRejectedValue(new Error("publication conflict"));
    render(<ProposalDetailPage proposalId="proposal_001" />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Publish" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "publication conflict",
    );
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByText(PROPOSAL_DETAIL.summary)).toBeInTheDocument();
  });
});
