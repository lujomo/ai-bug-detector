"""
GitHub Issues integration for the AI session bug detector.

Creates one GitHub issue per detected bug with severity label, what happened,
steps to reproduce, and affected session + user.
"""
import os
import requests

GITHUB_API = "https://api.github.com"

# Label names the detector will create/use in the target repo.
_SEVERITY_LABELS = {
    "high":   {"name": "ai-bug-detector: high",   "color": "d73a4a", "description": "High-severity bug detected by AI session analysis"},
    "medium": {"name": "ai-bug-detector: medium", "color": "e4a235", "description": "Medium-severity bug detected by AI session analysis"},
    "low":    {"name": "ai-bug-detector: low",    "color": "0075ca", "description": "Low-severity bug detected by AI session analysis"},
}
_DETECTOR_LABEL = {"name": "ai-bug-detector", "color": "22c55e", "description": "Auto-detected by AI session bug detector"}


class GitHubClient:
    def __init__(self, token: str, repo: str):
        """
        token: personal access token or fine-grained token with Issues write scope
        repo:  "owner/repo"
        """
        owner, name = repo.split("/", 1)
        self.owner = owner
        self.repo = name
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        self._ensure_labels()

    def _repo_url(self, path: str) -> str:
        return f"{GITHUB_API}/repos/{self.owner}/{self.repo}/{path}"

    def _ensure_labels(self) -> None:
        """Create detector labels in the repo if they don't already exist."""
        existing = {
            label["name"]
            for label in self.session.get(self._repo_url("labels"), params={"per_page": 100}).json()
            if isinstance(label, dict)
        }
        for label in [_DETECTOR_LABEL, *_SEVERITY_LABELS.values()]:
            if label["name"] not in existing:
                self.session.post(self._repo_url("labels"), json=label)

    def _issue_exists(self, title: str) -> bool:
        """Return True if an open issue with this exact title already exists."""
        resp = self.session.get(
            self._repo_url("issues"),
            params={"state": "open", "labels": "ai-bug-detector", "per_page": 100},
        )
        return any(i.get("title") == title for i in resp.json() if isinstance(i, dict))

    def create_issue(self, session_id: str, person: str, issue: dict) -> str | None:
        """
        Create a GitHub issue for a detected bug.
        Returns the issue URL, or None if it already exists (deduplication).
        """
        sev = issue.get("severity", "low").lower()
        title = f"[AI Bug Detector] {issue.get('title', 'Untitled bug')}"

        if self._issue_exists(title):
            return None

        steps_md = "\n".join(
            f"{i}. {step}"
            for i, step in enumerate(issue.get("steps_to_reproduce", []), 1)
        )

        body = f"""## {issue.get("what_happened", "")}

**Severity:** {sev.upper()}
**Page:** `{issue.get("page", "—")}`
**Type:** {issue.get("type", "—")}
**Confidence:** {issue.get("confidence", 0):.0%}
**Affected session:** `{session_id}` (user: {person})

### Steps to reproduce

{steps_md or "_No steps available._"}

---
_Auto-detected by AI session bug detector. Review the session replay for full context._
"""

        resp = self.session.post(
            self._repo_url("issues"),
            json={
                "title": title,
                "body": body,
                "labels": ["ai-bug-detector", _SEVERITY_LABELS.get(sev, _SEVERITY_LABELS["low"])["name"]],
            },
        )
        resp.raise_for_status()
        return resp.json().get("html_url")
