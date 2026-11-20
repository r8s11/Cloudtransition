// `orca plugin test .` runs this in Node with the same runtime and checks Orca uses.
import { assert, mockHost, mount, test } from "orca/testing";
import * as panel from "./panel";
import type { TimerView } from "./protocol";
import { DEFAULTS, initial, start } from "./timer";

const idle: TimerView = { state: initial(DEFAULTS, Date.now()), longEvery: 4 };

test("shows the idle timer and starts it", async () => {
	const running: TimerView = { ...idle, state: start(idle.state, Date.now()) };
	const host = mockHost({
		requests: { "pomo.get": () => idle, "pomo.start": () => running },
	});
	const view = await mount(panel, { host });
	assert.ok(view.find({ text: "25:00" }));
	assert.ok(view.find({ text: "Ready" }));
	await view.press({ text: "Start" });
	assert.ok(view.find({ text: "Running" }));
	assert.ok(view.find({ text: "Pause" }));
	assert.equal(view.find({ text: "Start" }), null);
	assert.deepEqual(view.errors, []);
	assert.deepEqual(view.warnings, []);
	await view.unmount();
});

test("follows what the worker posts", async () => {
	const host = mockHost({ requests: { "pomo.get": () => idle } });
	const view = await mount(panel, { host });
	await view.post("pomo.changed", {
		longEvery: 4,
		state: {
			...idle.state,
			phase: "long",
			cycle: 4,
			doneToday: 4,
			remainingMs: 15 * 60_000,
		},
	});
	assert.ok(view.find({ text: "Long break" }));
	assert.ok(view.find({ text: "15:00" }));
	await view.unmount();
});

test("a failed request shows an error instead of a blank panel", async () => {
	const host = mockHost({
		requests: {
			"pomo.get": () => {
				throw new Error("worker crashed");
			},
		},
	});
	const view = await mount(panel, { host });
	assert.deepEqual(view.summary(), ['Callout danger "Timer unavailable"']);
	await view.unmount();
});
