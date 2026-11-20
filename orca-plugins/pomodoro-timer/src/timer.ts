// Pure Pomodoro state machine. No clock, no host: every function takes `now` (ms), so the
// worker owns time and tests pass fixed instants.

export type Phase = "focus" | "short" | "long";
export type Status = "idle" | "running" | "paused";

/** Lengths in minutes, and how many focus sessions earn a long break. */
export interface Durations {
	focus: number;
	short: number;
	long: number;
	longEvery: number;
}

export interface TimerState {
	phase: Phase;
	status: Status;
	/** When the running phase ends; null unless running. */
	endsAt: number | null;
	/** Time left while idle or paused. */
	remainingMs: number;
	/** Focus sessions finished since the last long break. */
	cycle: number;
	/** Local date (YYYY-MM-DD) that `doneToday` counts. */
	day: string;
	doneToday: number;
}

export const DEFAULTS: Durations = {
	focus: 25,
	short: 5,
	long: 15,
	longEvery: 4,
};

export const PHASE_LABEL: Record<Phase, string> = {
	focus: "Focus",
	short: "Short break",
	long: "Long break",
};

export function dayKey(now: number): string {
	const d = new Date(now);
	return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function phaseMs(phase: Phase, d: Durations): number {
	return Math.round(d[phase] * 60_000);
}

export function initial(d: Durations, now: number): TimerState {
	return {
		phase: "focus",
		status: "idle",
		endsAt: null,
		remainingMs: phaseMs("focus", d),
		cycle: 0,
		day: dayKey(now),
		doneToday: 0,
	};
}

/** A stored value back to a state, or null when it is missing or the wrong shape. */
export function parse(value: unknown): TimerState | null {
	if (!value || typeof value !== "object") return null;
	const s = value as Partial<TimerState>;
	const phases: Phase[] = ["focus", "short", "long"];
	const statuses: Status[] = ["idle", "running", "paused"];
	if (
		!phases.includes(s.phase as Phase) ||
		!statuses.includes(s.status as Status)
	)
		return null;
	if (typeof s.remainingMs !== "number" || typeof s.cycle !== "number")
		return null;
	if (typeof s.day !== "string" || typeof s.doneToday !== "number") return null;
	if (s.status === "running" && typeof s.endsAt !== "number") return null;
	return {
		...(s as TimerState),
		endsAt: s.status === "running" ? (s.endsAt as number) : null,
	};
}

/** Zeroes the daily count once the local date has moved on. */
export function rollDay(s: TimerState, now: number): TimerState {
	const today = dayKey(now);
	return s.day === today ? s : { ...s, day: today, doneToday: 0 };
}

export function start(s: TimerState, now: number): TimerState {
	if (s.status === "running") return s;
	return { ...s, status: "running", endsAt: now + s.remainingMs };
}

export function pause(s: TimerState, now: number): TimerState {
	if (s.status !== "running" || s.endsAt === null) return s;
	return {
		...s,
		status: "paused",
		endsAt: null,
		remainingMs: Math.max(0, s.endsAt - now),
	};
}

/** Back to the start of the current phase, stopped. */
export function reset(s: TimerState, d: Durations): TimerState {
	return {
		...s,
		status: "idle",
		endsAt: null,
		remainingMs: phaseMs(s.phase, d),
	};
}

/**
 * Moves to the next phase. `completed` is true when the phase ran out, false when skipped:
 * only a completed focus session counts toward the long break and today's total.
 */
export function advance(
	s: TimerState,
	d: Durations,
	now: number,
	completed: boolean,
	autoStart = false,
): TimerState {
	const rolled = rollDay(s, now);
	let { cycle, doneToday } = rolled;
	let next: Phase;
	if (rolled.phase === "focus") {
		if (completed) {
			cycle += 1;
			doneToday += 1;
		}
		next = completed && cycle >= Math.max(1, d.longEvery) ? "long" : "short";
	} else {
		if (rolled.phase === "long") cycle = 0;
		next = "focus";
	}
	const stopped: TimerState = {
		...rolled,
		phase: next,
		status: "idle",
		endsAt: null,
		remainingMs: phaseMs(next, d),
		cycle,
		doneToday,
	};
	return autoStart ? start(stopped, now) : stopped;
}

/** Finishes a running phase whose end has passed; `finished` names it for the notification. */
export function reconcile(
	s: TimerState,
	d: Durations,
	now: number,
	autoStart = false,
): { state: TimerState; finished: Phase | null } {
	if (s.status === "running" && s.endsAt !== null && s.endsAt <= now) {
		return { state: advance(s, d, now, true, autoStart), finished: s.phase };
	}
	return { state: rollDay(s, now), finished: null };
}

/** "24:59" for a duration in ms, rounding up so a fresh 25-minute phase reads 25:00. */
export function clock(ms: number): string {
	const total = Math.max(0, Math.ceil(ms / 1000));
	const m = Math.floor(total / 60);
	const sec = total % 60;
	return `${m}:${String(sec).padStart(2, "0")}`;
}
