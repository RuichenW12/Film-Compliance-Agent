import Link from "next/link";

export default function AdminPage() {
  return (
    <section>
      <h1>Administration</h1>
      <p>
        Policy administration — proposals, side-by-side diffs, and the publish
        gate — lives under <code>/admin/policy</code> and is owned by the policy
        workstream.
      </p>
      <ul>
        <li>
          <Link href="/admin/policy">Policy administration</Link>
        </li>
      </ul>
      <p>
        A snapshot is only ever published by a human from that page. There is no
        automatic publish path.
      </p>
    </section>
  );
}
