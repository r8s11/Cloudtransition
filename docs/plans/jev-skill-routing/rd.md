# Jev skill routing requirements

## Request

> Before you load a skill, send my task and the list of my skill names and descriptions to Jev as a choice question, and load the skill it picks. Add a None option, and test it on 10 of my past tasks.

## Clarification

- Target: **all agents**.
- A Choice supports at most 255 options, including None. Use multiple Choice questions, each including None, and compare candidates.
- Routing must not override system-mandated skills or other higher-priority instructions; those may need to load before routing.
- Test with 10 actual past tasks, not invented examples. Obtain explicit permission for the selected task text, destination, use of the local TypeSafe key, and a spending cap before any live request. A previous approval covered only link analysis.
- The exact supported-agent inventory, hook availability and method of comparing choices across independently normalized groups remain unverified; do not claim universal enforcement until each agent integration is verified. Unsupported agents must be identified, not silently omitted.
