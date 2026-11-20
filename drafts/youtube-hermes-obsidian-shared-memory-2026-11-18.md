# Hermes Obsidian is WILD (FREE!)

**Channel:** Julian Goldie SEO
**Duration:** 9:19
**URL:** https://www.youtube.com/watch?v=ZXjw8vNCWAU
**Published:** 2026-11-18
**Views at extraction:** ~15,370
**Transcript:** auto-generated English (no manual captions)

---

## Executive synthesis (STAR)

**Situation.** Four coding agents — Hermes (the free, open-source, local agent from Nous Research, released February 2026), Claude Code, Codex, and OpenClaw — each ship with a separate, deliberately tiny memory. Hermes' main memory file holds roughly 2,200 characters (about one page), and its user-profile file holds less. Each agent therefore starts every morning blind to what the others did yesterday.

**Task.** Give all four agents one shared, durable memory that survives between sessions without the operator hand-editing files, and without drowning the models in irrelevant context.

**Action.** Point every agent at a single Obsidian vault (plain-text notes in a local folder), structure that vault with PARA plus four extra folders, and let one "orchestrator" agent build and maintain the system from a single prompt. Each agent then gets a pointer that makes it read the vault at session start and a nightly task that writes a short day summary — with all rules centralized in one "protocol" note.

**Result.** Any agent can read another agent's nightly note and continue its work; a lesson learned by one agent propagates to the rest within a day. The host also demonstrates a voice agent that answers questions about the vault out loud, and Hermes' Instagram integration for phone access.

---

## Detailed summary

### 1. The problem: four agents, four amnesias (0:00 – 2:20)

- Hermes is the free, open-source agent from Nous Research (auto-captions render it "Noose Research"). It runs on the user's own computer and has memory, but the memory is small by design — a main file of ~2,200 characters plus an even smaller profile file.
- Hermes only remembers for Hermes. Claude Code, Codex, and OpenClaw keep their own separate memories.
- Analogy used: four helpers in one office who never talk to each other, so each starts the day with no idea what the others finished.
- The host frames the fix as a "memory galaxy": every dot is a note, every line is a link between notes. In his vault there are thousands of memories; clicking a node (example: "Goldie Agency") shows who Julian is and what the agency does, with everything cross-linked. He does not curate it — the agents keep it updated.

### 2. Why Obsidian (2:20 – 3:00)

- Obsidian is a free notes app whose notes are plain text files in a local folder. Agents can read and write them like any other file, which is what makes the approach tool-agnostic.
- The host cites Andrej Karpathy sharing a similar setup in April 2026: an agent keeps a folder of notes tidy and linked, with Obsidian as the viewer. The quote given is: **"Obsidian is the IDE, the LLM is the programmer, the wiki is the codebase."**
- Adoption signals cited: a Reddit post on using Obsidian as long-term Hermes memory with close to 800 upvotes, and the fact that Hermes ships an Obsidian skill built in.

### 3. Folder structure: PARA plus four (3:00 – 4:40)

Base system is PARA:

| Folder | Meaning | Examples given |
|---|---|---|
| Projects | Work with an end date | Launch the AI Profit Boardroom welcome email |
| Areas | Ongoing responsibilities | Community, SEO |
| Resources | Reference material | Brand voice |
| Archive | Finished work | — |

Four additional folders:

- **Inbox** — messy, uncategorized notes.
- **Daily** — the operator's own daily notes.
- **Memories** — decisions and wins.
- **Agent OS** — the folder the agents own; this is the shared sync point where Claude, Hermes, and the voice agent all write.

### 4. The setup pattern: one orchestrator, one prompt (4:40 – 5:50)

- The common mistake: configuring each agent by hand, one at a time.
- Instead, designate one agent as the **orchestrator**. Claude Code or Codex are recommended because both can read and write files across the machine.
- Give the orchestrator one prompt along these lines: set up a shared Obsidian memory for all my agents, do all the setup yourself, I don't want to edit files by hand — plus the vault path and the list of agents (in the demo: Claude Code, Hermes, Codex, OpenClaw).
- The orchestrator then finds the agents, builds the folders, writes one rules note called the **protocol**, distributes instructions to each agent, tests everyone, and reports back. If a vault already exists, it audits what is already synced and fits the new system around it.
- Every agent ends up with two artifacts:
  1. A short **pointer** so it reads the vault at the start of every session.
  2. A **nightly task** so it writes its summary unprompted.
