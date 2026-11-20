# Interviews: Waiting status and Update application layout

## Request (verbatim, 2026-11-16)

> layout interviews "update Application" and also set a wating status and push the to the bottom

## Answered questions (2026-11-16)

| Question | Answer |
| --- | --- |
| Where do Waiting applications go? | Their own "Waiting" card at the bottom of the Interviews page, just above Closed threads |
| How do Waiting applications count? | Counted in Tracked; not in "In conversation" or "New leads"; a separate Waiting count is added |
| Today page | Waiting rows stay off Today's next interview action until their status changes |
| Meaning | "Applied or interviewed; waiting to hear back" |

## Requirements

1. Add `waiting` to the statuses the tracker accepts (`interviews/job-applications.yml`, `dashboard-app/interview_editor.py`), labelled "Waiting".
2. Waiting rows render in a "Waiting" card below New leads and Agents and above Closed threads, with a short explanation of the status.
3. Changing a row's status to or from Waiting in the dashboard moves the row to the matching card without a reload and updates the counts.
4. Counts: Tracked includes Waiting; In conversation and New leads exclude it; Pipeline shows a Waiting count.
5. Today's next interview action never picks a Waiting row.
6. Waiting rows keep every row control (Interview mode, Posting, Update application) and can be reopened by choosing another status.
7. The "Update application" panel is laid out as clearly separated, labelled groups (status and priority, next action, log a signal, notes) with field widths sized to their content; it works at phone, tablet and desktop widths.
8. Existing behaviour stays: closed threads, other statuses, the single atomic write path, other pages that read the tracker.
