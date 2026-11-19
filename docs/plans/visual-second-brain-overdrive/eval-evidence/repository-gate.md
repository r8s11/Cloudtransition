# Repository gate status

The Folded Atlas run reported R1 pass; all seventeen observed manual cases were subsequently recorded as pass. The later `check docs/plans/visual-second-brain-overdrive` invocation still evaluated other workspace features and exited 1.

Its output did not list Folded Atlas as failing. It listed unrelated recorded failures: checklist-calendar U5/U6; jev-command U2; jev-skill-routing U3/U4/R2; personal-knowledge-base U12. Other pre-existing evals were stale, changed, or never run. Those features were not part of this request and were not modified or rerun.

This is not a claim that the repository-wide gate passes. Folded Atlas has its own observed results; the global gate remains blocked by the unrelated cases above.

Temporary server cleanup via proc kill was unavailable because the daemon broker could not start. The internal disk also rejected a default screenshot temporary file. Final browser images and all evidence were saved on the external workspace volume; no user files were deleted to make space.

The three recorded temporary server PIDs no longer appeared in the process table when checked afterward. The production launchd service was not targeted for cleanup.
