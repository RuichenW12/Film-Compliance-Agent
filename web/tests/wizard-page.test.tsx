import { describe, expect, it, vi } from "vitest";

import WizardPage from "@/app/wizard/page";
import { redirect } from "next/navigation";


vi.mock("next/navigation", () => ({
  redirect: vi.fn(() => {
    throw new Error("NEXT_REDIRECT");
  }),
}));


describe("legacy wizard route", () => {
  it("sunsets the obsolete questionnaire by redirecting to the upload-first demo", () => {
    expect(() => WizardPage()).toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/");
  });
});