- All rules live in the single protocol note: change that note and all four agents change behavior.

### 5. Voice and mobile access (5:50 – 6:25)

- The host asks Hermes out loud: "Can you look at my vault and give me some ideas of what we worked on?" Hermes answers from the notes and reports that video title ideas were being produced in Claude — a different agent's work, retrieved by voice.
- Hermes also runs on Instagram, so the same question can be asked from a phone (example: "What did my agents get done on the AI Profit Boardroom yesterday?").

### 6. The mistake that makes agents slower (6:25 – 7:05)

- Do not save every chat and every message into the vault.
- Models read in tokens and each agent has a fixed context budget. Filling that budget with junk pushes the useful material out and degrades answers.
- Community members ask how to store millions of memories; the host says that is unnecessary. Karpathy's wiki on a single topic was about 100 articles and that was sufficient because the agent kept it organized and linked.

### 7. Anatomy of a nightly note (7:05 – 7:55)

One summary per agent per day, readable in under a minute, with four fields:

1. What it worked on
2. What it learned
3. Decisions it made
4. What is still in progress

Example note: "Worked on three subject lines for the AI Profit Boardroom welcome email. Learned that the shortest one was the clearest — pick that one. Still in progress: the day three follow-up."

The **learned** line is described as the most important line, because it is the transfer mechanism: Hermes learns something internally on Monday, writes it into the vault, and Claude Code, Codex, and OpenClaw can apply it on Tuesday without being told.

### 8. Three follow-on prompts (7:55 – 8:50)

- **Morning brief** — "Read yesterday's logs. Send me five bullets covering what's done, what's stuck, and my top three focus items."
- **Check before you start** — "Check the last 3 days of memories for anything about this project, then carry on." Prevents repeating experiments another agent already ran (example: Claude Code checking what Hermes tried before updating a landing page).
- **Health check** — "List each agent's nightly task, when it last ran, and fix any that failed." Recommended once a week, because nightly tasks sometimes fail silently.

### 9. Offer and closing (3:20 – 4:10, 8:50 – 9:19)

The middle and end of the video promote the paid **AI Profit Boardroom**, which includes the agent OS zip (Hermes, memory galaxy, voice agent, "create" section), a 30-day roadmap (day 1 install and connect Hermes; day 2 set up the vault folders; day 3 paste the setup prompt and enable nightly logs for every agent), four weekly coaching calls, a prompt library with the morning brief and health check, and a member map. A free community, the **AI Success Lab**, is also mentioned.

---

## Key insights

1. **Centralize rules, not context.** One protocol note controls every agent's behavior; per-agent prompt edits are the failure mode.
2. **Shared memory is a file-system contract.** Plain-text notes in a local folder work across vendors because every agent can read and write files — no API or plugin lock-in required.
3. **Summaries beat archives.** A four-field daily note that fits in a minute of reading outperforms dumping raw chat logs, because context windows are finite and dilution hurts answer quality.
4. **The "learned" field is the actual product.** It converts private, per-agent learning into shared institutional memory.
5. **Write path needs a scheduler.** Nightly tasks are the mechanism that makes memory accumulate without operator discipline — and they need a weekly health check because they fail silently.
6. **Orchestrated setup beats manual setup.** Delegating installation to one file-capable agent (Claude Code or Codex) makes the system reproducible and self-documenting.

## Caveats

- The video is promotional: the technical pattern is described fully enough to reproduce, but the packaged zip, roadmap, and support sit behind a paid membership.
- Unverified claims from the transcript, repeated here as claims and not facts: Nous Research release date (February 2026), the ~2,200-character memory limit, the Karpathy April 2026 post and quote, the ~800-upvote Reddit thread, and Karpathy's wiki being ~100 articles.
- "Codeex"/"Codecs"/"Clawed code" are auto-caption corruptions of Codex and Claude Code.

