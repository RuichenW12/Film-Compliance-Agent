import Link from "next/link";

export default function HomePage() {
  return (
    <section>
      <h1>Film Compliance Agent</h1>
      <p>
        Answer the intake questions, get a classification with the clauses it
        was based on, collect materials, and prepare the filing form with every
        field traceable to a source.
      </p>
      <ul>
        <li>
          <Link href="/wizard">Start a new project</Link>
        </li>
        <li>
          <Link href="/dashboard">Open the dashboard</Link>
        </li>
        <li>
          <Link href="/admin">Administration</Link>
        </li>
      </ul>
    </section>
  );
}
