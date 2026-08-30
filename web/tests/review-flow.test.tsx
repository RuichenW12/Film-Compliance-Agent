import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewFlow } from "@/components/review-flow";
import type { ReviewView } from "@/lib/reviews-api";
import {
  confirmReview,
  createIdeaReview,
  createScriptReview,
  getReview,
} from "@/lib/reviews-api";


vi.mock("@/lib/reviews-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/reviews-api")>();
  return {
    ...actual,
    confirmReview: vi.fn(),
    createIdeaReview: vi.fn(),
    createScriptReview: vi.fn(),
    getReview: vi.fn(),
    retryReviewIntake: vi.fn(),
  };
});


const AMOUNT_OPTIONS = [
  {
    value: "below_lower" as const,
    label: "Below CNY 300,000",
    lower_rmb: 300000,
    upper_rmb: 800000,
  },
  {
    value: "between" as const,
    label: "CNY 300,000–800,000",
    lower_rmb: 300000,
    upper_rmb: 800000,
  },
  {
    value: "at_or_above_upper" as const,
    label: "CNY 800,000 or above",
    lower_rmb: 300000,
    upper_rmb: 800000,
  },
];


const CONFIRM_VIEW: ReviewView = {
  review_id: "review_001",
  state: "AWAITING_CONFIRMATION",
  mode: "script",
  candidates: {
    title: {
      value: "先挂电话",
      origin: "extracted",
      confidence: 1,
      source_quote: "# 《先挂电话》",
      explanation: null,
    },
    tags: {
      value: ["public security", "family drama"],
      origin: "suggested",
      confidence: null,
      source_quote: null,
      explanation: "Suggested from the story content.",
    },
    synopsis: {
      value: "A family and an officer confront a suspicious call.",
      origin: "suggested",
      confidence: null,
      source_quote: null,
      explanation: "A concise summary of the central conflict.",
    },
    episode_count: {
      value: 10,
      origin: "suggested",
      confidence: null,
      source_quote: null,
      explanation: "A ten-part adaptation preserves total duration.",
    },
    episode_minutes: {
      value: 3,
      origin: "suggested",
      confidence: null,
      source_quote: null,
      explanation: "Three minutes per episode suits the format.",
    },
    amount_bracket: {
      value: "at_or_above_upper",
      origin: "suggested",
      confidence: null,
      source_quote: null,
      explanation: "An editable planning estimate.",
    },
    structure: {
      source_episode_count: 1,
      source_total_minutes: 30,
      source_scene_count: 15,
    },
  },
  confirmed: null,
  intake_status: "complete",
  semantic_status: null,
  source_filename: "e2e-30min-public-security.md",
  source_sha256: "abc123",
  source_download_url: "/v1/reviews/review_001/source",
  amount_options: AMOUNT_OPTIONS,
  classification: null,
  findings: [],
  artifacts: [],
};


const COMPLETE_VIEW: ReviewView = {
  ...CONFIRM_VIEW,
  state: "COMPLETE",
  confirmed: {
    title: "先挂电话",
    tags: ["公安", "家庭现实"],
    synopsis: "社区民警帮助居民识别可疑来电。",
    episode_count: 10,
    episode_minutes: 3,
    amount_bracket: "at_or_above_upper",
  },
  semantic_status: "pending",
  classification: {
    class_name: "Class 1",
    co_review_required: true,
    subjects: ["Public security subject"],
    snapshot_version: "v2",
    evidence_refs: [
      { snapshot_version: "v2", clause_id: "nrta-order-16-article-5" },
    ],
    route: { authority: "provincial_radio_television_authority" },
  },
  findings: [
    {
      risk_id: "RISK-001",
      episode: 1,
      scene: 3,
      quote: "社区民警说明诈骗链路。",
      category: "public_security",
      status: "Needs human review",
      evidence_refs: [],
      explanation: "Public-security depiction requires human review.",
      suggestion: "Verify the depiction with a qualified reviewer.",
    },
  ],
  artifacts: [
    {
      artifact_type: "form",
      filename: "project-review-form.pdf",
      download_url: "/v1/reviews/review_001/artifacts/form",
    },
    {
      artifact_type: "summary",
      filename: "risk-summary.pdf",
      download_url: "/v1/reviews/review_001/artifacts/summary",
    },
    {
      artifact_type: "annotated-script",
      filename: "annotated-script.md",
      download_url: "/v1/reviews/review_001/artifacts/annotated-script",
    },
  ],
};


afterEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
});


