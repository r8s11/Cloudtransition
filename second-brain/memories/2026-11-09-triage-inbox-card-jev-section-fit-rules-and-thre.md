# Triage inbox card — Jev section-fit rules and thresholds

> For every unchecked ## Inbox item, Jev answers two questions: does a ### section fit, which one. decide() thresholds: 0.7/0.3 Noul, 0.5 Choice; file-or-hold outcome; only item text plus section headings sent, never section contents.

_Saved: 2026-11-09T21:54:42Z_

Triage inbox card (dashboard-app/triage_jev.py): for every unchecked ## Inbox item, Jev answers two questions — does a ### section fit, and which one. decide() holds the thresholds that turn answers into file-or-hold: 0.7/0.3 for Noul and 0.5 for Choice. Only item text plus section headings is sent to Jev — never section contents. Context: OPENROUTEN_API_KEY/TYPESAFE_API_KEY from environment; triage_jev.py exits 2 when the key is missing, 3 on API failure, never writes TASKS.md in either case.
