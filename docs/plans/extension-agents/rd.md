# Job agents in the AutoFill Chrome extension

## Request (verbatim, 2026-11-16)

> wire the agents to chrome extention

## Answered questions (2026-11-16)

| Question | Answer |
| --- | --- |
| What should the extension do with the agents? | All four: (1) popup actions on a job posting page: Add to tracker, Read posting (Job Reader), Tailor CV (CV Adapter), with run status; (2) use that job's tailored CV when filling an application; (3) show Scout's latest leads in the popup and open them; (4) ask Gmail Reader about the company on the current page |
| How should the extension reach the agents? | Through the paired helper (`127.0.0.1:8766`), which forwards to the dashboard's existing run endpoints (`127.0.0.1:8000`) |
| One-click runs? | No. Show what will run (agent, model, URL) and require a Run click, like the dashboard |

## Requirements

1. The popup gets an **Agents** tab. It is available only when the extension is paired.
2. On a job posting page the tab shows the detected company, role and posting URL (editable before use) and whether this job is already in the tracker, read by Job Reader, and tailored by CV Adapter.
3. **Add to tracker** writes one `new_lead` entry to `interviews/job-applications.yml` through the dashboard's existing create endpoint. A job already tracked is not added twice.
4. **Read posting** starts the existing `job-reader` run and **Tailor CV** starts the existing `cv-tailor` run, through the dashboard's `/api/skills/run`. Tailor CV is offered only after the job has a Job Reader output and a base CV exists.
5. Before any run starts, the popup shows the agent, the model that will be used, the cost tag and the exact input (job id and URL), and requires a second, explicit **Run** click. Nothing runs on the first click.
6. The popup shows run status (running, done, failed with the reason) and survives being closed and reopened.
7. **Scout leads**: the tab lists the latest Scout scan's leads that are not in the tracker (company, title, score, location), each opening its posting in a new tab. The extension never starts a Scout scan.
8. **Tailored CV in autofill**: when the page being filled belongs to a tracked job that has a tailored CV, AI drafts are grounded in that tailored CV's headline, summary and experience bullets in addition to the resume. Drafts stay yellow for review. With no tailored CV, behaviour is unchanged.
9. **Emails about this company**: on an explicit click, the tab lists matching threads from the local Gmail archive (date, subject, short snippet, Gmail link), newest first. See assumption A1.
10. The extension still talks only to the helper. The helper forwards only to `127.0.0.1:8000`, only for an allow-list of actions, and only for paired requests. No new extension permission or host permission is added.
11. When the dashboard or the helper is not running, each action says so plainly and autofill keeps working as today.
12. Page content is untrusted: text from the posting page or from emails is never executed and never changes which agent, model or URL is run.

## Assumptions to confirm at review

- **A1 — Gmail without a model.** "Ask Gmail Reader" is delivered as a local archive lookup (`kb.py search --source gmail`): no model call, $0, and no email text leaves this computer. Running the Gmail Reader *agent* from the extension would send email content to a free OpenCode model provider; that is a data-transfer decision this request did not make, so it is left out.
- **A2 — Email results stay in the popup.** They are never passed to content scripts or the page.
- **A3 — Job detection.** Company and role come from the extension's existing ATS adapters when available, else from the page title; the user can correct them before any action.
- **A4 — Matching a page to a tracked job.** By posting URL (host + path, ignoring query and fragment) first, then by exact company + role.
