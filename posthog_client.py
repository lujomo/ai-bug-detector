import os
import requests
from dataclasses import dataclass, field
from typing import Optional

POSTHOG_BASE_URL = os.getenv("POSTHOG_HOST", "https://app.posthog.com")


@dataclass
class SessionEvent:
    timestamp: str
    event: str
    url: str
    properties: dict


@dataclass
class SessionSummary:
    session_id: str
    person_email: Optional[str]
    person_id: str
    start_url: str
    duration_seconds: int
    click_count: int
    keypress_count: int
    console_error_count: int
    console_warn_count: int
    activity_score: float
    events: list = field(default_factory=list)


class PostHogClient:
    def __init__(self, api_key: str, project_id: str):
        self.project_id = project_id
        self.base_url = POSTHOG_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def fetch_recordings(self, limit: int = 10, date_from: str = "-7d") -> list:
        url = f"{self.base_url}/api/projects/{self.project_id}/session_recordings/"
        resp = self.session.get(url, params={"limit": limit, "date_from": date_from})
        resp.raise_for_status()
        return resp.json().get("results", [])

    def fetch_session_events(self, session_id: str, limit: int = 100) -> list:
        url = f"{self.base_url}/api/projects/{self.project_id}/events/"
        resp = self.session.get(url, params={"session_id": session_id, "limit": limit})
        resp.raise_for_status()
        return resp.json().get("results", [])

    def get_session_summary(self, recording: dict) -> SessionSummary:
        session_id = recording["id"]
        person = recording.get("person", {})
        person_props = person.get("properties", {})

        raw_events = self.fetch_session_events(session_id)
        events = [
            SessionEvent(
                timestamp=e.get("timestamp", ""),
                event=e.get("event", ""),
                url=e.get("properties", {}).get("$current_url", ""),
                properties={
                    k: v for k, v in e.get("properties", {}).items()
                    if k in ("$event_type", "$el_text", "message", "error")
                },
            )
            for e in raw_events
        ]

        return SessionSummary(
            session_id=session_id,
            person_email=person_props.get("email"),
            person_id=person.get("distinct_id", "anonymous"),
            start_url=recording.get("start_url", ""),
            duration_seconds=int(recording.get("duration", 0) / 1000),
            click_count=recording.get("click_count", 0),
            keypress_count=recording.get("keypress_count", 0),
            console_error_count=recording.get("console_error_count", 0),
            console_warn_count=recording.get("console_warn_count", 0),
            activity_score=recording.get("activity_score", 0),
            events=events,
        )
