# Mission: Personal Pydantic AI Agents

## Why
Build useful Python agents for personal work: read Gmail, control smart-home devices, answer NYC-specific questions, and provide a pattern for adding more domain specialists.

## Success looks like
- Build and test a typed Pydantic AI agent with narrowly scoped tools and dependencies.
- Search the existing Gmail archive without giving the agent any write capability.
- Control only explicitly allowed smart-home devices through a supported API.
- Answer NYC questions from authoritative, current sources with evidence and uncertainty.
- Add a new specialist by defining its purpose, source set, tools, permissions, and tests.

## Constraints
- Starting level: basic Python; has built small scripts.
- Keep Gmail search on the existing local archive. Live email content must not go to a hosted model until its data handling is reviewed and approved.
- Alexa-linked devices need a supported control path. Home Assistant is one possible bridge, but its availability and device coverage are not yet established.
- Use synthetic data for exercises. Do not authorize live API calls, credentials, data transfers, or costs as part of the tutorial.

## Out of scope
- Sending or modifying Gmail.
- Public deployment or publishing an Alexa skill.
- Controlling locks, alarms, garage doors, or other high-impact devices without a separate approval design.
- Treating 311 data as legal, medical, or emergency guidance.
