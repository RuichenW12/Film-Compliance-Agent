import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PolicyVerificationBanner } from "@/components/policy-verification-banner";


describe("PolicyVerificationBanner", () => {
  it("renders a non-dismissible integration warning for mock policy", () => {
    render(<PolicyVerificationBanner status="mock_verified" />);

    expect(screen.getByRole("alert")).toHaveTextContent(/integration data/i);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders nothing for human-verified policy", () => {
    const { container } = render(
      <PolicyVerificationBanner status="human_verified" />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
