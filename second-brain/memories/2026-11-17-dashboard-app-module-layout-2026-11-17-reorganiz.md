# dashboard-app module layout (2026-11-17 reorganization)

> dashboard-app helper modules moved into core/, collectors/, scripts/, docs/; app.py stays at root as the ASGI entry.

_Saved: 2026-11-17T23:00:43Z_

On 2026-11-17 dashboard-app was reorganized. app.py stays at the root (uvicorn app:app, tests import app). core/: agents.py, interview_editor.py, workspace_content.py, work_search.py, calendar_sources.py, google_calendar.py. collectors/: metrics.py, server_activity.py, metric_charts.py. scripts/: triage_jev.py, leads_jev.py, screenshot.sh (run as dashboard-app/scripts/<name>). docs/: 2026-11-12_DRIFT_REPORT.md, claude-usage.html. Import as packages (from core import agents, from collectors import metrics); calendar_bridge.py imports core.calendar_sources. Older memories citing dashboard-app/<module>.py paths predate this move; see dashboard-app/CLAUDE.md file map.
