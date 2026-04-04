#!/usr/bin/env python3
"""
AI session bug detector — live recorder.

Spins up the local demo app, runs scripted Playwright sessions, feeds each
through the LLM pipeline, and prints results to the terminal.

For the full end-to-end demo with rrweb replays and an HTML report, use:
  python capture_fixture.py   # record sessions + save fixture
  python run_demo.py          # analyze fixture + generate HTML report

Usage:
  python record_session.py
  python record_session.py --model qwen2.5:1.5b --output markdown
  python record_session.py --github-repo owner/repo --github-token ghp_...
"""

import argparse
import http.server
import os
import sys
import threading
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from analyzer import analyze_session
from posthog_client import SessionEvent, SessionSummary
from reporter import export_json, export_markdown, print_report
from utils import ts

PORT = 8765
BASE_URL = f"http://localhost:{PORT}"
DEMO_APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_app")
VIEWPORT = {"width": 1024, "height": 640}


def _log(msg: str = "") -> None:
    print(f"{ts()} {msg}")


# ── Local HTTP server ────────────────────────────────────────────────────────

class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def start_server() -> http.server.HTTPServer:
    server = http.server.HTTPServer(
        ("localhost", PORT),
        lambda *a, **kw: _SilentHandler(*a, directory=DEMO_APP_DIR, **kw),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


# ── Session recorder ─────────────────────────────────────────────────────────

class SessionRecorder:
    """
    Wraps a Playwright page and records events into a SessionSummary.

    Interaction methods (goto, click, fill) each append a timestamped
    SessionEvent — the same shape PostHog's API returns for real users.
    """

    def __init__(self, page):
        self._page = page
        self._events: list[SessionEvent] = []
        self._start = time.time()
        self._clicks = 0
        self._keypresses = 0
        self._console_errors = 0
        self._console_warns = 0

        page.on("console", self._on_console)
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _on_console(self, msg) -> None:
        if msg.type == "error":
            self._console_errors += 1
            self._events.append(SessionEvent(
                timestamp=self._now(), event="console_error",
                url=self._page.url, properties={"message": msg.text},
            ))
        elif msg.type == "warning":
            self._console_warns += 1

    def _on_request_failed(self, request) -> None:
        self._events.append(SessionEvent(
            timestamp=self._now(), event="network_error",
            url=self._page.url,
            properties={"request_url": request.url, "failure": request.failure},
        ))

    def _on_response(self, response) -> None:
        if response.status >= 400 and "/api/" in response.url:
            self._events.append(SessionEvent(
                timestamp=self._now(), event="network_error",
                url=self._page.url,
                properties={"request_url": response.url, "status": response.status},
            ))

    def goto(self, url: str) -> None:
        self._page.goto(url)
        self._events.append(SessionEvent(
            timestamp=self._now(), event="$pageview", url=url, properties={},
        ))

    def click(self, selector: str, label: str) -> None:
        self._clicks += 1
        self._events.append(SessionEvent(
            timestamp=self._now(), event="$autocapture", url=self._page.url,
            properties={"$event_type": "click", "$el_text": label},
        ))
        self._page.click(selector)

    def fill(self, selector: str, value: str) -> None:
        self._keypresses += len(value)
        self._page.fill(selector, value)

    def wait(self, ms: int) -> None:
        time.sleep(ms / 1000)

    def pageleave(self) -> None:
        self._events.append(SessionEvent(
            timestamp=self._now(), event="$pageleave",
            url=self._page.url, properties={},
        ))

    def to_session_summary(self, session_id: str, person_email: str) -> SessionSummary:
        return SessionSummary(
            session_id=session_id,
            person_email=person_email,
            person_id=person_email.split("@")[0],
            start_url=self._events[0].url if self._events else BASE_URL,
            duration_seconds=int(time.time() - self._start),
            click_count=self._clicks,
            keypress_count=self._keypresses,
            console_error_count=self._console_errors,
            console_warn_count=self._console_warns,
            activity_score=min(100, self._clicks * 4 + self._console_errors * 15),
            events=self._events,
        )


# ── Scenarios ────────────────────────────────────────────────────────────────
# Each function receives an active SessionRecorder and scripts one user journey.
# Page creation and teardown are handled by the caller.

def scenario_invoice_save_fails(r: SessionRecorder) -> None:
    """Save fails silently → 404 from static server, error swallowed, user rage-clicks."""
    r.goto(f"{BASE_URL}#/invoices")
    r.wait(500)
    r.click("a[href='#/invoices/new']", "New Invoice")
    r.wait(600)
    r.fill("#invoice-client", "Acme Corp")
    r.fill("#invoice-amount", "1500")
    r.wait(400)
    r.click("#save-invoice", "Save Invoice")
    r.wait(900)
    r.click("#save-invoice", "Save Invoice")
    r.wait(400)
    r.click("#save-invoice", "Save Invoice")
    r.wait(400)
    r.click("#save-invoice", "Save Invoice")
    r.wait(1000)
    r.pageleave()


def scenario_upgrade_button_dead(r: SessionRecorder) -> None:
    """Upgrade Plan button looks up #upgrade-modal (null) → silently does nothing."""
    r.goto(f"{BASE_URL}#/settings/billing")
    r.wait(800)
    r.click("#upgrade-btn", "Upgrade Plan")
    r.wait(1200)
    r.click("#upgrade-btn", "Upgrade Plan")
    r.wait(1000)
    r.click("#upgrade-btn", "Upgrade Plan")
    r.wait(3000)
    r.pageleave()


def scenario_oauth_popup_blocked(r: SessionRecorder) -> None:
    """Onboarding step 3: OAuth popup opens then immediately closes → console.error, no fallback."""
    r.goto(f"{BASE_URL}#/onboarding/step-1")
    r.wait(600)
    r.click("a[href='#/onboarding/step-2']", "Next")
    r.wait(500)
    r.click("a[href='#/onboarding/step-3']", "Next")
    r.wait(800)
    r.click("#connect-tool", "Connect your tool")
    r.wait(1500)
    r.click("#connect-tool", "Connect your tool")
    r.wait(2500)
    r.pageleave()


def scenario_happy_path(r: SessionRecorder) -> None:
    """Clean browse of the invoice list — no errors, no rage clicks."""
    r.goto(f"{BASE_URL}#/dashboard")
    r.wait(600)
    r.click("a[href='#/invoices']", "Invoices")
    r.wait(800)
    r.pageleave()


# (name, session_id, person_email, scenario_fn)
SCENARIOS = [
    ("Invoice save fails silently",      "sess_live_001", "sarah@acme.co",    scenario_invoice_save_fails),
    ("Upgrade plan button is dead",      "sess_live_002", "james@startup.io",  scenario_upgrade_button_dead),
    ("OAuth popup blocked — onboarding", "sess_live_003", "maria@bigcorp.com", scenario_oauth_popup_blocked),
    ("Happy path — invoice list",        "sess_live_004", "alex@design.co",    scenario_happy_path),
]


# ── Main ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="AI session bug detector")
    p.add_argument("--model",        default="phi4-mini")
    p.add_argument("--output",       choices=["json", "markdown", "both"])
    p.add_argument("--github-repo",  default=os.getenv("GITHUB_REPO"))
    p.add_argument("--github-token", default=os.getenv("GITHUB_TOKEN"))
    return p.parse_args()


def main():
    args = parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _log("Error: playwright not installed.")
        _log("Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    _log("Starting local demo app server...")
    start_server()
    _log(f"Demo app live at {BASE_URL}")

    github = None
    if args.github_repo:
        if not args.github_token:
            _log("Error: --github-token required when --github-repo is set.")
            sys.exit(1)
        from github_integration import GitHubClient
        github = GitHubClient(args.github_token, args.github_repo)
        _log(f"GitHub integration enabled → {args.github_repo}")

    results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        _log(f"Chromium launched. Recording {len(SCENARIOS)} sessions...\n")

        for name, session_id, email, scenario_fn in SCENARIOS:
            _log(f"Recording: {name}")
            page = browser.new_page(viewport=VIEWPORT)
            r = SessionRecorder(page)
            scenario_fn(r)
            session = r.to_session_summary(session_id, email)
            page.close()

            _log(f"  → {session.click_count} clicks, {session.console_error_count} errors, {session.duration_seconds}s")
            _log(f"  Analyzing with {args.model}...")

            try:
                analysis = analyze_session(session, model=args.model)
            except Exception as e:
                _log(f"  ERROR: {e}")
                continue

            count = len(analysis.get("issues", []))
            _log(f"  → {count} issue(s) found")
            print_report(session_id, email, analysis)

            if github and count > 0:
                for issue in analysis.get("issues", []):
                    url = github.create_issue(session_id, email, issue)
                    _log(f"  → GitHub: {'created ' + url if url else 'already exists, skipped'}")

            results.append({"session_id": session_id, "person": email, "analysis": analysis})

        browser.close()

    total = sum(len(r["analysis"].get("issues", [])) for r in results)
    _log()
    _log("=" * 55)
    _log(f"Done. {len(results)} sessions, {total} issues found.")

    if args.output in ("json", "both"):
        export_json(results, "report.json")
    if args.output in ("markdown", "both"):
        export_markdown(results, "report.md")


if __name__ == "__main__":
    main()
