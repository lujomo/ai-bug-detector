#!/usr/bin/env python3
"""
Captures real browser sessions and saves them as a fixture.

Runs each scenario in Playwright with rrweb recording active, extracts the
full rrweb event stream from the browser after each session, and saves
everything to fixture/sessions.json.

The fixture is self-contained — once captured, run_demo.py can analyze and
generate an HTML report with embedded session replays without any live
browser or PostHog account.

PostHog integration is optional: if POSTHOG_PROJECT_API_KEY is set, sessions
are also sent to PostHog and their replay URLs are included in the fixture.

Usage:
  python capture_fixture.py
  python capture_fixture.py --out fixture/sessions.json
"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from record_session import (
    SCENARIOS,
    VIEWPORT,
    SessionRecorder,
    _log,
    start_server,
    BASE_URL,
)

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture")
DEFAULT_FIXTURE = os.path.join(FIXTURE_DIR, "sessions.json")


def _capture_scenario(browser, name: str, session_id: str, email: str, scenario_fn, ph_key: str | None) -> dict:
    """
    Run one scenario with rrweb recording enabled.

    Returns a fixture session dict containing metadata, events (for LLM),
    rrweb_events (for HTML replay), and optionally a PostHog replay URL.
    """
    page = browser.new_page(viewport=VIEWPORT)

    # These init scripts run before any page script on every navigation,
    # ensuring rrweb's emit target exists and PostHog has its key.
    page.add_init_script("window.__rrweb_events__ = [];")
    if ph_key:
        ph_host = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
        page.add_init_script(
            f"window.__POSTHOG_KEY__ = '{ph_key}';"
            f"window.__POSTHOG_HOST__ = '{ph_host}';"
            f"window.__USER_EMAIL__ = '{email}';"
        )

    r = SessionRecorder(page)
    scenario_fn(r)

    # Let async events (fetch callbacks, console errors) settle
    time.sleep(0.5)

    rrweb_events = page.evaluate("window.__rrweb_events__ || []")

    posthog_session_id = None
    posthog_replay_url = None
    if ph_key:
        try:
            posthog_session_id = page.evaluate(
                "typeof posthog !== 'undefined' ? posthog.get_session_id() : null"
            )
            project_id = os.getenv("POSTHOG_PROJECT_ID")
            ph_host_ui = os.getenv("POSTHOG_HOST", "https://us.posthog.com")
            if posthog_session_id and project_id:
                posthog_replay_url = (
                    f"{ph_host_ui}/project/{project_id}/replay/{posthog_session_id}"
                )
        except Exception:
            pass

    session = r.to_session_summary(session_id, email)
    page.close()

    return {
        "scenario": name,
        "session_id": session.session_id,
        "person_email": session.person_email,
        "start_url": session.start_url,
        "duration_seconds": session.duration_seconds,
        "click_count": session.click_count,
        "keypress_count": session.keypress_count,
        "console_error_count": session.console_error_count,
        "console_warn_count": session.console_warn_count,
        "activity_score": session.activity_score,
        "events": [asdict(e) for e in session.events],
        "rrweb_events": rrweb_events,
        "posthog_session_id": posthog_session_id,
        "posthog_replay_url": posthog_replay_url,
    }


def main():
    parser = argparse.ArgumentParser(description="Capture browser sessions to fixture")
    parser.add_argument("--out", default=DEFAULT_FIXTURE, help="Output path for fixture JSON")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _log("Error: playwright not installed.")
        _log("Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    ph_key = os.getenv("POSTHOG_PROJECT_API_KEY")
    if ph_key:
        _log(f"PostHog enabled (project API key found) — sessions will be sent to PostHog")
    else:
        _log("PostHog not configured — capturing rrweb events only (set POSTHOG_PROJECT_API_KEY to enable)")

    _log("Starting local demo app server...")
    start_server()
    _log(f"Demo app live at {BASE_URL}")

    os.makedirs(FIXTURE_DIR, exist_ok=True)

    sessions = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        _log(f"Chromium launched. Recording {len(SCENARIOS)} sessions...\n")

        for name, session_id, email, scenario_fn in SCENARIOS:
            _log(f"Recording: {name} ({email})")
            session_data = _capture_scenario(browser, name, session_id, email, scenario_fn, ph_key)
            event_count = len(session_data["rrweb_events"])
            _log(f"  → {session_data['click_count']} clicks, "
                 f"{session_data['console_error_count']} console errors, "
                 f"{event_count} rrweb events captured")
            if session_data["posthog_replay_url"]:
                _log(f"  → PostHog replay: {session_data['posthog_replay_url']}")
            sessions.append(session_data)

        browser.close()

    fixture = {
        "version": "1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "app_url": BASE_URL,
        "viewport": VIEWPORT,
        "sessions": sessions,
    }

    with open(args.out, "w") as f:
        json.dump(fixture, f, indent=2)

    size_kb = os.path.getsize(args.out) // 1024
    _log()
    _log(f"Fixture saved to {args.out} ({size_kb} KB, {len(sessions)} sessions)")
    _log("Run 'python run_demo.py' to analyze and generate the HTML report.")


if __name__ == "__main__":
    main()
