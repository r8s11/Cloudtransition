# Interview editor — line-targeted writes to job-applications.yml

> interview_editor.py edits only owned lines in interviews/job-applications.yml (status/priority, next action, timeline signal, interview_notes/questions/preparation, new application), re-parses before atomic write, returns rebuilt row; comments and neighbours untouched.

_Saved: 2026-11-09T21:54:52Z_

Interview editor (dashboard-app/interview_editor.py): line-targeted writes to interviews/job-applications.yml — status/priority, next action, timeline signal, interview_notes / interview_questions / interview_preparation, new application. Edits only the lines it owns (comments and neighbours untouched), re-parses the file before the atomic write, returns the rebuilt row so app.js updates in place (status changes move row between cards).
