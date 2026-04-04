import json
from datetime import datetime, timezone

from utils import ts

_SEV_COLOR = {
    "high":   "\033[91m",
    "medium": "\033[93m",
    "low":    "\033[94m",
}
_RESET = "\033[0m"
_BOLD  = "\033[1m"

_SEV_BORDER = {"high": "#ef4444", "medium": "#f59e0b", "low": "#3b82f6"}
_SEV_TEXT   = {"high": "#dc2626", "medium": "#d97706", "low": "#2563eb"}
_SEV_BG     = {"high": "#fef2f2", "medium": "#fffbeb", "low": "#eff6ff"}


def _p(msg: str = "") -> None:
    print(f"{ts()} {msg}")


# ── Terminal output ───────────────────────────────────────────────────────────

def print_report(session_id: str, person: str, analysis: dict) -> None:
    issues = analysis.get("issues", [])
    intent = analysis.get("session_intent", "—")

    _p()
    _p(f"{'─' * 55}")
    _p(f"{_BOLD}Session{_RESET}  {session_id}")
    _p(f"{_BOLD}User{_RESET}     {person}")
    _p(f"{_BOLD}Intent{_RESET}   {intent}")
    _p(f"{_BOLD}Issues{_RESET}   {len(issues)}")
    _p(f"{'─' * 55}")

    if not issues:
        _p("  No issues detected.")
        _p()
        return

    for issue in issues:
        sev = issue.get("severity", "low").lower()
        color = _SEV_COLOR.get(sev, "")
        _p()
        _p(f"{color}{_BOLD}[{sev.upper()}]{_RESET}  {issue.get('title', '')}")
        _p(f"  Page:  {issue.get('page', '—')}")
        _p(f"  Type:  {issue.get('type', '—')}")
        _p()
        _p(f"  {issue.get('what_happened', '')}")
        steps = issue.get("steps_to_reproduce", [])
        if steps:
            _p()
            _p("  Steps to reproduce:")
            for i, step in enumerate(steps, 1):
                _p(f"    {i}. {step}")
        _p()
        _p(f"  Confidence: {issue.get('confidence', 0):.0%}")


# ── File exports ──────────────────────────────────────────────────────────────

def export_json(results: list, path: str) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_count": len(results),
        "issue_count": sum(len(r["analysis"].get("issues", [])) for r in results),
        "results": results,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"{ts()} JSON report saved to {path}")