describe("upload-first review flow", () => {
  it("starts with an accessible upload action and a secondary idea path", () => {
    render(<ReviewFlow />);

    expect(
      screen.getByRole("heading", { name: "Upload a script. Skip the questionnaire." })
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Choose a script")).toHaveAttribute(
      "accept",
      ".md,.txt,.docx"
    );
    expect(
      screen.getByRole("button", { name: "Extract project details" })
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "I only have an idea" })
    ).toBeInTheDocument();
    expect(screen.queryByText(/production stage/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/project id/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/roadmap/i)).not.toBeInTheDocument();
  });

  it("uploads first, then exposes editable candidates without analyzing early", async () => {
    vi.mocked(createScriptReview).mockResolvedValue(CONFIRM_VIEW);
    const user = userEvent.setup();
    render(<ReviewFlow />);

    const file = new File(["# Demo"], "demo.md", { type: "text/markdown" });
    await user.upload(screen.getByLabelText("Choose a script"), file);
    await user.click(
      screen.getByRole("button", { name: "Extract project details" })
    );

    const title = await screen.findByLabelText("Project title");
    expect(title).toHaveValue("先挂电话");
    expect(title).toHaveFocus();
    expect(screen.getByText("Extracted from script")).toBeInTheDocument();
    expect(screen.getAllByText("AI suggested").length).toBeGreaterThan(0);
    expect(screen.getByText("1 episode · 30 min · 15 scenes")).toBeInTheDocument();
    expect(screen.getByLabelText("Investment band")).toHaveValue(
      "at_or_above_upper"
    );
    expect(confirmReview).not.toHaveBeenCalled();
    expect(window.location.search).toBe("?review=review_001");

    await user.clear(title);
    await user.type(title, "Edited title");
    await user.click(
      screen.getByRole("button", { name: "Confirm & analyze risks" })
    );

    expect(confirmReview).toHaveBeenCalledWith(
      "review_001",
      expect.objectContaining({ title: "Edited title", episode_count: 10 })
    );
  });

  it("opens blank manual fields for the idea-only path", async () => {
    vi.mocked(createIdeaReview).mockResolvedValue({
      ...CONFIRM_VIEW,
      mode: "idea",
      candidates: {
        title: null,
        tags: null,
        synopsis: null,
        episode_count: null,
        episode_minutes: null,
        amount_bracket: null,
        structure: null,
      },
      source_filename: null,
      source_sha256: null,
      source_download_url: null,
    });
    const user = userEvent.setup();
    render(<ReviewFlow />);

    await user.click(
      screen.getByRole("button", { name: "I only have an idea" })
    );

    expect(await screen.findByLabelText("Project title")).toHaveValue("");
    expect(screen.getByText("Enter the essential details manually.")).toBeInTheDocument();
    expect(screen.queryByText(/source script structure/i)).not.toBeInTheDocument();
  });

  it("restores a completed review and states the semantic boundary", async () => {
    vi.mocked(getReview).mockResolvedValue(COMPLETE_VIEW);
    render(<ReviewFlow initialReviewId="review_001" />);

    expect(await screen.findByText("Class 1")).toBeInTheDocument();
    expect(screen.getByText("Co-review required")).toBeInTheDocument();
    expect(screen.getByText("Public security subject")).toBeInTheDocument();
    expect(screen.getByText(/semantic review is pending/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Passed$/i)).not.toBeInTheDocument();
    expect(screen.getByText("RISK-001")).toBeInTheDocument();
    expect(screen.getByText("Needs human review")).toBeInTheDocument();
    expect(getReview).toHaveBeenCalledWith("review_001");

    const packageSection = screen.getByRole("region", { name: "Review package" });
    expect(within(packageSection).getAllByRole("link")).toHaveLength(4);
    const beyond = screen.getByRole("region", { name: "Beyond this demo" });
    expect(within(beyond).queryAllByRole("link")).toHaveLength(0);
    expect(within(beyond).queryAllByRole("button")).toHaveLength(0);
  });

  it("shows real request progress and moves focus to results", async () => {
    vi.mocked(createScriptReview).mockResolvedValue(CONFIRM_VIEW);
    let finish: ((view: ReviewView) => void) | undefined;
    vi.mocked(confirmReview).mockImplementation(
      () => new Promise((resolve) => { finish = resolve; })
    );
    const user = userEvent.setup();
    render(<ReviewFlow />);
    await user.upload(
      screen.getByLabelText("Choose a script"),
      new File(["# Demo"], "demo.md", { type: "text/markdown" })
    );
    await user.click(screen.getByRole("button", { name: "Extract project details" }));
    await user.click(screen.getByRole("button", { name: "Confirm & analyze risks" }));

    expect(screen.getByText("Classifying project and reviewing scenes…")).toBeInTheDocument();
    finish?.(COMPLETE_VIEW);

    const results = await screen.findByRole("heading", { name: "Review results" });
    await waitFor(() => expect(results).toHaveFocus());
  });
});
