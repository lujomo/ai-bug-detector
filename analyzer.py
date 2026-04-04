import json
from openai import OpenAI
from posthog_client import SessionSummary

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # Ollama requires a value but ignores it
)

SYSTEM_PROMPT = """You are a senior QA engineer analyzing user session replays to detect bugs and UX friction.

Given a session summary, identify issues the user encountered. Focus on:
- Silent failures: actions that should do something but produce no visible response
- Rage clicks: the same button clicked 3+ times in rapid succession
- Console errors: JavaScript errors, unhandled rejections, network failures
- Dead ends: user gets stuck on a page for a long time then leaves without completing their goal
- OAuth or auth failures

Respond ONLY with a valid JSON object matching this exact schema — no explanation, no markdown fences:
{
  "session_intent": "one sentence describing what the user was trying to accomplish",
  "issues": [
    {
      "type": "bug or ux_friction",
      "severity": "high, medium, or low",
      "title": "short title, max 8 words",
      "page": "the URL or page name where it occurred",
      "what_happened": "2-3 sentence description of the problem",
      "steps_to_reproduce": ["step 1", "step 2", "..."],
      "confidence": 0.0
    }
  ]
}

Severity guide:
- high: user could not complete a core action (save, submit, pay, onboard)
- medium: user was frustrated or confused but may have continued
- low: minor friction with no clear task failure

If no issues are detected, return an empty issues array. Only flag real issues supported by the event data."""


def _format_session(session: SessionSummary) -> str:
    lines = [
        f"Session ID: {session.session_id}",
        f"User: {session.person_email or session.person_id}",
        f"Start URL: {session.start_url}",
        f"Duration: {session.duration_seconds}s",
        f"Clicks: {session.click_count} | Keypresses: {session.keypress_count}",
        f"Console errors: {session.console_error_count} | Warnings: {session.console_warn_count}",
        f"Activity score: {session.activity_score}",
        "",
        "Event sequence (chronological):",
    ]
    for e in session.events[:60]:  # cap at 60 to stay within context limits
        detail = ""
        if e.properties.get("$el_text"):
            detail = f' → clicked "{e.properties["$el_text"]}"'
        elif e.properties.get("message"):
            detail = f' → {e.properties["message"]}'
        lines.append(f"  [{e.timestamp}] {e.event}{detail}  ({e.url})")
    return "\n".join(lines)


def analyze_session(session: SessionSummary, model: str = "phi4-mini") -> dict:
    prompt = _format_session(session)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this session:\n\n{prompt}"},
        ],
        temperature=0.1,
        max_tokens=600,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return json.loads(content)
