# Manual verification — 2026-11-05

No private mail/session bodies, credentials, DB copies or API payloads are recorded here.

## U9 — partially verified, blocked by Gmail setup

Installed `~/Library/LaunchAgents/com.cloudtransition.personal-kb.plist`; StartInterval 21600, RunAtLoad false, absolute system Python and internal-disk launcher. Launcher delegates to private ingest virtualenv. `launchctl print` exited 0; `launchctl kickstart -p` launched PID 75519. Internal log `~/.local-routines/personal-kb/ingest.log` is mode 0600 and records actual Claude success (32 unchanged files, zero new/updated) and GmailAuthError with explicit setup guidance. No token exists; full configured-source schedule verification remains blocked by U12. Existing schedule definitions were not rewritten.

## U10 — pass

Actual local Claude inventory: 32 JSONL files; first ingest parsed 32, created 31 items, skipped one empty item. DB has 299 rows: 293 raw, six short. Coverage 2026-08-28 through 2026-11-05. Long pending summaries: 25. Malformed/incomplete records and source errors: zero. Second run parsed zero, skipped 32 unchanged files and added/updated zero items. SHA-256 manifests before/after both runs had zero byte differences and zero deletions. No paid requests made. Synthetic regression verifies archive retention if an original is later deleted.

## U11 — blocked by source coverage, not search speed

End-to-end Python CLI processes from /tmp:

| Query | Seconds | Observation |
| --- | ---: | --- |
| Pomodoro | 0.1602 | No match anywhere in actual Claude corpus; cannot claim Orca Pomodoro coverage |
| workspace map privacy | 0.1948 | Relevant source evidence for workspace_content.py readonly file access and privacy rules |
| Orizuru | 0.1451 | Relevant source evidence for dashboard design rationale and palette |

Opened the original JSONL for the latter topics using read's JSONL filter; verified the privacy-helper excerpt and Orizuru design-rationale title. No private bodies copied here. Earlier broad OR query `Orca Pomodoro` returned unrelated Orca-path research; this is NOT counted as a Pomodoro success. User approval is required to replace the unsupported named topic in U11, or it stays pending until source coverage exists.

## U12 — blocked, no login or spend approval

Gmail token absent. No OAuth flow started; no mailbox API reads performed. Feature/eval approval did not authorize login, payload transfer or any dollar cap. Anthropic key not requested or printed. Twenty-five current Claude long items are pending; Gmail could change that item count. Obtain login permission, complete interactive readonly setup, ingest Gmail twice, then present combined current inventory and official current model pricing for separate payload/budget approval.

## U13 — pass for reachable local handoff

Created the requested heading exactly once in ~/.claude/CLAUDE.md, preserving its pre-existing relocated-parent symlink. Read back the quoted literal kb.py path, distinctive-word retry, open-original rule, 12-hour refresh rule and untrusted-evidence warning. Actual CLI commands ran from /tmp. KB-README.md covers every module, optional SDKs, OAuth, schedule/logs, redaction, remote-summary approval, USB encryption risk and cleanupPeriodDays. No retention setting changed. CODE.md links to the implementation docs. All 40 KB tests and neighboring suites (28 second-brain, 15 map, 119 dashboard) passed. Automated evals are rerun after the final index refresh. Overall feature remains incomplete while U9/U11/U12 are blocked.
