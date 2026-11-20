import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { chmodSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { Database } from "@agentic-os/storage";
import { AgentRuntime, CommandAgentAdapter, opencodeAdapter } from "./index.js";

// Hub seams: named-agent launch option and the run-completion subscription.
describe("hub runtime seams", () => {
  let directory: string;
  let db: Database;
  let runtime: AgentRuntime;
  beforeEach(() => {
    directory = realpathSync(mkdtempSync(join(tmpdir(), "hub-seams-")));
    execFileSync("git", ["init", "--quiet", directory]);
    db = Database.open(join(directory, "runtime.db"));
  });
  afterEach(async () => {
    if (runtime) await runtime.shutdown();
    db.close();
    rmSync(directory, { recursive: true, force: true });
  });

  it("notifies subscribers once per run after the terminal state is persisted", async () => {
    runtime = new AgentRuntime(db, [
      new CommandAgentAdapter("node", process.execPath, () => ["-e", "process.exit(0)"]),
    ]);
    const seen: string[] = [];
    const unsubscribe = runtime.subscribe((run) => seen.push(`${run.id}:${run.status}`));
    const project = await runtime.registerProject(directory);
    const run = await runtime.start({ projectId: project.id, adapterId: "node", prompt: "t" });
    await expect.poll(() => seen.length).toBe(1);
    expect(seen[0]).toBe(`${run.id}:completed`);
    expect(runtime.getRun(run.id)?.status).toBe("completed");
    unsubscribe();
    const second = await runtime.start({ projectId: project.id, adapterId: "node", prompt: "t" });
    await expect.poll(() => runtime.getRun(second.id)?.status).toBe("completed");
    expect(seen.length).toBe(1);
  });

  it("rejects an agent the adapter does not offer", async () => {
    runtime = new AgentRuntime(db, [
      new CommandAgentAdapter("node", process.execPath, () => ["-e", ""], { agents: ["forge"] }),
    ]);
    const project = await runtime.registerProject(directory);
    await expect(
      runtime.start({ projectId: project.id, adapterId: "node", prompt: "t", agent: "scout" }),
    ).rejects.toMatchObject({ status: 400 });
  });

  it("opencodeAdapter passes only configured agent and model flags", async () => {
    const script = join(directory, "echo-args.sh");
    writeFileSync(script, '#!/bin/sh\necho "$@"\n');
    chmodSync(script, 0o755);
    runtime = new AgentRuntime(db, [
      opencodeAdapter({ executable: script, models: ["opencode/beam-free"], agents: ["job-reader"] }),
    ]);
    const project = await runtime.registerProject(directory);
    const run = await runtime.start({
      projectId: project.id,
      adapterId: "opencode",
      prompt: "read the posting",
      agent: "job-reader",
      model: "opencode/beam-free",
    });
    await expect.poll(() => runtime.getRun(run.id)?.status).toBe("completed");
    const stdout = runtime
      .events(run.id)
      .filter((e) => e.kind === "stdout")
      .map((e) => e.data)
      .join("");
    expect(stdout.trim()).toBe("run --agent job-reader --model opencode/beam-free -- read the posting");
    await expect(
      runtime.start({ projectId: project.id, adapterId: "opencode", prompt: "t", agent: "scout" }),
    ).rejects.toMatchObject({ status: 400 });
  });
});
