import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewFlow } from "@/components/review-flow";
import type { ReviewView } from "@/lib/reviews-api";
import {
  confirmReview,
  createIdeaReview,
  createScriptReview,
  getReview,
  reanalyzeReview,
  retryReviewIntake,
} from "@/lib/reviews-api";


vi.mock("@/lib/reviews-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/reviews-api")>();
  return {
    ...actual,
    confirmReview: vi.fn(),
    createIdeaReview: vi.fn(),
    createScriptReview: vi.fn(),
    getReview: vi.fn(),
    reanalyzeReview: vi.fn(),
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
    title: "Confirmed script title",
    tags: ["公安", "家庭现实"],
    synopsis: "社区民警帮助居民识别可疑来电。",
    episode_count: 12,
    episode_minutes: 2.5,
    amount_bracket: "between",
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

    expect(screen.getByRole("tablist", { name: "Review progress" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Upload/ })).toHaveAttribute(
      "aria-selected",
      "true"
    );
    expect(screen.getByRole("tab", { name: /Confirm details/ })).toBeDisabled();
    expect(screen.getByRole("tab", { name: /Review results/ })).toBeDisabled();
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
    expect(screen.queryByRole("button", { name: /Back/i })).not.toBeInTheDocument();
  });

  it("navigates visited tabs without requests and reanalyzes confirmed edits once", async () => {
    vi.mocked(getReview).mockResolvedValue(COMPLETE_VIEW);
    vi.mocked(reanalyzeReview).mockResolvedValue({
      ...COMPLETE_VIEW,
      confirmed: { ...COMPLETE_VIEW.confirmed!, title: "Updated confirmed title" },
    });
    const user = userEvent.setup();
    render(<ReviewFlow initialReviewId="review_001" />);

    expect(await screen.findByText("Class 1")).toBeInTheDocument();
    const resultsTab = screen.getByRole("tab", { name: /Review results/ });
    const confirmTab = screen.getByRole("tab", { name: /Confirm details/ });
    const uploadTab = screen.getByRole("tab", { name: /Upload/ });
    expect(resultsTab).toHaveAttribute("aria-selected", "true");
    expect(confirmTab).toBeEnabled();
    expect(uploadTab).toBeEnabled();

    await user.click(confirmTab);
    expect(screen.getByLabelText("Project title")).toHaveValue("Confirmed script title");
    expect(screen.getByLabelText("Tags")).toHaveValue("公安, 家庭现实");
    expect(screen.getByLabelText("Synopsis")).toHaveValue("社区民警帮助居民识别可疑来电。");
    expect(screen.getByLabelText("Episode count")).toHaveValue(12);
    expect(screen.getByLabelText("Minutes per episode")).toHaveValue(2.5);
    expect(screen.getByLabelText("Investment band")).toHaveValue("between");
    expect(screen.getAllByText("Last confirmed")).toHaveLength(6);
    expect(screen.getByRole("button", { name: "Confirm changes & reanalyze" })).toBeInTheDocument();
    expect(confirmReview).not.toHaveBeenCalled();
    expect(reanalyzeReview).not.toHaveBeenCalled();

    await user.click(resultsTab);
    await user.click(uploadTab);
    expect(screen.getByText("e2e-30min-public-security.md")).toBeInTheDocument();
    expect(screen.getByText(/abc123/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue with current script" })).toBeInTheDocument();
    expect(confirmReview).not.toHaveBeenCalled();
    expect(reanalyzeReview).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Continue with current script" }));
    expect(screen.getByText("Class 1")).toBeInTheDocument();
    expect(resultsTab).toHaveAttribute("aria-selected", "true");
    expect(confirmReview).not.toHaveBeenCalled();
    expect(reanalyzeReview).not.toHaveBeenCalled();

    await user.click(confirmTab);
    const title = screen.getByLabelText("Project title");
    await user.clear(title);
    await user.type(title, "Updated confirmed title");
    await user.click(screen.getByRole("button", { name: "Confirm changes & reanalyze" }));

    expect(reanalyzeReview).toHaveBeenCalledTimes(1);
    expect(reanalyzeReview).toHaveBeenCalledWith(
      "review_001",
      expect.objectContaining({ title: "Updated confirmed title" })
    );
    expect(confirmReview).not.toHaveBeenCalled();
    expect(await screen.findByText("Class 1")).toBeInTheDocument();
    expect(screen.getByText("Updated confirmed title")).toBeInTheDocument();
    expect(resultsTab).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("button", { name: /Back/i })).not.toBeInTheDocument();
  });

  it("supports arrow-key navigation across visited progress tabs", async () => {
    vi.mocked(getReview).mockResolvedValue(COMPLETE_VIEW);
    const user = userEvent.setup();
    render(<ReviewFlow initialReviewId="review_001" />);

    const resultsTab = await screen.findByRole("tab", { name: /Review results/ });
    const uploadTab = screen.getByRole("tab", { name: /Upload/ });
    await waitFor(() => expect(resultsTab).toHaveAttribute("aria-selected", "true"));
    resultsTab.focus();
    await user.keyboard("{ArrowRight}");

    expect(uploadTab).toHaveFocus();
    expect(uploadTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: "Continue with current script" })).toBeInTheDocument();
    expect(confirmReview).not.toHaveBeenCalled();
    expect(reanalyzeReview).not.toHaveBeenCalled();
  });

  it("disables every progress tab while a request is mutating the review", async () => {
    let finish: ((view: ReviewView) => void) | undefined;
    vi.mocked(createScriptReview).mockImplementation(
      () => new Promise((resolve) => { finish = resolve; })
    );
    const user = userEvent.setup();
    render(<ReviewFlow />);

    await user.upload(
      screen.getByLabelText("Choose a script"),
      new File(["# Demo"], "demo.md", { type: "text/markdown" })
    );
    await user.click(screen.getByRole("button", { name: "Extract project details" }));

    for (const tab of screen.getAllByRole("tab")) {
      expect(tab).toBeDisabled();
    }
    expect(screen.getByRole("form", { name: "Script upload" })).toHaveAttribute(
      "aria-busy",
      "true"
    );
    expect(screen.getByRole("status")).toHaveTextContent("Reading script…");
    finish?.(CONFIRM_VIEW);
    expect(await screen.findByLabelText("Project title")).toBeInTheDocument();
  });

  it("guards confirmation against duplicate submissions before React can rerender", async () => {
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
    const submit = await screen.findByRole("button", { name: "Confirm & analyze risks" });

    act(() => {
      submit.click();
      submit.click();
    });

    expect(confirmReview).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Classifying project and reviewing scenes…")).toBeInTheDocument();
    for (const tab of screen.getAllByRole("tab")) {
      expect(tab).toBeDisabled();
    }
    await act(async () => { finish?.(COMPLETE_VIEW); });
    expect(await screen.findByText("Class 1")).toBeInTheDocument();
  });

  it("disables retry, editable fields, and submit while one retry request is pending", async () => {
    const partialView: ReviewView = { ...CONFIRM_VIEW, intake_status: "partial" };
    vi.mocked(getReview).mockResolvedValue(partialView);
    let finish: ((view: ReviewView) => void) | undefined;
    vi.mocked(retryReviewIntake).mockImplementation(
      () => new Promise((resolve) => { finish = resolve; })
    );
    const user = userEvent.setup();
    render(<ReviewFlow initialReviewId="review_001" />);

    const retry = await screen.findByRole("button", { name: "Retry extraction" });
    await user.click(retry);
    await user.click(retry);

    expect(retryReviewIntake).toHaveBeenCalledTimes(1);
    expect(retry).toBeDisabled();
    expect(screen.getByLabelText("Project title")).toBeDisabled();
    expect(screen.getByLabelText("Tags")).toBeDisabled();
    expect(screen.getByLabelText("Synopsis")).toBeDisabled();
    expect(screen.getByLabelText("Episode count")).toBeDisabled();
    expect(screen.getByLabelText("Minutes per episode")).toBeDisabled();
    expect(screen.getByLabelText("Investment band")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Confirm & analyze risks" })).toBeDisabled();

    await act(async () => { finish?.(CONFIRM_VIEW); });
    await waitFor(() => expect(screen.getByLabelText("Project title")).toBeEnabled());
  });

  it("refetches server truth after retry fails and renders a failed session", async () => {
    const partialView: ReviewView = { ...CONFIRM_VIEW, intake_status: "partial" };
    const failedView: ReviewView = {
      ...partialView,
      state: "FAILED",
      failure_message: "Extraction failed after retry.",
    };
    vi.mocked(getReview)
      .mockResolvedValueOnce(partialView)
      .mockResolvedValueOnce(failedView);
    vi.mocked(retryReviewIntake).mockRejectedValue(new Error("Retry request failed."));
    const user = userEvent.setup();
    render(<ReviewFlow initialReviewId="review_001" />);

    await user.click(await screen.findByRole("button", { name: "Retry extraction" }));

    expect(await screen.findByRole("heading", { name: "Review could not be completed." })).toBeInTheDocument();
    expect(screen.getByText("Extraction failed after retry.")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Retry request failed.");
    expect(retryReviewIntake).toHaveBeenCalledTimes(1);
    expect(retryReviewIntake).toHaveBeenCalledWith("review_001");
    expect(getReview).toHaveBeenCalledTimes(2);
    expect(getReview).toHaveBeenNthCalledWith(2, "review_001");
  });

  it("starts a new session and resets future tab access when a replacement file is uploaded", async () => {
    vi.mocked(getReview).mockResolvedValue(COMPLETE_VIEW);
    vi.mocked(createScriptReview).mockResolvedValue({
      ...CONFIRM_VIEW,
      review_id: "review_002",
      source_filename: "replacement.md",
      source_sha256: "def456",
    });
    const user = userEvent.setup();
    render(<ReviewFlow initialReviewId="review_001" />);

    const uploadTab = await screen.findByRole("tab", { name: /Upload/ });
    await waitFor(() => expect(screen.getByRole("tab", { name: /Review results/ })).toBeEnabled());
    await user.click(uploadTab);
    await user.upload(
      screen.getByLabelText("Choose a script"),
      new File(["# Replacement"], "replacement.md", { type: "text/markdown" })
    );
    await user.click(screen.getByRole("button", { name: "Extract project details" }));

    expect(createScriptReview).toHaveBeenCalledTimes(1);
    expect(await screen.findByLabelText("Project title")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Confirm details/ })).toHaveAttribute(
      "aria-selected",
      "true"
    );
    expect(screen.getByRole("tab", { name: /Review results/ })).toBeDisabled();
    expect(window.location.search).toBe("?review=review_002");
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

  it("pluralizes a multi-episode source structure", async () => {
    vi.mocked(getReview).mockResolvedValue({
      ...CONFIRM_VIEW,
      candidates: {
        ...CONFIRM_VIEW.candidates!,
        structure: {
          source_episode_count: 7,
          source_total_minutes: 70,
          source_scene_count: 28,
        },
      },
    });
    render(<ReviewFlow initialReviewId="review_001" />);

    expect(await screen.findByText("7 episodes · 70 min · 28 scenes")).toBeInTheDocument();
  });

  it("restores a completed review and states the semantic boundary", async () => {
    vi.mocked(getReview).mockResolvedValue(COMPLETE_VIEW);
    render(<ReviewFlow initialReviewId="review_001" />);

    expect(await screen.findByText("Class 1")).toBeInTheDocument();
    expect(screen.getByText("Co-review required")).toBeInTheDocument();
    expect(screen.getByText("Public security subject")).toBeInTheDocument();
    expect(screen.getByText("Provincial radio television authority")).toBeInTheDocument();
    expect(screen.getByText(/Policy snapshot v2/)).toBeInTheDocument();
    expect(screen.getByText("nrta-order-16-article-5")).toBeInTheDocument();
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

  it("polls a restored analyzing review until it completes", async () => {
    vi.mocked(getReview)
      .mockResolvedValueOnce({ ...CONFIRM_VIEW, state: "ANALYZING" })
      .mockResolvedValueOnce({ ...CONFIRM_VIEW, state: "ANALYZING" })
      .mockResolvedValueOnce(COMPLETE_VIEW);
    render(<ReviewFlow initialReviewId="review_001" />);

    expect(await screen.findByText("Class 1", {}, { timeout: 2500 })).toBeInTheDocument();
    expect(getReview).toHaveBeenCalledTimes(3);
  });

  it("renders a safe recovery action for failed reviews", async () => {
    vi.mocked(getReview).mockResolvedValue({
      ...CONFIRM_VIEW,
      state: "FAILED",
      failure_message: "We couldn't complete this review. Start a new review and upload the source again.",
    });
    const user = userEvent.setup();
    render(<ReviewFlow initialReviewId="review_001" />);

    expect(await screen.findByRole("heading", { name: "Review could not be completed." })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start a new review" }));
    expect(screen.getByRole("heading", { name: "Upload a script. Skip the questionnaire." })).toBeInTheDocument();
    expect(window.location.search).toBe("");
  });

  it("shows the matching upload panel when a failed review revisits Upload", async () => {
    vi.mocked(getReview).mockResolvedValue({
      ...CONFIRM_VIEW,
      state: "FAILED",
      failure_message: "Review failed.",
    });
    const user = userEvent.setup();
    render(<ReviewFlow initialReviewId="review_001" />);

    expect(await screen.findByRole("heading", { name: "Review could not be completed." })).toBeInTheDocument();
    const uploadTab = screen.getByRole("tab", { name: /Upload/ });
    await user.click(uploadTab);

    expect(uploadTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Upload a script. Skip the questionnaire." })).toBeInTheDocument();
    expect(screen.getByText("e2e-30min-public-security.md")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Review could not be completed." })).not.toBeInTheDocument();
    expect(createScriptReview).not.toHaveBeenCalled();
    expect(confirmReview).not.toHaveBeenCalled();
    expect(reanalyzeReview).not.toHaveBeenCalled();
  });
});
