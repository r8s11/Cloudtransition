# Job application autofill — Chrome extension + local helper

Status: draft for review (2026-11-11). This file is both the requirements doc and the design doc. Nothing is built until the eval next to it is approved.

## User request (verbatim)

> Okay, here's the thing. This is what I'm looking for. I'm looking for either a Chrome extension or an application that will let me autofill job applications. Maybe sometimes I want to make it autonomous and just have one of the agents in this repo do it for me. So I did get a plan from Google, and here are the four files. What you're going to do is in no way integrate or incorporate these files into the existing interview project interview section of this project.

The "four files" were four pasted iterations of a Google-generated plan for a Manifest V3 extension ("AutoApply & Form Autofill Engine" v1.0.0 → v1.3.0: popup, content script, background worker, Shadow DOM walker, combobox engine, resume upload via `DataTransfer`, Gemini/OpenAI question answering, confidence borders, CAPTCHA guard, multi-step wizard observer, floating HUD). They were not saved verbatim; the techniques kept and the parts changed are listed under [What is kept from the Google plan](#what-is-kept-from-the-google-plan).

## Answers given (2026-11-11)

| Question | Answer |
| --- | --- |
| Separation | Standalone project. No integration with `interviews/`, the dashboard Interviews tab, Forge / Scout / Job Reader / CV Adapter, `workspace/agents/`, or `docs/plans/job-application-submission-loop/`. |
| Who presses Submit | Auto-submit is allowed only on a run where the user turned it on, and only when every safety check passes. Otherwise the user submits. |
| Agent mode | Extension only for now. An agent driving it is a later project. |
| Sites | Greenhouse, Lever, Ashby, Workday, Indeed, iCIMS. Not LinkedIn Easy Apply. |
| Open-ended questions | AI drafts an answer from the resume, always marked for review. Provider: Claude or OpenAI (user picks). Not Gemini. |
| Profile source | Imported from `resume/master.md` plus a resume PDF; editable afterwards. |
| Build approach | Chrome extension plus a small local helper on 127.0.0.1 (picked over extension-only). |
| Input method | Simulated input by default; real input through Chrome's debugger only when a field does not take the simulated value. |

## Intent

Roosevelt is applying to many jobs. Retyping the same contact details, links, work-authorization answers and resume upload into every applicant tracking system (ATS) form is slow. He wants one click to fill a form correctly and, when he chooses, to finish the application when nothing on the page is uncertain. Later, an agent in this repo should be able to do the same thing for him.

Success: on a Greenhouse, Lever or Ashby posting, one click fills every standard field and uploads the resume. Each AI draft is marked for review. Nothing wrong or invented is ever submitted.

## Goals

1. Fill standard fields from the profile: name, email, phone, location, links, address, work authorization, sponsorship, voluntary self-identification (EEO) answers, and the resume file.
2. Work on the six named ATS families, including Shadow DOM, embedded iframes, custom dropdowns and multi-step forms.
3. Draft answers to open-ended questions with Claude or OpenAI, grounded only in the resume text. Every draft is marked for review.
4. Show the confidence of every field on the page (green = from the profile and confirmed on the page; yellow = check this).
5. Offer a per-run "Continue and submit when safe" switch. It clicks Next or Submit only when every check in [Safety checks](#safety-checks) passes.
6. Keep the API key out of the browser and personal data off any AI service except the resume text and the question.
7. Keep a local log of runs (what was filled, whether submitted and confirmed) without storing answer values.

## Non-goals

- Agent or autonomous mode (later project; the helper API is shaped so an agent can reuse it, but nothing agent-specific is built).
- LinkedIn Easy Apply, Gemini, TypeSafe/Jev field mapping.
- Creating ATS accounts, signing in, solving CAPTCHAs, or reading email.
- Writing to `interviews/job-applications.yml` or any file in the interview section, the dashboard, the Forge agents or `workspace/agents/`.
- Tailoring resumes or writing cover letters (the cover-letter upload slot is left alone).
- Publishing to the Chrome Web Store.

## Anti-goals (failure even if it "works")

- Submitting an application with a wrong, guessed or invented answer.
- Submitting the same application twice.
- The API key stored in the browser, or EEO answers, phone, address or email sent to an AI provider.
- A web page on the internet being able to talk to the helper.

## Constraints

- Branded Google Chrome 137+ ignores `--load-extension`; automated tests load the extension in Playwright's Chromium (or Chrome for Testing). Daily use is "Load unpacked" in the user's Chrome.
- The internal disk is full: test browsers and caches go on the USB volume (`PLAYWRIGHT_BROWSERS_PATH` under `job-autofill/.cache/`, gitignored; `TMPDIR` on the USB volume).
- The helper uses only the Python standard library (same as `tools/arms`), runs on Python 3.9+, and binds only to `127.0.0.1`.
- Paid AI calls in tests are forbidden: tests use a fake provider. A live call needs the user's explicit approval and budget.
- Model names are never hard-coded: the helper lists models from the chosen provider's models endpoint and the user picks one.
- New files under the repo get a router entry in `CODE.md` in the same change.

## Approaches

| Approach | Trade-off | Decision |
| --- | --- | --- |
| **Extension + local helper** | Key in macOS Keychain, profile read live from `resume/master.md`, run log and answer cache on disk, reusable by a future agent. Needs a small helper running; when it is off, profile fields still fill from the extension's cached copy but AI drafts are unavailable. | **Picked** by the user. |
| Extension only (the Google plan's shape) | Simplest. API key unencrypted in extension storage; resume edits need a manual re-import; nothing for an agent to reuse. | Rejected. |
| Script-driven Chrome over the DevTools protocol, no extension | Real input everywhere and agent-friendly, but no one-click use while browsing. | Deferred to agent mode. |

## Design

### Layout

```text
job-autofill/
├── README.md               install, load unpacked, start helper, pair, troubleshoot
├── package.json            dev-only: playwright; scripts test:unit, test:e2e, test, check
├── extension/              Manifest V3, no build step, plain ES modules
│   ├── manifest.json
│   ├── background.js       service worker: helper calls, debugger fallback, run state
│   ├── content/            matcher, fill engine, adapters (one per ATS), HUD, wizard
│   └── popup/              popup.html/css/js: Run, Profile, AI tabs
├── helper/                 Python stdlib
│   ├── server.py           127.0.0.1 HTTP API
│   ├── profile_import.py   reads resume/master.md
│   ├── ai.py               Claude / OpenAI calls, model listing, spend cap, answer cache
│   ├── store.py            config, profile overrides, run log under JOB_AUTOFILL_HOME
│   └── launchd/            optional LaunchAgent plist + install notes
└── tests/
    ├── unit/               node --test (matcher, scoring, safety checks)
    ├── helper/             python unittest
    ├── e2e/                Playwright + Chromium with the unpacked extension
    ├── fixtures/ats/       synthetic pages per ATS (no real personal data)
    └── fake_provider.py    fake Claude/OpenAI endpoints for tests
```

### Data locations

- `JOB_AUTOFILL_HOME` (default `~/.config/job-autofill/`, dir `0700`, files `0600`): `config.json` (port, provider, model, daily AI-call cap, resume PDF path, resume markdown path), `profile.json` (manual fields), `token` (pairing secret), `answers.json` (draft cache), `runs.jsonl` (run log). Nothing personal is written inside the repo.
- API keys: macOS Keychain generic passwords `job-autofill-anthropic` and `job-autofill-openai`, set by `python3 job-autofill/helper/server.py set-key anthropic|openai` (reads from stdin, never echoes).
- Extension `chrome.storage.local` (with the `unlimitedStorage` permission): pairing token, the last-synced profile, the resume PDF bytes as base64 with its name and type (so filling and upload work with the helper off), UI preferences. Never an API key.

### Profile

- Imported, read-only in the popup, re-read from `resume/master.md` on every sync: full name, first/last name, city, state, phone, email, website, GitHub URL, LinkedIn URL (from the contact line under the `#` name heading).
- Manual, editable in the popup, saved to `profile.json`: street address, ZIP, country, work authorization (Yes/No), needs sponsorship (Yes/No), gender, race/ethnicity, veteran status, disability status, each with "Leave blank" as default. Blank fields are never guessed.
- Resume PDF: a path in `config.json` chosen in the popup. The helper stores only the path and serves the bytes on `GET /resume.pdf`; the extension caches those bytes at each sync.
- Locations: the helper finds the workspace root from its own file path (`job-autofill/helper/` → two levels up), so it works from launchd. `config.json` key `resume_markdown` (default `resume/master.md`) and `resume_pdf` are resolved against that root unless absolute.
- AI grounding text: the resume markdown with every section marked `master only` removed (those were deliberately excluded from variants). It is re-read on every draft request; the answer-cache key includes its hash, so editing the resume invalidates old drafts.

### Field identification and confidence

A field that already holds a value (typed by the user or prefilled by the site) is left alone and not counted.

1. Per-ATS adapters identify fields by stable markers first (`autocomplete` tokens, Greenhouse/Lever/Ashby system field names, Workday `data-automation-id`, iCIMS/Indeed field ids). A field found this way is **green** after read-back.
2. Generic fallback: label/name/placeholder patterns (the Google plan's `FIELD_MATCHERS`). A short label that names the field ("First name", "Email") is green. A label that is a question (contains `?` or more than six words) is **yellow** even when it matches, so "Willing to relocate to this city?" never passes as green.
3. Dropdowns, radios and comboboxes use the alias dictionary and scorer: score ≥ 85 green, 70–84 yellow, below 70 not filled.
4. Every filled value is read back from the page. A value that did not stick is retried once through the debugger; if it still does not stick the field is yellow with "Couldn't set this field".
5. AI drafts are always yellow. Required fields left empty are yellow with "Required field still needs input".

### Input

- Default: native value setter + `input`/`change`/`blur` events, pointer/mouse sequence for clicks, `DataTransfer` for file inputs (drop events for Workday's drop zone).
- Fallback: `chrome.debugger` attach to the tab, `Input.insertText` / `Input.dispatchMouseEvent` / `Input.dispatchKeyEvent`, detach as soon as the field is done. Chrome shows its "started debugging this browser" bar during this. The user can switch the fallback off in the popup.

### AI drafts

- Sent to the helper: question text, field type, max length, options (for selects), page title, company name from the page, job title heading. The helper adds the grounding text. Never sent: phone, email, address, EEO answers, work-authorization answers.
- Rules enforced in code after the reply: trim to max length at a word boundary; digits only for number fields; a select answer must equal one of the options or nothing is filled.
- Cache: same question + company + grounding-text hash returns the cached draft without a new call.
- Daily cap on AI calls (default 30, set in the popup). At the cap, drafts stop and the popup says why.
- Provider errors (bad key, timeout, rate limit) are shown as errors, never as an empty answer.

### Safety checks

"Continue and submit when safe" is off at the start of every run and must be switched on for that run. When on, the extension clicks **Next** or **Submit** only if all of these hold for the current page:

1. No CAPTCHA widget (reCAPTCHA, hCaptcha, Cloudflare Turnstile, Arkose) in any frame.
2. No yellow field.
3. No AI draft on the page (follows from 2; stated so it cannot be relaxed by a confidence number).
4. Every required field has a value.
5. Every filled value matched on read-back.
6. The button is classified (Next vs Submit) and is not Back, Cancel, Save draft, Upload or a sign-in.
7. This URL has not already been submitted in this run.

Any failing check stops the run on that page with the reason in the in-page panel. After a Submit click, the extension waits up to 15 s for a confirmation (confirmation text such as "Thank you for applying" / "Application submitted", or a URL change to a known confirmation path) and logs `submitted_confirmed` or `submitted_unconfirmed`. It never clicks Submit a second time in the same run.

### Multi-step forms

A run watches the page for new steps (MutationObserver, ~850 ms settle, step fingerprint). Each new step is filled automatically. With the switch off, filling continues when the user clicks Next. A run ends on submit, Stop, 10 steps, or 5 minutes without a new step.

### Helper API (127.0.0.1 only)

Every request needs header `X-Job-Autofill-Token` equal to the pairing token and an `Origin` of `chrome-extension://…`; anything else gets 403 and no body. Endpoints: `GET /health`, `GET /profile`, `PUT /profile`, `GET /resume.pdf`, `GET /models?provider=`, `PUT /config`, `POST /draft`, `POST /runs`. Pairing: the helper prints the token once at first start and on `server.py pair`; the user pastes it into the popup.

### Run log

One JSON line per run in `runs.jsonl`: time, page host and path, ATS family, counts (green, yellow, AI drafts), steps, outcome (`filled`, `stopped:<reason>`, `submitted_confirmed`, `submitted_unconfirmed`), AI calls used. No field values and no draft text.

## What is kept from the Google plan

Kept: MV3 shape, `all_frames`, Shadow DOM walker, label extraction (`aria-labelledby`, `label[for]`, wrappers), native value setter, alias dictionary and word-boundary scorer, custom combobox engine, radio handling, `DataTransfer` resume upload with the cover-letter guard, CAPTCHA detector, step fingerprinting, Shadow DOM HUD, highlight restore.

Changed: API key and AI calls move to the helper; Gemini dropped; hard-coded model ids (`gemini-3.8-flash`, `gpt-5.4-mini`) replaced by a model list from the provider; the AI's self-reported confidence no longer turns a field green; keyword-only matches on question-style labels become yellow; read-back verification added; debugger fallback added; auto-submit is per-run and checks read-back and AI drafts; run state that must survive the service worker sleeping (after ~30 s idle) lives in `chrome.storage.session` instead of worker memory; a duplicate-submit guard and confirmation detection added.

## Builder-check calls (made by the assistant, open to correction)

- **Adapter choice:** the page host picks the adapter (`*.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`, `*.myworkdayjobs.com`, `*.icims.com`, `*.indeed.com`); each frame decides from its own host, so an embedded Greenhouse or iCIMS iframe gets its adapter. The generic label matcher then handles every field the adapter did not claim, and is the only matcher on other hosts.
- **Confirmation detection:** a built-in list per adapter (confirmation path patterns and heading text) plus a generic text pattern (`thank you for (applying|your application)`, `application (was )?(submitted|received)`). Not user-editable. Anything else is logged `submitted_unconfirmed`, which is the safe outcome.
- **Model choice:** stored per provider in `config.json` (`{"provider": "anthropic", "models": {"anthropic": "...", "openai": "..."}}`), so switching back restores the previous pick; a provider with no saved pick shows "— pick a model —" and drafts stay off until one is picked.

## Left to the builder

Exact adapter selectors per ATS (verified against live public postings without submitting), HUD and popup implementation within the mockup, helper port (default 8766, configurable), fixture page contents.

## Assumptions to confirm at review

- Daily AI-call cap default 30.
- The AI grounding text is `resume/master.md` with `master only` sections removed (not a tailored variant).
- Indeed Apply and Workday run inside the user's own signed-in session; the extension does nothing on sign-in pages.
- Real-site checks fill but never submit. The only real submission in acceptance is one the user names explicitly.
