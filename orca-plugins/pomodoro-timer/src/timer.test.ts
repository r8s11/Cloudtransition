import { assert, test } from "orca/testing";
import {
	advance,
	clock,
	DEFAULTS,
	initial,
	parse,
	pause,
	reconcile,
	reset,
	start,
} from "./timer";

const T0 = new Date(2026, 10, 4, 9, 0, 0).getTime();
const MIN = 60_000;

test("pause keeps the time left and resume continues from it", () => {
	const running = start(initial(DEFAULTS, T0), T0);
	const paused = pause(running, T0 + 10 * MIN);
	assert.equal(paused.status, "paused");
	assert.equal(paused.remainingMs, 15 * MIN);
	const resumed = start(paused, T0 + 60 * MIN);
	assert.equal(resumed.endsAt, T0 + 75 * MIN);
});

test("every fourth finished focus session earns a long break, which resets the cycle", () => {
	let s = initial(DEFAULTS, T0);
	const phases: string[] = [];
	for (let i = 0; i < 8; i += 1) {
		s = advance(s, DEFAULTS, T0, true);
		phases.push(s.phase);
	}
	assert.deepEqual(phases, [
		"short",
		"focus",
		"short",
		"focus",
		"short",
		"focus",
		"long",
		"focus",
	]);
	assert.equal(s.cycle, 0);
	assert.equal(s.doneToday, 4);
});

test("skipping a focus session goes to a break without counting it", () => {
	const s = advance(initial(DEFAULTS, T0), DEFAULTS, T0, false);
	assert.equal(s.phase, "short");
	assert.equal(s.cycle, 0);
	assert.equal(s.doneToday, 0);
});

test("the daily count starts over on a new local day", () => {
	const yesterday = { ...initial(DEFAULTS, T0), doneToday: 6 };
	const s = advance(yesterday, DEFAULTS, T0 + 24 * 60 * MIN, true);
	assert.equal(s.doneToday, 1);
});

test("reconcile finishes an overdue phase and only that one", () => {
	const running = start(initial(DEFAULTS, T0), T0);
	assert.equal(reconcile(running, DEFAULTS, T0 + 24 * MIN).finished, null);
	const { state, finished } = reconcile(running, DEFAULTS, T0 + 26 * MIN);
	assert.equal(finished, "focus");
	assert.equal(state.phase, "short");
	assert.equal(state.status, "idle");
	const auto = reconcile(running, DEFAULTS, T0 + 26 * MIN, true).state;
	assert.equal(auto.status, "running");
	assert.equal(auto.endsAt, T0 + 31 * MIN);
});

test("reset returns to the full length of the current phase", () => {
	const paused = pause(start(initial(DEFAULTS, T0), T0), T0 + 3 * MIN);
	const s = reset(paused, { ...DEFAULTS, focus: 50 });
	assert.equal(s.status, "idle");
	assert.equal(s.remainingMs, 50 * MIN);
});

test("parse refuses damaged storage", () => {
	assert.equal(parse(null), null);
	assert.equal(parse({ phase: "nap", status: "idle" }), null);
	assert.equal(
		parse({ ...initial(DEFAULTS, T0), status: "running", endsAt: null }),
		null,
	);
	assert.deepEqual(parse(initial(DEFAULTS, T0)), initial(DEFAULTS, T0));
});

test("clock rounds up to whole seconds", () => {
	assert.equal(clock(25 * MIN), "25:00");
	assert.equal(clock(59_001), "1:00");
	assert.equal(clock(0), "0:00");
});
