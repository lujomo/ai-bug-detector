#!/usr/bin/env python3
"""
Analyzes a captured fixture and generates an HTML report.

Loads fixture/sessions.json (produced by capture_fixture.py), reconstructs
each session, runs it through the LLM, groups bugs across sessions, and
writes report.html with embedded rrweb session replays.

Usage:
  python run_demo.py
  python run_demo.py --model qwen2.5:1.5b
  python run_demo.py --fixture fixture/sessions.json --output both
  python run_demo.py --github-repo owner/repo --github-token ghp_...
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from analyzer import analyze_session
from posthog_client import SessionEvent, SessionSummary
from reporter import export_html, export_json, export_markdown, print_report
from utils import ts

FIXTURE_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture")
DEFAULT_FIXTURE = os.path.join(FIXTURE_DIR, "sessions.json")


def _log(msg: str = "") -> None:
    print(f"{ts()} {msg}")


def _load_fixture(path: str) -> tuple[dict, list[SessionSummary]]:
    """Load fixture JSON and reconstruct SessionSummary objects."""
    with open(path) as f:
        fixture = json.load(f)

    sessions = []
    for s in fixture["sessions"]:
        events = [SessionEvent(**e) for e in s.get("events", [])]
        sessions.append(SessionSummary(
            session_id=s["session_id"],
            person_email=s["person_email"],
            person_id=s["person_email"].split("@")[0],
            start_url=s.get("start_url", ""),
            duration_seconds=s["duration_seconds"],
            click_count=s["click_count"],
            keypress_count=s["keypress_count"],
            console_error_count=s["console_error_count"],
            console_warn_count=s["console_warn_count"],
            activity_score=s["activity_score"],
            events=events,
        ))
    return fixture, sessions


def parse_args():
    p = argparse.ArgumentParser(description="Analyze a fixture and generate an HTML report")
    p.add_argument("--fixture",      default=DEFAULT_FIXTURE, help="Path to fixture JSON")
    p.add_argument("--model",        default="phi4-mini",     help="Ollama model (default: phi4-mini)")
    p.add_argument("--output",       choices=["json", "markdown", "html", "all"], default="html")
    p.add_argument("--github-repo",  default=os.getenv("GITHUB_REPO"))
    p.add_argument("--github-token", default=os.getenv("GITHUB_TOKEN"))
    return p.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.fixture):
        _log(f"Fixture not found: {args.fixture}")
        _log("Run 'python capture_fixture.py' first to record sessions.")
        sys.exit(1)

    _log(f"Loading fixture: {args.fixture}")
    fixture, sessions = _load_fixture(args.fixture)
    _log(f"Loaded {len(sessions)} sessions (captured {fixture.get('captured_at', 'unknown')})")

    github = None
    if args.github_repo:
        if not args.github_token:
            _log("Error: --github-token required when --github-repo is set.")
            sys.exit(1)
        from github_integration import GitHubClient
        github = GitHubClient(args.github_token, args.github_repo)
        _log(f"GitHub integration enabled → {args.github_repo}")

    _log(f"Analyzing with {args.model}...\n")

    results = []
    fixture_sessions_by_id = {s["session_id"]: s for s in fixture["sessions"]}

    for session in sessions:
        _log(f"Analyzing {session.session_id} ({session.person_email})...")
        try:
            analysis = analyze_session(session, model=args.model)
        except Exception as e:
            _log(f"  ERROR: {e}")
            continue

        count = len(analysis.get("issues", []))
        _log(f"  → {count} issue(s) found")
        print_report(session.session_id, session.person_email, analysis)

        if github and count > 0:
            for issue in analysis.get("issues", []):
                url = github.create_issue(session.session_id, session.person_email, issue)
                _log(f"  → GitHub: {'created ' + url if url else 'already exists, skipped'}")

        # Merge fixture data (rrweb events, PostHog URL) with analysis
        fixture_data = fixture_sessions_by_id.get(session.session_id, {})
        results.append({
            "session_id":        session.session_id,
            "person":            session.person_email,
            "analysis":          analysis,
            "rrweb_events":      fixture_data.get("rrweb_events", []),
            "posthog_replay_url": fixture_data.get("posthog_replay_url", ""),
        })

    total = sum(len(r["analysis"].get("issues", [])) for r in results)
    _log()
    _log("=" * 55)
    _log(f"Done. {len(results)} sessions analyzed, {total} issues found.")

    if args.output in ("html", "all"):
        export_html(results, "report.html")
    if args.output in ("json", "all"):
        export_json(results, "report.json")
    if args.output in ("markdown", "all"):
        export_markdown(results, "report.md")


if __name__ == "__main__":
    main()
