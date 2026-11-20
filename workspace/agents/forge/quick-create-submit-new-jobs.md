## User request

Submit me for new jobs.

Run the pipeline against postings not already seen, and take the work through to submission rather than stopping at a search report.

## Context

- Pipeline ownership (from `workspace/agents/forge/memory/index.md`): Scout searches and scores 0–100 → Forge shortlists → Job Reader reads one promoted listing → CV Adapter tailors the CV and exports Word + PDF. Search/ranking is free; Job Reader + CV Adapter spend tokens.
- Standing approval rule already recorded in Forge memory: paid promotion runs only on an explicit numbered pick by Roosevelt; scheduled scans never run paid work unattended. This request asks for submission without naming specific jobs, so the executing agent must either get the pick confirmed or treat the request as the authorization it is.
- Latest scans already on disk: `workspace/agents/scout/outputs/scan-2026-11-09` through `scan-2026-11-12` (`.json` + `.md`). 2026-11-12 scored 44 new unique listings against 99 prior ones excluded as already scored. "New" has to mean deduplicated against all of these.
- Already promoted and delivered (2026-11-11 / 2026-11-12): CAIS IT Support Associate (92), Stable Rock Tier 2 Support Engineer (86), NYC DSS Desktop Support Specialist (84). CVs for these exist as docx/pdf under `workspace/agents/cv-adapter/outputs/`.
- Known open item from 2026-11-12: the AI-evidence insertions drafted in `workspace/agents/forge/outputs/master-md-ai-evidence-final.md` were never pasted into `resume/master.md`, so AI-tool claims stay withheld from tailored CVs until that lands.
- Target track in use: IT support / desktop / service desk / sysadmin / EUC in the NYC metro, secondary junior cloud / Azure / M365 admin.
- Last scan run 2026-11-12; today is 2026-11-16, so listings are four days stale.
