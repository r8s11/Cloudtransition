import { execFile, spawn, type ChildProcess } from "node:child_process";
import { promisify } from "node:util";

const exec = promisify(execFile);

export interface AgentStartOptions {
  cwd: string;
  prompt: string;
  /** Only values from the adapter's own `models` / `efforts` / `agents` lists reach here. */
  model?: string;
  effort?: string;
  agent?: string;
}

export interface AgentUsage {
  /** The agent's final answer, stored as the run's stdout in place of the raw report. */
  result: string;
  inputTokens: number | null;
  outputTokens: number | null;
  costUsd: number | null;
}

export interface AdapterCapabilities {
  /** Launch options a caller may choose. Absent or empty: the option is not offered. */
  models?: readonly string[];
  efforts?: readonly string[];
  /** Named agents this adapter can launch (OpenCode). Absent: not offered. */
  agents?: readonly string[];
  /** Parses the complete stdout of a finished run. Null: not a usage report, keep stdout as is. */
  usage?: (stdout: string) => AgentUsage | null;
}

/** Adapters return immediately after spawn, before any process events fire.
 * Each process must lead its own POSIX process group and expose piped output.
 * Controls receive a live handle, never an untrusted persisted PID.
 */
export interface AgentAdapter {
  readonly id: string;
  readonly models?: readonly string[];
  readonly efforts?: readonly string[];
  readonly agents?: readonly string[];
  usage?(stdout: string): AgentUsage | null;
  detect(): Promise<boolean>;
  start(options: AgentStartOptions): ChildProcess;
  interrupt(child: ChildProcess): void;
  terminate(child: ChildProcess, force?: boolean): void;
}

function signalGroup(child: ChildProcess, signal: NodeJS.Signals): void {
  if (!child.pid) return;
  try {
    process.kill(-child.pid, signal);
  } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ESRCH"))
      throw error;
  }
}

/** Trusted host configuration only; executable/arguments are never accepted over HTTP.
 * A caller can pick a model or effort only from the lists this configuration names. */
export class CommandAgentAdapter implements AgentAdapter {
  readonly models?: readonly string[];
  readonly efforts?: readonly string[];
  readonly agents?: readonly string[];
  readonly usage?: (stdout: string) => AgentUsage | null;

  constructor(
    readonly id: string,
    private readonly executable: string,
    private readonly args: (prompt: string, options: AgentStartOptions) => string[],
    capabilities: AdapterCapabilities = {},
  ) {
    this.models = capabilities.models;
    this.efforts = capabilities.efforts;
    this.agents = capabilities.agents;
    this.usage = capabilities.usage;
  }

  async detect(): Promise<boolean> {
    try {
      await exec(this.executable, ["--version"], {
        timeout: 5000,
        maxBuffer: 64 * 1024,
      });
      return true;
    } catch {
      return false;
    }
  }

  start(options: AgentStartOptions): ChildProcess {
    return spawn(this.executable, this.args(options.prompt, options), {
      cwd: options.cwd,
      detached: true,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    });
  }

  interrupt(child: ChildProcess): void {
    signalGroup(child, "SIGINT");
  }

  terminate(child: ChildProcess, force = false): void {
    signalGroup(child, force ? "SIGKILL" : "SIGTERM");
  }
}

export function defaultAdapters(): AgentAdapter[] {
  return [
    new CommandAgentAdapter("codex", "codex", (prompt) => [
      "exec",
      "--",
      prompt,
    ]),
    new CommandAgentAdapter(
      "claude",
      "claude",
      (prompt, options) => [
        "--print",
        "--output-format",
        "json",
        ...(options.model ? ["--model", options.model] : []),
        ...(options.effort ? ["--effort", options.effort] : []),
        "--",
        prompt,
      ],
      {
        models: ["haiku", "sonnet", "opus"],
        efforts: ["low", "medium", "high"],
        usage: claudeUsage,
      },
    ),
  ];
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? Math.round(value)
    : 0;
}

/** Reads the single JSON report `claude --print --output-format json` writes on exit.
 * Input tokens include cache writes and cache reads: all three are billed input. */
export function claudeUsage(stdout: string): AgentUsage | null {
  let report: unknown;
  try {
    report = JSON.parse(stdout);
  } catch {
    return null;
  }
  if (typeof report !== "object" || report === null || Array.isArray(report))
    return null;
  const { type, result, usage, total_cost_usd: cost } = report as Record<
    string,
    unknown
  >;
  if (type !== "result") return null;
  const tokens =
    typeof usage === "object" && usage !== null
      ? (usage as Record<string, unknown>)
      : null;
  return {
    result: typeof result === "string" ? result : "",
    inputTokens: tokens
      ? count(tokens.input_tokens) +
        count(tokens.cache_creation_input_tokens) +
        count(tokens.cache_read_input_tokens)
      : null,
    outputTokens: tokens ? count(tokens.output_tokens) : null,
    costUsd:
      typeof cost === "number" && Number.isFinite(cost) && cost >= 0
        ? cost
        : null,
  };
}

/** OpenCode runs one named agent from the trusted registry. Models and agents
 * come only from configuration; HTTP never supplies an executable or flag. */
export function opencodeAdapter(options: {
  executable?: string;
  models?: readonly string[];
  agents?: readonly string[];
} = {}): AgentAdapter {
  return new CommandAgentAdapter(
    "opencode",
    options.executable ?? "opencode",
    (prompt, o) => [
      "run",
      ...(o.agent ? ["--agent", o.agent] : []),
      ...(o.model ? ["--model", o.model] : []),
      "--",
      prompt,
    ],
    { models: options.models ?? [], agents: options.agents ?? [] },
  );
}
