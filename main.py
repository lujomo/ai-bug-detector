#!/usr/bin/env python3
"""
AI session bug detector — demo using PostHog session replays.

Usage:
  # Demo mode (no PostHog account needed):
  python main.py --demo

  # Real PostHog data:
  python main.py --project-id 12345 --api-key phx_...

  # Export a markdown report:
  python main.py --demo --output markdown

  # Push detected bugs to GitHub Issues:
  python main.py --demo --github-repo owner/repo --github-token ghp_...
"""
import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from posthog_client import PostHogClient
from analyzer import analyze_session
from reporter import print_report, export_json, export_markdown
from sample_data import SAMPLE_SESSIONS
from utils import ts


def _log(msg: str = "", **kwargs) -> None:
    print(f"{ts()} {msg}", **kwargs)


def parse_args():
    p = argparse.ArgumentParser(
        description="AI session bug detector — PostHog session replays"
    )
    p.add_argument("--project-id", default=os.getenv("POSTHOG_PROJECT_ID"),
                   help="PostHog project ID")
    p.add_argument("--api-key", default=os.getenv("POSTHOG_API_KEY"),
                   help="PostHog personal API key")
    p.add_argument("--limit", type=int, default=5,
                   help="Number of sessions to fetch (default: 5)")
    p.add_argument("--model", default="phi4-mini",
                   help="Ollama model to use (default: phi4-mini)")
    p.add_argument("--output", choices=["json", "markdown", "both"],
                   help="Export results to file in addition to terminal output")
    p.add_argument("--demo", action="store_true",
                   help="Run on built-in sample data (no PostHog account needed)")
    p.add_argument("--github-repo",
                   default=os.getenv("GITHUB_REPO"),
                   help="Push detected bugs to GitHub Issues: owner/repo")
    p.add_argument("--github-token",
                   default=os.getenv("GITHUB_TOKEN"),
                   help="GitHub personal access token (Issues write scope)")
    return p.parse_args()


def main():
    args = parse_args()

    # ── Session source ────────────────────────────────────────────────
    if args.demo:
        sessions = SAMPLE_SESSIONS
        _log(f"[demo mode] Loaded {len(sessions)} sample sessions.")
    else:
        if not args.project_id or not args.api_key:
            _log(
                "Error: --project-id and --api-key are required.\n"
                "Alternatively, set POSTHOG_PROJECT_ID and POSTHOG_API_KEY in .env,\n"
                "or use --demo to run on sample data."
            )
            sys.exit(1)
        client = PostHogClient(args.api_key, args.project_id)
        _log(f"Fetching {args.limit} sessions from PostHog...")
        recordings = client.fetch_recordings(limit=args.limit)
        sessions = [client.get_session_summary(r) for r in recordings]
        _log(f"Fetched {len(sessions)} sessions.")

    # ── GitHub client (optional) ──────────────────────────────────────
    github = None
    if args.github_repo:
        if not args.github_token:
            _log("Error: --github-token is required when --github-repo is set.")
            sys.exit(1)
        from github_integration import GitHubClient
        _log(f"GitHub integration enabled → {args.github_repo}")
        github = GitHubClient(args.github_token, args.github_repo)

    # ── Analysis loop ─────────────────────────────────────────────────
    _log(f"Analyzing with {args.model} via Ollama...")
    _log()

    results = []
    for session in sessions:
        _log(f"Analyzing session {session.session_id}...")
        try:
            analysis = analyze_session(session, model=args.model)
            count = len(analysis.get("issues", []))
            _log(f"  → {count} issue(s) found")
            person = session.person_email or session.person_id
            print_report(session.session_id, person, analysis)

            # ── Push to GitHub Issues ─────────────────────────────────
            if github and count > 0:
                for issue in analysis.get("issues", []):
                    url = github.create_issue(session.session_id, person, issue)
                    if url:
                        _log(f"  → GitHub issue created: {url}")
                    else:
                        _log(f"  → GitHub issue already exists, skipped: {issue.get('title')}")

            results.append({
                "session_id": session.session_id,
                "person": person,
                "analysis": analysis,
            })
        except Exception as e:
            _log(f"  ERROR — {e}")

    # ── Summary ───────────────────────────────────────────────────────
    total_issues = sum(len(r["analysis"].get("issues", [])) for r in results)
    _log()
    _log(f"{'=' * 55}")
    _log(f"Done. {len(results)} sessions analyzed, {total_issues} issues found.")

    if args.output in ("json", "both"):
        export_json(results, "report.json")
    if args.output in ("markdown", "both"):
        export_markdown(results, "report.md")


if __name__ == "__main__":
    main()
