# RoboNuggets "Second Brain" System

```mermaid
flowchart TB
    subgraph SRC["Sources"]
        YT["RoboNuggets YouTube\nTutorials"]
        SKOOL["Skool Community\nPlaybooks / Templates"]
        OWN["Your Own Notes\n& Project Logs"]
    end

    YT --> INGEST
    SKOOL --> INGEST
    OWN --> INGEST

    INGEST["Ingest\ninto Google NotebookLM"] --> REPO

    subgraph REPO["Centralized Knowledge Repository (NotebookLM)"]
        FUND["Fundamentals\nnodes, triggers, credentials,\ndata mapping, error handling"]
        AUTO["Automations\nrepeatable n8n workflows"]
        AGENT["Agents\nadvanced AI agent builds"]
    end

    REPO --> SYNTH["AI-Powered Synthesis\n(NotebookLM + Gemini)"]
    SYNTH --> PLAN["Actionable Study Plans"]
    PLAN --> PRACTICE["Forced Practice\nbuild & deploy real templates"]
    PRACTICE -->|feeds learnings back| OWN
```

**Flow:** Raw content (YouTube tutorials, Skool playbooks, your own notes) → ingested into a single NotebookLM notebook → organized into three categories (Fundamentals, Automations, Agents) → synthesized by AI into study plans → applied through forced practice, which feeds new learnings back into the loop.