---

## Concepts and terminology

- **Hermes** — free, open-source, locally running AI agent attributed to Nous Research.
- **Obsidian** — free note-taking app storing plain Markdown/text files in a local vault folder.
- **Vault** — the folder Obsidian opens; here it doubles as the agents' shared memory store.
- **PARA** — Projects, Areas, Resources, Archive; a folder taxonomy for organizing knowledge by actionability.
- **Orchestrator** — the single agent (Claude Code or Codex in this setup) responsible for building and maintaining the memory system.
- **Protocol note** — the one rules file that defines how every agent reads and writes the vault.
- **Pointer** — a short instruction in each agent's config telling it to read the vault at session start.
- **Nightly task** — a scheduled job that makes an agent write its daily summary without being asked.
- **Token / context window** — the unit and the budget of text a model can process; the reason bulk log storage backfires.
- **Memory galaxy** — the host's visual for a densely cross-linked Obsidian graph of agent notes.

## Resources mentioned

- Obsidian (free note app) — obsidian.md
- Hermes agent (Nous Research)
- Claude Code, Codex, OpenClaw — the other agents in the shared-memory setup
- Andrej Karpathy's "LLM wiki" note (cited, April 2026)
- AI Profit Boardroom — aiprofitboardroom.com (paid; agent OS zip, 30-day roadmap, coaching calls, prompt library)
- AI Success Lab — free community

## Conclusion

The video's real content is a reproducible architecture, not a product demo: put shared memory in a plain-text vault, let one capable agent generate the wiring from a single prompt, keep all rules in one protocol file, and have each agent write a four-field summary every night. The constraints that make it work are the same ones that make it easy to get wrong — keep the vault small and curated, and never let agents write their decisions only into their own private memory.

---

## Raw transcript

Hermes Obsidian is wild. Every night, each of your AI agents writes a short note about its day, what it worked on, what it finished, and what it learned. The next morning, any agent can read that note and pick up right where the others stopped. Hermes, Claude Code, Codeex, and OpenClaw all read from one shared memory. You set the whole thing up with one prompt, and you never edit a file yourself. I'll show you the exact setup inside our agent OS. I'll also show you one mistake that makes agents slower. And stick around for the part where my voice agent reads my notes back to me out loud.

So, here's the problem. Hermes agent is the free open-source agent from Noose Research. It came out in February 2026, and it runs on your own computer. It has memory, but the built-in memory is tiny on purpose. One file holds about 2200 characters, which is about one page in a kids book. The file about you holds even less. Plus, Hermes only remembers for Hermes. Claude Code, Codeex, and OpenClaw each have their own separate memory. It's like four helpers in your office who never talk to each other. Every morning, each one starts with no idea what the others did yesterday.

This is the memory galaxy inside our agent OS. Every dot is a note and every line is a link between two notes. There are thousands of memories in here. Click on Goldie Agency and you'll see who Julian is and what the agency does, all linked together. Julian doesn't sort any of it. The agents keep it up to date.

Obsidian is a free notes app. Your notes are plain text files in a folder on your own computer. Your agents can open and write them like any other file. Andre Karpathy, one of the people who started OpenAI, shared a setup like this in April 2026. An AI agent keeps a folder of notes neat and linked, and he uses Obsidian to look at it. His line was, "Obsidian is the IDE, the LLM is the programmer, the wiki is the codebase." In plain words, Obsidian is the window, the AI does the writing, and the notes are what gets built. Hermes users found this, too. A Reddit post about using obsidian as long-term memory for Hermes got close to 800 up votes. Hermes even comes with an obsidian skill built in.

So, how do you keep it from turning into a mess? You use folders. The folder system is called para projects, areas, resources, and archive. Projects have an end date like launch the new AI profit boardroom welcome email. Areas never end, like the community or SEO. Resources are things you look up, like your brand voice. Archive is where finish stuff goes.

