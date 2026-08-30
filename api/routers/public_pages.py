"""The two pages an OAuth consent screen has to point at.

Google will not let an external OAuth app be published without a privacy
policy and a terms link, and it checks that their domain is one you have
registered. That makes these pages a deployment dependency rather than a
product feature -- which is why they live in their own router, mounted with one
line, and touch nothing else.

They are deliberately plain HTML with no dependency on the Next.js app: the
consent screen links straight at the API, and a person following that link
should not need the front end to be up.

Everything stated here is checkable against the code. That is the whole
standard for this file. A privacy policy that describes a system we do not run
is worse than none, and a demo is exactly where that mistake is easy to make.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["public"], include_in_schema=False)


_STYLE = """
:root { color-scheme: light dark; }
body {
  margin: 0 auto; padding: 3rem 1.5rem 6rem; max-width: 42rem;
  font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
h1 { font-size: 1.7rem; line-height: 1.2; margin: 0 0 .4rem; }
h2 { font-size: 1.05rem; margin: 2.2rem 0 .5rem; }
.sub { color: #667; margin: 0 0 2.5rem; }
ul { padding-left: 1.2rem; }
li { margin: .3rem 0; }
footer { margin-top: 3.5rem; font-size: .9rem; color: #667; }
a { color: inherit; }
"""


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Film Compliance Agent</title>
<style>{_STYLE}</style>
</head>
<body>
{body}
<footer>
Film Compliance Agent — a pre-check reference, not legal advice.
<a href="/privacy">Privacy</a> · <a href="/terms">Terms</a>
</footer>
</body>
</html>"""
    )


@router.get("/privacy", response_class=HTMLResponse)
def privacy() -> HTMLResponse:
    return _page(
        "Privacy",
        """
<h1>Privacy</h1>
<p class="sub">What this service stores, where it goes, and what it does not do.</p>

<p>Film Compliance Agent is a demonstration tool. It helps someone preparing a
Chinese micro-drama filing check their project before they submit it. It is
not a government service and has no connection to any regulator.</p>

<h2>What is collected</h2>
<ul>
  <li><strong>What you type</strong> — a working title, genre keywords, a
      synopsis, episode length, and a budget range, if you give one.</li>
  <li><strong>What you upload</strong> — scripts and supporting documents, kept
      as files together with a checksum of their contents.</li>
  <li><strong>Your sign-in identity</strong> — if access is behind Google
      sign-in, the email address of the account that signed in. No password
      ever reaches this service.</li>
</ul>

<h2>Where it goes</h2>
<ul>
  <li>Stored in Google Cloud (Firestore and Cloud Storage) in the
      <code>us-east1</code> region, under a project controlled by the
      operators of this demo.</li>
  <li>Text you supply is sent to Google's Vertex AI to classify the project and
      to check a script against published rules. It is processed to answer your
      request and is not used to train models.</li>
</ul>

<h2>What does not happen</h2>
<ul>
  <li>Nothing is filed with, submitted to, or shared with any government body.
      This service cannot submit on your behalf and does not try to.</li>
  <li>Nothing is sold, rented, or shared with advertisers. There is no
      advertising and no third-party analytics.</li>
  <li>No payment details are collected, because nothing is charged for.</li>
</ul>

<h2>Keeping and removing it</h2>
<p>This is a demonstration environment. Data is kept while the demo runs and may
be deleted at any time without notice, so treat nothing stored here as a
record of anything. <strong>Do not upload a script or document you would mind
losing, or one you are not free to share.</strong></p>
<p>To have something removed sooner, write to the contact below and say which
project it is.</p>

<h2>Contact</h2>
<p>Reach the operator at
<a href="mailto:maxma0223@gmail.com">maxma0223@gmail.com</a>.</p>
""",
    )


@router.get("/terms", response_class=HTMLResponse)
def terms() -> HTMLResponse:
    return _page(
        "Terms",
        """
<h1>Terms of use</h1>
<p class="sub">The short version: this is a demo, and it is not legal advice.</p>

<h2>What this is</h2>
<p>A tool that reads what you describe and upload, and reports how a project
would likely be classified under published Chinese rules on micro-drama
filing — citing the specific clause behind each conclusion so you can check it
yourself.</p>

<h2>What it is not</h2>
<ul>
  <li><strong>Not legal advice.</strong> It is a pre-check reference. Every
      output is something to verify with a qualified person or the responsible
      authority, not something to rely on.</li>
  <li><strong>Not a filing channel.</strong> It does not submit anything
      anywhere. A real filing goes through a licensed production company and
      the relevant authority.</li>
  <li><strong>Not authoritative on the law.</strong> Rules change, and a
      snapshot of them can be out of date or wrong. Where a source is unclear
      the tool is built to say so rather than guess — but it can still be
      mistaken.</li>
</ul>

<h2>Using it</h2>
<ul>
  <li>Upload only material you have the right to upload.</li>
  <li>Do not use it to prepare anything unlawful.</li>
  <li>It is offered as-is, with no warranty and no guarantee of availability.
      It is a demonstration and may change or stop without notice.</li>
</ul>

<h2>Contact</h2>
<p><a href="mailto:maxma0223@gmail.com">maxma0223@gmail.com</a></p>
""",
    )
