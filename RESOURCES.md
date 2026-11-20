# Personal Pydantic AI Agents Resources

## Knowledge

- [Pydantic AI overview](https://pydantic.dev/docs/ai/overview/)
  Official starting point for the Python agent framework and its test model. Use for setup and core vocabulary.
- [Pydantic AI agents](https://pydantic.dev/docs/ai/core-concepts/agent/)
  Official API for constructing and running agents, instructions, outputs, and run limits. Use when building each specialist.
- [Pydantic AI function tools](https://pydantic.dev/docs/ai/tools-toolsets/tools/)
  Official contracts for typed function tools. Use when exposing a small, testable capability to a model.
- [Pydantic AI dependencies](https://pydantic.dev/docs/ai/core-concepts/dependencies/)
  Official dependency-injection pattern using `RunContext`. Use to pass clients and settings without putting secrets in prompts.
- [Pydantic AI structured output](https://pydantic.dev/docs/ai/core-concepts/output/)
  Official output modes and validation. Use when an agent must return a known data shape.
- [Pydantic AI testing](https://pydantic.dev/docs/ai/testing/)
  Official `TestModel`, `FunctionModel`, and agent override patterns. Use for deterministic tests without paid model calls.
- [Pydantic AI multi-agent applications](https://pydantic.dev/docs/ai/guides/multi-agent-applications/)
  Official delegation patterns and usage limits. Use only after each single-purpose agent works.
- [Gmail `users.messages.list`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list), [Gmail `users.messages.get`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get), and [Gmail OAuth scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
  Google's API contracts and permission scopes. Use to verify read-only access and avoid broader permissions.
- [Personal knowledge base guide](./KB-README.md)
  Workspace-specific Gmail archive, search, privacy, freshness, and approval rules. Use this instead of inventing a second mail connector.
- [Alexa Smart Home Skills](https://developer.amazon.com/en-US/alexa/alexa-skills-kit/get-deeper/smart-home-skills)
  Amazon's overview of skills that expose a device provider's cloud-connected devices to Alexa. Use to distinguish that flow from an agent controlling arbitrary Alexa-linked devices.
- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest)
  Official authentication and service-call API. Use only when Home Assistant already controls the target entity.
- [Home Assistant Alexa integration](https://www.home-assistant.io/integrations/alexa/)
  Official options for connecting Home Assistant entities to Alexa. Use to assess whether a particular device is supported.
- [NYC Open Data API guide](https://www.nyc.gov/opendata/get-started/user-guides/open-data-apis) and [Socrata API endpoints](https://dev.socrata.com/docs/endpoints.html)
  Official city and API-provider guidance for finding and querying public datasets.
- [NYC 311 Service Requests from 2020 to Present](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9)
  City dataset for a narrow NYC data-agent exercise. Use its metadata and update notes; do not treat records as legal or policy authority.

## Wisdom (Communities)

- [Pydantic GitHub Discussions](https://github.com/pydantic/pydantic-ai/discussions)
  Ask implementation questions after reducing them to a small reproducible example.
- [Home Assistant Community](https://community.home-assistant.io/)
  Compare device-integration experiences when official compatibility docs do not answer a device-specific question.

## Gaps

- Official Alexa skill docs describe Alexa calling a device provider's skill; they do not establish a general public API for an agent to command every device already linked to a consumer's Alexa account. Confirm each device's supported control path before implementation.
- Home Assistant availability, device integrations, and remote-access configuration are unknown. Do not assume Alexa exposure makes a device controllable through Home Assistant.
- Hosted-model handling of private email needs a separate provider, retention, and data-transfer decision.
