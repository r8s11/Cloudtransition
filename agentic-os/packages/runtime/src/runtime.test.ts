import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  mkdirSync,
  mkdtempSync,
  realpathSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import {
  Database,
  SqliteMissionRepository,
  SqlitePlanRepository,
} from "@agentic-os/storage";
import { createMission } from "@agentic-os/core";
import { AgentRuntime, CommandAgentAdapter, claudeUsage } from "./index.js";

// Real subprocesses are intentional: fake timers cannot exercise OS signal delivery
// or the grace-period escalation. Poll observed state, never guess a sleep duration.
describe("local agent supervision", () => {
  let directory: string;
  let db: Database;
  let runtime: AgentRuntime;
  beforeEach(() => {
    directory = realpathSync(mkdtempSync(join(tmpdir(), "agent-runtime-")));
    execFileSync("git", ["init", "--quiet", directory]);
    db = Database.open(join(directory, "runtime.db"));
  });
  afterEach(async () => {
    if (runtime) await runtime.shutdown();
    db.close();
    rmSync(directory, { recursive: true, force: true });
  });
  function create(script: string) {
    runtime = new AgentRuntime(db, [
      new CommandAgentAdapter("node", process.execPath, () => ["-e", script]),
    ]);
    return runtime;
  }
  async function start() {
    const project = await runtime.registerProject(directory);
    return runtime.start({
      projectId: project.id,
      adapterId: "node",
      prompt: "test",
    });
  }
  it("canonicalizes symlink registrations and rejects non-repositories", async () => {
    create("");
    const project = await runtime.registerProject(directory);
    symlinkSync(directory, join(directory, "alias"));
    expect((await runtime.registerProject(join(directory, "alias"))).id).toBe(
      project.id,
    );
    await expect(runtime.registerProject(tmpdir())).rejects.toMatchObject({
      status: 400,
    });
  });
  it("drains both output streams before persisting a nonzero exit across reopen", async () => {
    create(
      "process.stdout.write(process.cwd()); process.stderr.write('diagnostic'); process.exitCode=7",
    );
    const run = await start();
    await expect.poll(() => runtime.getRun(run.id)?.status).toBe("failed");
    expect(
      runtime
        .events(run.id)
        .filter((e) => e.kind === "stdout")
        .map((e) => e.data)
        .join(""),
    ).toBe(directory);
    expect(
      runtime
        .events(run.id)
        .filter((e) => e.kind === "stderr")
        .map((e) => e.data)
        .join(""),
    ).toBe("diagnostic");
    await runtime.shutdown();
    db.close();
    db = Database.open(join(directory, "runtime.db"));
    create("");
    expect(runtime.getRun(run.id)).toMatchObject({
      status: "failed",
      exitCode: 7,
    });
    expect(runtime.listRuns({ active: true })).toEqual([]);
  });
  it("persists spawn failures rather than leaving starting runs", async () => {
    runtime = new AgentRuntime(db, [
      new CommandAgentAdapter("node", join(directory, "missing"), () => []),
    ]);
    const run = await start();
    expect(run.status).toBe("failed");
    expect(runtime.getRun(run.id)?.error).toContain("ENOENT");
  });
  it("interrupts a running process without reporting completion", async () => {
    create(
      "process.on('SIGINT',()=>process.exit(0)); console.log('ready'); setInterval(()=>{},1000)",
    );
    const run = await start();
    await expect
      .poll(() => runtime.events(run.id).some((e) => e.data.includes("ready")))
      .toBe(true);
    await runtime.interrupt(run.id);
    await expect.poll(() => runtime.getRun(run.id)?.status).toBe("interrupted");
  });
  it("escalates termination for an agent ignoring SIGTERM", async () => {
    create(
      "process.on('SIGTERM',()=>{}); console.log('ready'); setInterval(()=>{},1000)",
    );
    const run = await start();
    await expect
      .poll(() => runtime.events(run.id).some((e) => e.data.includes("ready")))
      .toBe(true);
    await runtime.terminate(run.id);
    await expect
      .poll(() => runtime.getRun(run.id)?.status, { timeout: 6000 })
      .toBe("terminated");
    expect(runtime.getRun(run.id)?.signal).toBe("SIGKILL");
  }, 10000);
  it("rejects a second supervisor and releases ownership on shutdown", async () => {
    create("");
    expect(() => new AgentRuntime(db)).toThrow(/supervis/i);
    await runtime.shutdown();
    create("");
    const run = await start();
    await expect.poll(() => runtime.getRun(run.id)?.status).toBe("completed");
  });
  it("marks stale runs lost without signalling the stored PID", async () => {
    create("console.log('ready'); setInterval(()=>{},1000)");
    const run = await start();
    await runtime.terminate(run.id);
    await expect.poll(() => runtime.getRun(run.id)?.status).toBe("terminated");
    await runtime.shutdown();
    db.prepare(
      "UPDATE agent_runs SET status = 'running', owner_id = 'old', pid = ? WHERE id = ?",
    ).run(process.pid, run.id);
    create("");
    expect(runtime.getRun(run.id)).toMatchObject({
      status: "lost",
      pid: process.pid,
    });
  });
  it("rejects invalid task linkage before executing an agent", async () => {
    create("");
    const project = await runtime.registerProject(directory);
    await expect(
      runtime.start({
        projectId: project.id,
        adapterId: "node",
        prompt: "test",
        taskId: "unknown",
      }),
    ).rejects.toMatchObject({ status: 400 });
    expect(runtime.listRuns()).toEqual([]);
  });
  it("cleans inherited-pipe descendants when the agent leader exits", async () => {
    create(`
      const {spawn}=require('node:child_process');
      const helper=spawn(process.execPath,['-e',"process.send('ready');setInterval(()=>{},1000)"],{stdio:['ignore','inherit','inherit','ipc']});
      helper.on('message',()=>{console.log(helper.pid);process.exit(0)});
    `);
    const run = await start();
    await expect.poll(() => runtime.getRun(run.id)?.status).toBe("completed");
    const pid = Number(
      runtime
        .events(run.id)
        .filter((e) => e.kind === "stdout")
        .map((e) => e.data)
        .join("")
        .trim(),
    );
    expect(pid).toBeGreaterThan(1);
    await expect
      .poll(() => {
        try {
          process.kill(pid, 0);
          return false;
        } catch (error) {
          return (
            error instanceof Error && "code" in error && error.code === "ESRCH"
          );
        }
      })
      .toBe(true);
  });
  it("pins a Core plan version without automatically advancing its mission", async () => {
    create("");
    const missions = new SqliteMissionRepository(db);
    const plans = new SqlitePlanRepository(db);
    await missions.create(
      createMission(
        {
          id: "mission",
          title: "Existing mission",
          priority: "low",
          acceptanceCriteria: ["verified"],
        },
        () => new Date(),
      ),
    );
    await plans.save("mission", {
      missionId: "mission",
      tasks: [
        {
          id: "task",
          title: "Existing task",
          steps: [],
          expectedResult: "verified",
          verificationCriteria: ["verified"],
        },
      ],
    });
    const project = await runtime.registerProject(directory);
    const run = await runtime.start({
      projectId: project.id,
      adapterId: "node",
      prompt: "test",
      missionId: "mission",
      planVersion: 1,
      taskId: "task",
    });
    await plans.save("mission", {
      missionId: "mission",
      tasks: [
        {
          id: "replacement",
          title: "Revised task",
          steps: [],
          expectedResult: "verified",
          verificationCriteria: ["verified"],
        },
      ],
    });
    await expect.poll(() => runtime.getRun(run.id)?.status).toBe("completed");
    expect(runtime.getRun(run.id)).toMatchObject({
      missionId: "mission",
      planVersion: 1,
      taskId: "task",
    });
    expect((await missions.getById("mission"))?.status).toBe("queued");
    await expect(
      runtime.start({
        projectId: project.id,
        adapterId: "node",
        prompt: "test",
        missionId: "mission",
        planVersion: 2,
        taskId: "task",
      }),
    ).rejects.toMatchObject({ status: 400 });
  });
  function metered(script: string) {
    runtime = new AgentRuntime(db, [
      new CommandAgentAdapter(
        "node",
        process.execPath,
        (_prompt, options) => [
          "-e",
          script,
          options.model ?? "default-model",
          options.effort ?? "default-effort",
        ],
        { models: ["small", "large"], efforts: ["low"], usage: claudeUsage },
      ),
    ]);
    return runtime;
  }
  function stdout(id: string) {
    return runtime
      .events(id)
      .filter((e) => e.kind === "stdout")
      .map((e) => e.data)
      .join("");
  }
  it("records usage from the agent report and stores the answer as output", async () => {
    metered(
      `const report={type:"result",result:"answer "+process.argv[1]+" "+process.argv[2],total_cost_usd:0.25,usage:{input_tokens:10,cache_creation_input_tokens:20,cache_read_input_tokens:30,output_tokens:7}};const text=JSON.stringify(report);process.stdout.write(text.slice(0,20));setTimeout(()=>process.stdout.write(text.slice(20)),20)`,
    );
    const project = await runtime.registerProject(directory);
    const run = await runtime.start({
      projectId: project.id,
      adapterId: "node",
      prompt: "/tidy",
      model: "small",
      effort: "low",
    });
    await expect.poll(() => runtime.getRun(run.id)?.status).toBe("completed");
    expect(runtime.getRun(run.id)).toMatchObject({
      model: "small",
      effort: "low",
      inputTokens: 60,
      outputTokens: 7,
      costUsd: 0.25,
    });
    expect(stdout(run.id)).toBe("answer small low");
    expect(runtime.usage(7)).toEqual([
      expect.objectContaining({
        prompt: "/tidy",
        runs: 1,
        meteredRuns: 1,
        inputTokens: 60,
        outputTokens: 7,
        costUsd: 0.25,
      }),
    ]);
    expect(await runtime.detectAdapters()).toEqual([
      { id: "node", available: true, models: ["small", "large"], efforts: ["low"] },
    ]);
  });
  it("keeps output that is not a usage report and leaves usage empty", async () => {
    metered("process.stdout.write('plain text, not a report'); process.exitCode=3");
    const run = await start();
    await expect.poll(() => runtime.getRun(run.id)?.status).toBe("failed");
    expect(stdout(run.id)).toBe("plain text, not a report");
    expect(runtime.getRun(run.id)).toMatchObject({
      model: null,
      inputTokens: null,
      outputTokens: null,
      costUsd: null,
    });
    expect(runtime.usage(7)).toEqual([
      expect.objectContaining({ runs: 1, meteredRuns: 0, costUsd: 0 }),
    ]);
  });
  it("rejects a model or effort the adapter does not offer before creating a run", async () => {
    metered("");
    const project = await runtime.registerProject(directory);
    for (const option of [{ model: "--dangerously-skip-permissions" }, { effort: "max" }])
      await expect(
        runtime.start({ projectId: project.id, adapterId: "node", prompt: "x", ...option }),
      ).rejects.toMatchObject({ status: 400 });
    expect(runtime.listRuns()).toEqual([]);
  });
  it("lists only real skill folders of a registered repository", async () => {
    create("");
    const project = await runtime.registerProject(directory);
    expect(await runtime.listSkills(project.id)).toEqual([]);
    const skills = join(directory, ".claude", "skills");
    mkdirSync(join(skills, "clean-up"), { recursive: true });
    writeFileSync(
      join(skills, "clean-up", "SKILL.md"),
      '---\nname: clean-up\ndescription: "Tidy the downloads folder"\n---\nSteps\n',
    );
    mkdirSync(join(skills, "no-skill-file"));
    mkdirSync(join(skills, "bad name"));
    writeFileSync(join(skills, "bad name", "SKILL.md"), "description: hidden\n");
    expect(await runtime.listSkills(project.id)).toEqual([
      { name: "clean-up", description: "Tidy the downloads folder" },
    ]);
    await expect(runtime.listSkills("missing")).rejects.toMatchObject({ status: 404 });
  });
  it("reads only a well-formed claude result report", () => {
    expect(claudeUsage("not json")).toBeNull();
    expect(claudeUsage('{"type":"other","result":"x"}')).toBeNull();
    expect(claudeUsage('{"type":"result","result":"x","is_error":true}')).toEqual({
      result: "x",
      inputTokens: null,
      outputTokens: null,
      costUsd: null,
    });
  });
});