Quick pause before I show you the next part. If you want it, you can get the agent OS inside the AI profit boardroom. You get the full zip file ready to install with Hermes, the memory galaxy, the voice agent, and the create section already set up. We've also built a 30-day agent OS road map. Day one, you install the agent OS and connect Hermes. Day two, you set up your Obsidian Vault with the right folders. Day three, you paste in the setup prompt and turn on nightly logs for every agent. There are four coaching calls every week where you can share your screen and get help live. A lot of members already run this exact stack. link in the description or go to aiprofitboardroom.com.

On top of that, we add four more folders. An inbox for messy notes, a daily folder for your own notes, a memories folder for decisions and wins, and an agent OS folder that belongs to the agents. That last folder is how everything syncs. Claude, Hermes, and the voice agent all write into the same vault.

Now, there's one choice that makes or breaks this, and most people get it wrong. They set up each agent by hand, one at a time. Please don't do that. Instead, pick one agent to be the boss. We call it the orchestrator. Clawed code or codecs work best because both can read and write files all over your computer. Then you give the boss one big prompt. Set up a shared Obsidian memory for all my agents. Do all the setup yourself. I don't want to edit these files by hand. Add your vault path and list your agents. For Julian, that's Claude Code, Hermes, Codeex, and OpenClaw. The boss finds your agents, builds the folders, and writes one rules note called the protocol. It gives each agent its instructions, tests everyone, and reports back. Already have a vault? It checks what's synced and fits the new system around what you have. When it's done, every agent gets two things. The first is a short pointer, so it reads the vault at the start of every session. The second is a nightly task, so it writes its summary without you asking. All the rules live in that one protocol note. If you change the note, all four agents change.

Now, the voice agent, Julian asks Hermes out loud, "Can you look at my vault and give me some ideas of what we worked on?" Hermes answers from his notes. It tells him he'd been making video title ideas in Claude. He did that work in Claude. Then he asked a totally different agent by voice and Hermes knew. Hermes also runs Instagram so you can ask from your phone. What did my agents get done on the AI profit boardroom yesterday?

Now the mistake. You might think, why not save every chat and every message? It backfires. AI reads text in small chunks called tokens, and each agent only has so much room. If you fill that room with junk, the useful stuff gets pushed out and answers get worse. People in our community have asked how to put millions of memories into Obsidian. Honestly, you don't need that. Karpathy's wiki on one topic was about 100 articles. That was plenty because the agent kept it neat and linked.

So, what does the nightly note look like? Each agent writes one summary for its whole day. So, any agent can read it in under a minute. It has four parts. What it worked on, what it learned, decisions it made, and what's still in progress. Here's what one could look like. Hermes writes, "Worked on three subject lines for the AI profit boardroom welcome email. Learned that the shortest one was the clearest. Pick that one. Still in progress. the day three follow-up." That learned line is the most important line in the note. Hermes already learns from what it does, but that learning stays inside Hermes. Once Hermes writes it into the vault, Claude Code, Codeex, and Open Claw all learn it, too. So, if Hermes learns something on Monday, Claude Code uses it on Tuesday. Nobody had to tell it.

Once the logs are running, you can add a few extra prompts. Pick the ones that fit. The first is the morning brief. Read yesterday's logs. Send me five bullets covering what's done, what's stuck, and my top three focus items. You wake up knowing where your AI profit boardroom projects stand. The second is check before you start. Check the last 3 days of memories for anything about this project, then carry on. So before Claude code updates the AI profit boardroom landing page, it checks what Hermes already tried. The third is the health check. List each agent's nightly task, when it last ran, and fix any that failed. Nightly tasks fail sometimes, so run this once a week.

There's a window right now where most business owners haven't figured this out. They're still pasting the same background info into every agent every day. That window won't stay open forever. If you want the exact system from this video, get the agent OS inside the AI profit boardroom. It's the full zip file ready to install. You get the memory galaxy, the voice agent, the create section, and the setup prompt with the full Obsidian daily log guide. There are daily tutorials on using Hermes and the agent OS to save time and get more leads. There are four coaching calls every week where you can bring your vault and get help live. You get a prompt library with the morning brief and the health check. And there's a member map so you can find people near you running Hermes and Obsidian 2. Link in the description or go to a profitboardroom.com. And if you want the full process, the SOPs and over 100 AI use cases like this one, join the AI success lab. It's our free community links in the comments and description.
