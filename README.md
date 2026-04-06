# AI Session Bug Detector

Automatically detects bugs and UX friction in user session recordings using a local LLM. Analyzes click patterns, console errors, and navigation events to surface rage clicks, silent failures, dead-end flows, and auth issues — then exports a report or pushes findings directly to GitHub Issues.

## How it works

1. Sessions are collected (from PostHog, a live Playwright recording, or a fixture file)
2. Each session is formatted as a structured event log and sent to a local Ollama LLM
3. The LLM returns structured JSON: session intent, issue type, severity, what happened, steps to reproduce, and confidence
4. Results are printed to the terminal and optionally exported as HTML, JSON, or Markdown

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally with a model pulled (default: `phi4-mini`)

```bash
pip install -r requirements.txt
```

For the live recording and fixture demos, also install Playwright:

```bash
pip install playwright && playwright install chromium
```

## Demos

There are three ways to run the demo, in increasing order of fidelity.

---

### Demo 1 — Sample data (no dependencies)

Runs the LLM analyzer against four built-in sessions in `sample_data.py`. No browser, no PostHog account needed.

```bash
python main.py --demo
```

Optional flags:

```
--model qwen2.5:1.5b      # use a different Ollama model
--output markdown          # also write report.md
--output json              # also write report.json
--output both
--github-repo owner/repo --github-token ghp_...   # push bugs to GitHub Issues
```

---

### Demo 2 — Live Playwright recording

Launches `demo_app/index.html` on a local server, runs four scripted Playwright sessions through it, analyzes each session as it completes, and prints results to the terminal.

```bash
python record_session.py
```

The demo app (`demo_app/index.html`) is a fake invoicing SaaS called **Invoicr** with three intentional bugs:

| Bug | Scenario | What happens |
|-----|----------|--------------|
| Silent save failure | `scenario_invoice_save_fails` | "Save Invoice" posts to `/api/invoices` which 404s; the error is caught and swallowed — no toast, no message shown to the user |
| Dead upgrade button | `scenario_upgrade_button_dead` | "Upgrade Plan" looks up `#upgrade-modal` which doesn't exist; the button silently does nothing |
| OAuth popup blocked | `scenario_oauth_popup_blocked` | "Connect your tool" opens a popup that is immediately blocked; `console.error` is logged but no fallback UI is shown |

Optional flags (same as Demo 1):

```
--model phi4-mini
--output markdown
--github-repo owner/repo --github-token ghp_...
```

---

### Demo 3 — Fixture capture + HTML report (recommended)

Two-step process. First, record sessions into a self-contained fixture file. Then analyze the fixture and generate an HTML report with embedded [rrweb](https://github.com/rrweb-io/rrweb) session replays.

**Step 1 — capture:**

```bash
python capture_fixture.py
# writes fixture/sessions.json
```

**Step 2 — analyze and report:**

```bash
python run_demo.py
# writes report.html
```

Open `report.html` in a browser to see:
- Summary stats (sessions analyzed, issue counts by severity)
- Grouped bug cards with affected users (cross-session deduplication)
- Per-session cards with inline rrweb replay and AI analysis

Additional output formats:

```bash
python run_demo.py --output json       # report.json
python run_demo.py --output markdown   # report.md
python run_demo.py --output all        # all three
```

Other flags:

```
--fixture path/to/sessions.json        # use a different fixture
--model qwen2.5:1.5b                   # use a different Ollama model
--github-repo owner/repo --github-token ghp_...
```

---

## PostHog integration (optional)

To analyze real user sessions from PostHog instead of the demo app, set these environment variables in `.env`:

```
POSTHOG_PROJECT_ID=12345
POSTHOG_API_KEY=phx_...
```

Then run:

```bash
python main.py --limit 10
```

To also send rrweb events to PostHog during fixture capture, add:

```
POSTHOG_PROJECT_API_KEY=phc_...
POSTHOG_PROJECT_ID=12345
POSTHOG_HOST=https://us.i.posthog.com   # optional, defaults to us.i.posthog.com
```

PostHog replay URLs will be embedded in the HTML report when available.

---

## GitHub Issues integration (optional)

Pass `--github-repo` and `--github-token` to any of the three demos. The detector will:
- Create labels (`ai-bug-detector`, `ai-bug-detector: high/medium/low`) in the repo on first run
- Create one issue per detected bug, with severity, what happened, steps to reproduce, and the affected session ID
- Skip duplicates (deduplicates by title against open issues)

```bash
python run_demo.py --github-repo owner/repo --github-token ghp_...
```

The token needs the **Issues: write** scope (or classic token with `repo` scope).

---

## Project structure

```
main.py               # Demo 1 entry point (sample data / PostHog)
record_session.py     # Demo 2 entry point (live Playwright recording)
capture_fixture.py    # Demo 3 step 1 — record sessions to fixture
run_demo.py           # Demo 3 step 2 — analyze fixture, export report
analyzer.py           # LLM prompt + session formatter
reporter.py           # Terminal, HTML, JSON, and Markdown exporters
posthog_client.py     # PostHog API client + session data models
github_integration.py # GitHub Issues client
sample_data.py        # Built-in mock sessions for Demo 1
demo_app/index.html   # Local SaaS app with intentional bugs (Invoicr)
fixture/sessions.json # Captured sessions (produced by capture_fixture.py)
```
