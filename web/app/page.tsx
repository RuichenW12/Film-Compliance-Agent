import Link from "next/link";

import { t } from "@/lib/i18n";

/**
 * The first thing anyone sees, written for someone who has never filed
 * anything.
 *
 * It used to say "answer the intake questions, get a classification with the
 * clauses it was based on, collect materials, and prepare the filing form with
 * every field traceable to a source" -- every noun in that sentence is ours,
 * not a creator's. Someone arriving with a drama idea has no reason to know
 * what an intake question or a clause is.
 *
 * The three bounds are stated up front rather than buried in a footer, because
 * they are what someone deciding whether to trust this most needs to know: it
 * checks before you submit, it is not legal advice, and it never files
 * anything on your behalf.
 */
export default function HomePage() {
  return (
    <section>
      <h1>{t("home.title")}</h1>
      <p className="page-intro">{t("home.lede")}</p>

      <div className="card">
        <h2>{t("home.what_it_does")}</h2>
        <ul>
          <li>{t("home.does.class")}</li>
          <li>{t("home.does.route")}</li>
          <li>{t("home.does.script")}</li>
          <li>{t("home.does.form")}</li>
        </ul>
      </div>

      <div className="card">
        <h2>{t("home.what_it_does_not")}</h2>
        <ul>
          <li>{t("home.not.submit")}</li>
          <li>{t("home.not.advice")}</li>
          <li>{t("home.not.guess")}</li>
        </ul>
      </div>

      <p>
        <Link className="primary-button" href="/wizard">
          {t("home.start")}
        </Link>
      </p>
      <p className="muted">
        <Link href="/dashboard">{t("home.dashboard")}</Link>
        {" · "}
        <Link href="/institution">{t("home.institution")}</Link>
        {" · "}
        <Link href="/admin">{t("home.admin")}</Link>
      </p>
    </section>
  );
}
