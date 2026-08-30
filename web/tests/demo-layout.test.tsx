import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AdminPage from "@/app/admin/page";
import CollectionPage from "@/app/collection/page";
import DashboardPage from "@/app/dashboard/page";
import InstitutionPage from "@/app/institution/page";
import RootLayout from "@/app/layout";


describe("creator demo shell", () => {
  it("shows only product context and no legacy workflow navigation", () => {
    render(<RootLayout><div>Demo body</div></RootLayout>);

    expect(screen.getByText("Film Compliance")).toBeInTheDocument();
    expect(screen.getByText("AI micro-drama review")).toBeInTheDocument();
    expect(screen.getByText("Demo body")).toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.queryByText(/switch view/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /wizard/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /collection/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /dashboard/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /institution/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /admin/i })).not.toBeInTheDocument();
  });

  it("keeps staff tools compiled as direct routes", () => {
    expect(AdminPage).toBeTypeOf("function");
    expect(CollectionPage).toBeTypeOf("function");
    expect(DashboardPage).toBeTypeOf("function");
    expect(InstitutionPage).toBeTypeOf("function");
  });
});
