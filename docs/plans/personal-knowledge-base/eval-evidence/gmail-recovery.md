# Gmail recovery verification

Readonly OAuth completed with the owner's permission. Client and token live only in the private internal runtime folder; no credentials included here. The owner explicitly chose to use the provided Desktop client despite its earlier chat exposure; rotation remains recommended.

Live CLI diagnosis found HTTP 403, reason rateLimitExceeded, quota metric Total Query Cost, quota limit Units per minute per user. A successful independent threads.list and full threads.get confirmed credentials and API access worked. A bounded real ingest stored nine additional threads, retained 40 unchanged, skipped one security message, and received the rate rejection after 50 full reads. No successful discovery watermark advanced.

Official Gmail docs currently specify 6,000 units/minute/user/project, threads.list 10 units, full threads.get 120. Corrected ingestion uses 500-ID pages, spaces request costs at 80 units/second, waits at least a minute for quota recovery, and retains whitelisted Google error labels. No quota settings or authorization scopes were changed.

Regression checks: 43 KB tests, 28 second-brain tests, 15 workspace-map tests and 119 dashboard tests pass. Live production-path smoke run 1 made one page request and eight full reads, persisted page index 8. Run 2 made zero page requests and eight full reads, persisted page index 16. Successful watermark remained unset; no false full-coverage claim.

The first full paced run (bg_6) stopped after 1,028 reads, with 985 new items, 33 unchanged and 18 security-message exclusions (message-level count). The exact pending item succeeded on replay (page index 43 to 44). The next diagnostic run (bg_7) failed in kb_store.replace_rows during INSERT, not in Google transport. A bounded replay captured OperationalError, SQLITE_CANTOPEN (14). Default temporary storage failed within two items; directing SQLITE_TMPDIR to a private USB temporary directory completed twelve items (index 46 to 58). The internal filesystem had only 127 MB free; the USB had 44 GB free.

kb_store now defaults SQLITE_TMPDIR to the workspace volume, while preserving any explicit setting. No source files or unrelated system files were deleted. With the normal CLI environment and this fix, twelve real production-path items completed (index 58 to 70). All 43 KB, 28 second-brain, 15 workspace-map and 119 dashboard tests pass after the change. This is a verified local spill-storage fix, not a claim of full Gmail coverage.

The corrected full backfill and catch-up/unchanged rerun is running as current host job bg_1 (job registry restarted; this is not the earlier bg_6 or bg_7). The refreshed 24 automated KB eval cases all pass. U9 still awaits full-source verification; U12 needs separate payload/budget approval. U10/U11/U13 manual evidence remains stale and requires final-snapshot refresh before feature completion. No paid summarization or Anthropic upload is authorized.
