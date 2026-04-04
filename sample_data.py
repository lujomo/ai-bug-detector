from posthog_client import SessionEvent, SessionSummary

# Realistic mock sessions for demo mode (no PostHog account needed).
# Each session is crafted to surface a specific class of bug or UX issue.

SAMPLE_SESSIONS = [
    # Session 1: rage-clicking a broken Save button → silent network error
    SessionSummary(
        session_id="sess_abc123",
        person_email="sarah@acme.co",
        person_id="user_1",
        start_url="https://app.example.com/invoices",
        duration_seconds=187,
        click_count=23,
        keypress_count=45,
        console_error_count=2,
        console_warn_count=1,
        activity_score=82,
        events=[
            SessionEvent("2026-04-03T10:00:00Z", "$pageview",    "https://app.example.com/invoices",     {}),
            SessionEvent("2026-04-03T10:00:12Z", "$autocapture", "https://app.example.com/invoices",     {"$event_type": "click", "$el_text": "New Invoice"}),
            SessionEvent("2026-04-03T10:00:15Z", "$pageview",    "https://app.example.com/invoices/new", {}),
            SessionEvent("2026-04-03T10:01:02Z", "$autocapture", "https://app.example.com/invoices/new", {"$event_type": "click", "$el_text": "Save Invoice"}),
            SessionEvent("2026-04-03T10:01:03Z", "$autocapture", "https://app.example.com/invoices/new", {"$event_type": "click", "$el_text": "Save Invoice"}),
            SessionEvent("2026-04-03T10:01:04Z", "$autocapture", "https://app.example.com/invoices/new", {"$event_type": "click", "$el_text": "Save Invoice"}),
            SessionEvent("2026-04-03T10:01:05Z", "$autocapture", "https://app.example.com/invoices/new", {"$event_type": "click", "$el_text": "Save Invoice"}),
            SessionEvent("2026-04-03T10:01:30Z", "console_error","https://app.example.com/invoices/new", {"message": "Unhandled Promise Rejection: NetworkError when attempting to fetch resource"}),
            SessionEvent("2026-04-03T10:02:10Z", "$pageview",    "https://app.example.com/dashboard",    {}),
        ],
    ),

    # Session 2: user stuck on billing upgrade — button does nothing, user leaves
    SessionSummary(
        session_id="sess_def456",
        person_email="james@startup.io",
        person_id="user_2",
        start_url="https://app.example.com/settings/billing",
        duration_seconds=312,
        click_count=8,
        keypress_count=0,
        console_error_count=0,
        console_warn_count=0,
        activity_score=22,
        events=[
            SessionEvent("2026-04-03T11:00:00Z", "$pageview",    "https://app.example.com/settings/billing", {}),
            SessionEvent("2026-04-03T11:01:00Z", "$autocapture", "https://app.example.com/settings/billing", {"$event_type": "click", "$el_text": "Upgrade Plan"}),
            SessionEvent("2026-04-03T11:01:05Z", "$autocapture", "https://app.example.com/settings/billing", {"$event_type": "click", "$el_text": "Upgrade Plan"}),
            SessionEvent("2026-04-03T11:01:10Z", "$autocapture", "https://app.example.com/settings/billing", {"$event_type": "click", "$el_text": "Upgrade Plan"}),
            SessionEvent("2026-04-03T11:05:12Z", "$pageleave",   "https://app.example.com/settings/billing", {}),
        ],
    ),

    # Session 3: onboarding OAuth popup blocked, user retries and gives up
    SessionSummary(
        session_id="sess_ghi789",
        person_email="maria@bigcorp.com",
        person_id="user_3",
        start_url="https://app.example.com/onboarding/step-1",
        duration_seconds=523,
        click_count=31,
        keypress_count=120,
        console_error_count=2,
        console_warn_count=3,
        activity_score=67,
        events=[
            SessionEvent("2026-04-03T09:00:00Z", "$pageview",    "https://app.example.com/onboarding/step-1", {}),
            SessionEvent("2026-04-03T09:00:30Z", "$autocapture", "https://app.example.com/onboarding/step-1", {"$event_type": "click", "$el_text": "Next"}),
            SessionEvent("2026-04-03T09:00:31Z", "$pageview",    "https://app.example.com/onboarding/step-2", {}),
            SessionEvent("2026-04-03T09:01:00Z", "$autocapture", "https://app.example.com/onboarding/step-2", {"$event_type": "click", "$el_text": "Next"}),
            SessionEvent("2026-04-03T09:01:01Z", "$pageview",    "https://app.example.com/onboarding/step-3", {}),
            SessionEvent("2026-04-03T09:04:30Z", "$autocapture", "https://app.example.com/onboarding/step-3", {"$event_type": "click", "$el_text": "Connect your tool"}),
            SessionEvent("2026-04-03T09:04:35Z", "console_error","https://app.example.com/onboarding/step-3", {"message": "OAuth popup blocked by browser"}),
            SessionEvent("2026-04-03T09:08:41Z", "$autocapture", "https://app.example.com/onboarding/step-3", {"$event_type": "click", "$el_text": "Connect your tool"}),
            SessionEvent("2026-04-03T09:08:46Z", "console_error","https://app.example.com/onboarding/step-3", {"message": "OAuth popup blocked by browser"}),
            SessionEvent("2026-04-03T09:12:03Z", "$pageleave",   "https://app.example.com/onboarding/step-3", {}),
        ],
    ),

    # Session 4: clean session, no issues (tests the "no issues found" path)
    SessionSummary(
        session_id="sess_jkl012",
        person_email="alex@design.co",
        person_id="user_4",
        start_url="https://app.example.com/dashboard",
        duration_seconds=94,
        click_count=12,
        keypress_count=8,
        console_error_count=0,
        console_warn_count=0,
        activity_score=91,
        events=[
            SessionEvent("2026-04-03T14:00:00Z", "$pageview",    "https://app.example.com/dashboard",      {}),
            SessionEvent("2026-04-03T14:00:20Z", "$autocapture", "https://app.example.com/dashboard",      {"$event_type": "click", "$el_text": "View Report"}),
            SessionEvent("2026-04-03T14:00:22Z", "$pageview",    "https://app.example.com/reports/weekly", {}),
            SessionEvent("2026-04-03T14:01:34Z", "$pageleave",   "https://app.example.com/reports/weekly", {}),
        ],
    ),
]