def export_markdown(results: list, path: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    all_issues = [
        (r["session_id"], r["person"], issue)
        for r in results
        for issue in r["analysis"].get("issues", [])
    ]
    sev_order = {"high": 0, "medium": 1, "low": 2}
    all_issues.sort(key=lambda x: sev_order.get(x[2].get("severity", "low"), 2))
    counts = {"high": 0, "medium": 0, "low": 0}
    for _, _, issue in all_issues:
        counts[issue.get("severity", "low")] += 1

    lines = [
        "# AI Session Bug Detector — Report\n\n",
        f"Generated: {now}  \n",
        f"Sessions analyzed: **{len(results)}**  \n",
        f"Issues found: **{len(all_issues)}** ({counts['high']} high / {counts['medium']} medium / {counts['low']} low)\n\n",
    ]
    if not all_issues:
        lines.append("No issues detected.\n")
    else:
        for session_id, person, issue in all_issues:
            sev = issue.get("severity", "low").upper()
            lines += [
                "---\n\n",
                f"### [{sev}] {issue.get('title', '')}\n\n",
                f"**Session:** `{session_id}` | **User:** {person} | **Page:** `{issue.get('page', '—')}`  \n",
                f"**Type:** {issue.get('type', '—')} | **Confidence:** {issue.get('confidence', 0):.0%}\n\n",
                f"{issue.get('what_happened', '')}\n\n",
                "**Steps to reproduce:**\n\n",
            ]
            for i, step in enumerate(issue.get("steps_to_reproduce", []), 1):
                lines.append(f"{i}. {step}\n")
            lines.append("\n")

    with open(path, "w") as f:
        f.writelines(lines)
    print(f"{ts()} Markdown report saved to {path}")


def export_html(results: list, path: str) -> None:
    """
    Generate a self-contained HTML report with:
    - Summary stats (sessions, severity breakdown)
    - Grouped bug cards with affected user lists (cross-session deduplication)
    - Per-session cards with embedded rrweb replay and AI analysis
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    all_issues = [
        issue
        for r in results
        for issue in r["analysis"].get("issues", [])
    ]
    counts = {"high": 0, "medium": 0, "low": 0}
    for issue in all_issues:
        counts[issue.get("severity", "low")] += 1

    groups = _group_issues(results)

    # Embed session data (analysis + rrweb events) as JSON for the player scripts
    session_data = {
        r["session_id"]: {
            "person":          r["person"],
            "analysis":        r["analysis"],
            "rrweb_events":    r.get("rrweb_events", []),
            "posthog_url":     r.get("posthog_replay_url", ""),
        }
        for r in results
    }

    html = _build_html(now, len(results), counts, groups, results, session_data)

    with open(path, "w") as f:
        f.write(html)
    print(f"{ts()} HTML report saved to {path}")


# ── Grouping ──────────────────────────────────────────────────────────────────

def _group_issues(results: list) -> list:
    """Cluster identical bugs across sessions by (normalised title, page)."""
    groups: dict = {}
    for r in results:
        for issue in r["analysis"].get("issues", []):
            key = (issue.get("title", "").strip().lower(), issue.get("page", ""))
            if key not in groups:
                groups[key] = {"issue": issue, "affected": []}
            groups[key]["affected"].append({"session_id": r["session_id"], "person": r["person"]})

    sev_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(groups.values(),
                  key=lambda g: sev_order.get(g["issue"].get("severity", "low"), 2))


# ── HTML builders ─────────────────────────────────────────────────────────────

def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _group_card(group: dict) -> str:
    issue    = group["issue"]
    affected = group["affected"]
    sev      = issue.get("severity", "low").lower()
    border   = _SEV_BORDER.get(sev, "#3b82f6")
    text_col = _SEV_TEXT.get(sev, "#2563eb")
    bg       = _SEV_BG.get(sev, "#eff6ff")

    user_chips = "".join(
        f'<span class="inline-block px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs mr-1 mb-1">{_esc(a["person"])}</span>'
        for a in affected
    )
    steps = "".join(
        f'<li>{_esc(s)}</li>'
        for s in issue.get("steps_to_reproduce", [])
    )

    return f"""
<div class="bg-white rounded-xl border border-gray-200 border-l-4 p-5 mb-3"
     style="border-left-color:{border}">
  <div class="flex items-start justify-between mb-2">
    <div>
      <span class="text-xs font-bold uppercase tracking-wide" style="color:{text_col}">{_esc(sev)}</span>
      <h3 class="font-semibold text-gray-900 mt-0.5">{_esc(issue.get("title",""))}</h3>
      <p class="text-xs text-gray-400 mt-0.5">{_esc(issue.get("page",""))}</p>
    </div>
    <span class="text-sm font-semibold text-gray-700 whitespace-nowrap ml-4">{len(affected)} affected</span>
  </div>
  <p class="text-sm text-gray-600 mb-3">{_esc(issue.get("what_happened",""))}</p>
  {f'<ol class="text-xs text-gray-500 list-decimal list-inside mb-3 space-y-0.5">{steps}</ol>' if steps else ""}
  <div class="flex flex-wrap">{user_chips}</div>
</div>"""


def _session_card(result: dict) -> str:
    sid      = result["session_id"]
    person   = result["person"]
    analysis = result["analysis"]
    issues   = analysis.get("issues", [])
    intent   = analysis.get("session_intent", "—")
    ph_url   = result.get("posthog_replay_url", "")
    has_rrweb = bool(result.get("rrweb_events"))

    issue_badges = ""
    for issue in issues:
        sev    = issue.get("severity", "low").lower()
        border = _SEV_BORDER.get(sev, "#3b82f6")
        col    = _SEV_TEXT.get(sev, "#2563eb")
        bg     = _SEV_BG.get(sev, "#eff6ff")
        issue_badges += f"""
<div class="rounded-lg border p-3 mb-2" style="border-color:{border};background:{bg}">
  <span class="text-xs font-bold uppercase" style="color:{col}">{_esc(sev)}</span>
  <span class="text-sm font-medium text-gray-900 ml-2">{_esc(issue.get("title",""))}</span>
  <p class="text-xs text-gray-500 mt-1">{_esc(issue.get("what_happened",""))}</p>
</div>"""

    player_section = ""
    if has_rrweb:
        player_section = f'<div id="player-{_esc(sid)}" class="rounded-lg overflow-hidden border border-gray-200 mb-4 bg-gray-900" style="min-height:200px"></div>'
    else:
        player_section = '<div class="rounded-lg border border-dashed border-gray-200 bg-gray-50 flex items-center justify-center mb-4" style="min-height:80px"><p class="text-xs text-gray-400">No replay — run capture_fixture.py to record rrweb sessions</p></div>'

    ph_link = f'<a href="{_esc(ph_url)}" target="_blank" class="text-xs text-blue-500 hover:underline mt-3 inline-block">View in PostHog →</a>' if ph_url else ""

    no_issues_note = '<p class="text-sm text-gray-400 italic">No issues detected.</p>' if not issues else ""

    return f"""
<div class="bg-white rounded-xl border border-gray-200 p-6 mb-4">
  <div class="flex items-center justify-between mb-4">
    <div class="flex items-center gap-2">
      <code class="text-xs bg-gray-100 px-2 py-0.5 rounded text-gray-600">{_esc(sid)}</code>
      <span class="text-sm text-gray-700">{_esc(person)}</span>
    </div>
    <span class="text-xs text-gray-400 italic max-w-xs text-right truncate">{_esc(intent)}</span>
  </div>
  {player_section}
  {issue_badges}
  {no_issues_note}
  {ph_link}
</div>"""


def _build_html(now, session_count, counts, groups, results, session_data) -> str:
    total_issues = counts["high"] + counts["medium"] + counts["low"]
    groups_html   = "".join(_group_card(g) for g in groups) if groups else '<p class="text-sm text-gray-400 italic">No issues found across all sessions.</p>'
    sessions_html = "".join(_session_card(r) for r in results)
    data_json     = json.dumps(session_data)

    # JS is kept as a plain string (no f-string) to avoid brace-escaping hell
    player_script = r"""
window.addEventListener('load', function() {
  var sessions = window.__LUCENT_SESSIONS__;
  if (!sessions || typeof rrwebPlayer === 'undefined') return;
  Object.keys(sessions).forEach(function(sid) {
    var data = sessions[sid];
    var el = document.getElementById('player-' + sid);
    if (!el || !data.rrweb_events || data.rrweb_events.length === 0) return;
    try {
      new rrwebPlayer({
        target: el,
        props: {
          events: data.rrweb_events,
          width: 860,
          height: 540,
          autoPlay: false,
          showController: true,
        }
      });
    } catch(e) {
      el.innerHTML = '<p style="color:#9ca3af;padding:16px;font-size:12px">Replay unavailable: ' + e.message + '</p>';
    }
  });
});
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI Session Bug Detector — Report — {_esc(now)}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/rrweb-player@latest/dist/style.css" />
  <script src="https://cdn.jsdelivr.net/npm/rrweb-player@latest/dist/index.js"></script>
  <style>
    .rr-player {{ border-radius: 0; }}
  </style>
</head>
<body class="bg-gray-50 font-sans text-gray-900 antialiased">
<div class="max-w-4xl mx-auto px-6 py-10">

  <!-- Header -->
  <div class="flex items-center justify-between mb-10">
    <div class="flex items-center gap-2">
      <div class="w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center">
        <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>
      <span class="font-bold text-lg tracking-tight">AI Session Bug Detector</span>
    </div>
    <span class="text-sm text-gray-400">Generated {_esc(now)}</span>
  </div>

  <!-- Stats -->
  <div class="grid grid-cols-4 gap-4 mb-10">
    <div class="bg-white rounded-xl border border-gray-200 p-5">
      <p class="text-2xl font-bold text-gray-900">{session_count}</p>
      <p class="text-xs text-gray-500 mt-1">Sessions analyzed</p>
    </div>
    <div class="bg-white rounded-xl border border-gray-200 p-5">
      <p class="text-2xl font-bold" style="color:#dc2626">{counts["high"]}</p>
      <p class="text-xs text-gray-500 mt-1">High severity</p>
    </div>
    <div class="bg-white rounded-xl border border-gray-200 p-5">
      <p class="text-2xl font-bold" style="color:#d97706">{counts["medium"]}</p>
      <p class="text-xs text-gray-500 mt-1">Medium severity</p>
    </div>
    <div class="bg-white rounded-xl border border-gray-200 p-5">
      <p class="text-2xl font-bold" style="color:#2563eb">{counts["low"]}</p>
      <p class="text-xs text-gray-500 mt-1">Low severity</p>
    </div>
  </div>

  <!-- Bug groups -->
  <div class="flex items-baseline justify-between mb-4">
    <h2 class="text-lg font-semibold">Issues found</h2>
    <span class="text-sm text-gray-400">{total_issues} total · {session_count} sessions</span>
  </div>
  {groups_html}

  <!-- Sessions -->
  <h2 class="text-lg font-semibold mb-4 mt-10">Sessions</h2>
  {sessions_html}

</div>

<script>window.__LUCENT_SESSIONS__ = {data_json};</script>
<script>{player_script}</script>
</body>
</html>"""
