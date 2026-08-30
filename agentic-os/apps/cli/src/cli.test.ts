import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { main } from "./cli.js";
import { Database, SqliteMissionRepository, SqliteTransitionRepository } from "@agentic-os/storage";

let dir: string;
let configPath: string;
let dbPath: string;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "agent-os-cli-"));
  dbPath = join(dir, "os.db");
  configPath = join(dir, "agentic-os.yaml");
  writeFileSync(
    configPath,
    `database:\n  provider: sqlite\n  path: ${dbPath}\n\npolicy:\n  default: require_approval\n  capabilities:\n    filesystem.read:\n      decision: allow\n`,
  );
});

afterEach(() => {
  rmSync(dir, { recursive: true, force: true });
});

describe("CLI entrypoint (main)", () => {
  it("mission create → list → show → transition → illegal transition", async () => {
    const logSpy = vi.spyOn(console, "log").mockImplementation(() => {});

    // create
    const createCode = await main([
      "mission",
      "create",
      "--title",
      "Improve event search",
      "--objective",
      "Add searchable event filtering",
      "--acceptance",
      "Users can search events by title",
      "--acceptance",
      "Results paginate",
      "--priority",
      "high",
      "--config",
      configPath,
    ]);
    expect(createCode).toBe(0);
    const createdOut = logSpy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(createdOut).toContain("Created mission");

    // extract id from "Created mission <id>"
    const idMatch = createdOut.match(/Created mission ([\w-]+)/);
    expect(idMatch).not.toBeNull();
    const id = idMatch![1]!;

    // list
    logSpy.mockClear();
    const listCode = await main(["mission", "list", "--config", configPath]);
    expect(listCode).toBe(0);
    const listOut = logSpy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(listOut).toContain(id);
    expect(listOut).toContain("queued");

    // show
    logSpy.mockClear();
    const showCode = await main(["mission", "show", id, "--config", configPath]);
    expect(showCode).toBe(0);
    const showOut = logSpy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(showOut).toContain("Improve event search");
    expect(showOut).toContain("Users can search events by title");

    // transition running (legal)
    logSpy.mockClear();
    const trCode = await main([
      "mission",
      "transition",
      id,
      "running",
      "--reason",
      "Plan accepted",
      "--config",
      configPath,
    ]);
    expect(trCode).toBe(0);

    // verify persistence directly
    const db = Database.open(dbPath);
    const repo = new SqliteMissionRepository(db);
    const persisted = await repo.getById(id);
    expect(persisted!.status).toBe("running");
    const history = await new SqliteTransitionRepository(db).listForMission(id);
    expect(history).toHaveLength(1);
    expect(history[0]!.toStatus).toBe("running");
    db.close();

    // running → cancelled is legal; pick an illegal: running → draft.
    const errSpy2 = vi.spyOn(console, "error").mockImplementation(() => {});
    logSpy.mockClear();
    const illegalCode = await main([
      "mission",
      "transition",
      id,
      "draft",
      "--config",
      configPath,
    ]);
    expect(illegalCode).toBe(1);
    const illegalOut = errSpy2.mock.calls.map((c) => String(c[0])).join("\n");
    expect(illegalOut).toMatch(/cannot transition/);
    errSpy2.mockRestore();

    // status unchanged after illegal transition
    const db2 = Database.open(dbPath);
    const repo2 = new SqliteMissionRepository(db2);
    const after = await repo2.getById(id);
    expect(after!.status).toBe("running");
    db2.close();

    logSpy.mockRestore();
  });

  it("mission create requires --title (returns usage error)", async () => {
    const logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const code = await main(["mission", "create", "--config", configPath]);
    expect(code).toBe(2);
    logSpy.mockRestore();
    errSpy.mockRestore();
  });

  it("mission show on unknown id returns 1", async () => {
    const logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const code = await main([
      "mission",
      "show",
      "does-not-exist",
      "--config",
      configPath,
    ]);
    expect(code).toBe(1);
    logSpy.mockRestore();
    errSpy.mockRestore();
  });
});
