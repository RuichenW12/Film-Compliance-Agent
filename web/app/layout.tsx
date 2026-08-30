import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Film Compliance · AI micro-drama review",
  description:
    "Upload a micro-drama script, confirm extracted project details, and prepare a risk review package."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="demo-topbar">
          <Link className="demo-brand" href="/" aria-label="Film Compliance home">
            <span className="demo-brand-mark" aria-hidden="true">FC</span>
            <span>
              <strong>Film Compliance</strong>
              <small>AI micro-drama review</small>
            </span>
          </Link>
          <span className="demo-context">Pre-production demo</span>
        </header>
        <main className="demo-main">{children}</main>
        <footer className="demo-footer">
          <span>Review preparation only</span>
          <span>Not legal advice · Nothing is filed on your behalf</span>
        </footer>
      </body>
    </html>
  );
}
