// The timer's owner. State lives in orca.storage so a worker restart (a save, or Orca stopping
// an idle worker) loses nothing; on every start, request or command the worker first finishes
// any phase whose end passed while it was not running.
import type { OrcaWorkerApi } from "orca/worker";
import type { TimerView } from "./protocol";
import {
	advance,
	DEFAULTS,
	initial,
	parse,
	pause,
	PHASE_LABEL,
	reconcile,
	reset,
	start,
	type Durations,
	type TimerState,
} from "./timer";

const KEY = "timer";
const NEXT_LINE: Record<TimerState["phase"], string> = {
	focus: "Time to focus.",
	short: "Take a short break.",
	long: "Take a long break.",
};

let wake: ReturnType<typeof setTimeout> | undefined;

export default function activate(orca: OrcaWorkerApi): void {
	/** One change at a time, so a timer firing and a button press never interleave. */
	let queue: Promise<unknown> = Promise.resolve();

	async function readSettings(): Promise<{ d: Durations; autoStart: boolean }> {
		const s = await orca.settings.get();
		const minutes = (key: string, fallback: number, min: number) => {
			const v = s[key];
			return typeof v === "number" && Number.isFinite(v) && v >= min
				? v
				: fallback;
		};
		return {
			d: {
				focus: minutes("focusMinutes", DEFAULTS.focus, 1),
				short: minutes("shortBreakMinutes", DEFAULTS.short, 1),
				long: minutes("longBreakMinutes", DEFAULTS.long, 1),
				longEvery: Math.round(minutes("longBreakEvery", DEFAULTS.longEvery, 1)),
			},
			autoStart: s.autoStartNext === true,
		};
	}

	function mutate(
		change: (s: TimerState, d: Durations, now: number) => TimerState,
	): Promise<TimerView> {
		const run = queue.then(async () => {
			const { d, autoStart } = await readSettings();
			const now = Date.now();
			const loaded = parse(await orca.storage.get(KEY)) ?? initial(d, now);
			const { state: current, finished } = reconcile(loaded, d, now, autoStart);
			const next = change(current, d, now);
			await orca.storage.set(KEY, { ...next });
			clearTimeout(wake);
			if (next.status === "running" && next.endsAt !== null) {
				// A little past the end, so the check that runs sees it as over.
				wake = setTimeout(
					() => void mutate((s) => s),
					Math.max(0, next.endsAt - now) + 250,
				);
			}
			if (finished) {
				void orca.host
					.call("notifications.show", {
						title: `${PHASE_LABEL[finished]} done`,
						body:
							next.status === "running"
								? `${PHASE_LABEL[next.phase]} started.`
								: NEXT_LINE[next.phase],
					})
					.catch((error: unknown) =>
						orca.log(`notification failed: ${String(error)}`),
					);
			}
			const view: TimerView = { state: next, longEvery: d.longEvery };
			orca.panels.post("pomo.changed", view);
			return view;
		});
		queue = run.catch(() => undefined);
		return run;
	}

	orca.panels.handle("pomo.get", () => mutate((s) => s));
	orca.panels.handle("pomo.start", () => mutate((s, _d, now) => start(s, now)));
	orca.panels.handle("pomo.pause", () => mutate((s, _d, now) => pause(s, now)));
	orca.panels.handle("pomo.reset", () => mutate((s, d) => reset(s, d)));
	orca.panels.handle("pomo.skip", () =>
		mutate((s, d, now) => advance(s, d, now, false)),
	);

	orca.commands.register("pomodoro.toggle", async () => {
		const { state } = await mutate((s, _d, now) =>
			s.status === "running" ? pause(s, now) : start(s, now),
		);
		return state.status === "running"
			? `${PHASE_LABEL[state.phase]} running.`
			: `${PHASE_LABEL[state.phase]} paused.`;
	});
	orca.commands.register("pomodoro.skip", async () => {
		const { state } = await mutate((s, d, now) => advance(s, d, now, false));
		return `Skipped. Next: ${PHASE_LABEL[state.phase]}.`;
	});
	orca.commands.register("pomodoro.reset", async () => {
		const { state } = await mutate((s, d) => reset(s, d));
		return `${PHASE_LABEL[state.phase]} reset.`;
	});

	// New lengths apply at once to a timer that has not started.
	orca.settings.onDidChange(() => {
		void mutate((s, d) => (s.status === "idle" ? reset(s, d) : s));
	});

	// Re-arm the wake-up (or finish an overdue phase) whenever the worker starts.
	void mutate((s) => s);
}

export function deactivate(): void {
	clearTimeout(wake);
}
