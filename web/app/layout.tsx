import type { Metadata } from "next";
import Link from "next/link";

import { RoleSwitcher } from "../components/RoleSwitcher";
import { t } from "../lib/i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: "Film Compliance Agent",
  description:
    "Pre-shoot compliance workflow for micro-dramas: classification, evidence-linked review, and filing preparation."
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <strong>{t("app.title")}</strong>
          <nav>
            <Link href="/wizard">{t("nav.wizard")}</Link>
            <Link href="/dashboard">{t("nav.dashboard")}</Link>
            <Link href="/admin">{t("nav.admin")}</Link>
          </nav>
          <RoleSwitcher />
        </header>
        <main>{children}</main>
        <footer className="disclaimer">{t("app.disclaimer")}</footer>
      </body>
    </html>
  );
}
