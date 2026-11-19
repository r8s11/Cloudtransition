// Runs src/worker.ts's activate(orca) with the orca object Orca passes, over a mock host.
import { assert, mockHost, mountWorker, test } from "orca/testing";
import { initial, DEFAULTS } from "./timer";
import * as main from "./worker";

const CAPS = ["storage:own", "settings:own", "notifications:show"];
const COMMANDS = ["pomodoro.toggle", "pomodoro.skip", "pomodoro.reset"];

test("start, pause and resume through panel requests, telling open panels", async () => {
	const host = mockHost({ capabilities: CAPS });
	const worker = await mountWorker(main, { host, commands: COMMANDS });
	const started = await worker.request("pomo.start");
	assert.equal(started.state.status, "running");
	assert.ok(started.state.endsAt !== null && started.state.endsAt > Date.now());
	const paused = await worker.request("pomo.pause");
	assert.equal(paused.state.status, "paused");
	assert.ok(paused.state.remainingMs > 24 * 60_000);
	assert.equal(worker.posts.at(-1)?.event, "pomo.changed");
	assert.deepEqual(worker.refusals, []);
	await worker.deactivate();
});

test("a phase that ended while the worker was stopped finishes and notifies once", async () => {
	const overdue = {
		...initial(DEFAULTS, Date.now()),
		status: "running",
		endsAt: Date.now() - 1000,
	};
	const host = mockHost({ capabilities: CAPS, storage: { timer: overdue } });
	const worker = await mountWorker(main, { host, commands: COMMANDS });
	const view = await worker.request("pomo.get");
	assert.equal(view.state.phase, "short");
	assert.equal(view.state.status, "idle");
	assert.equal(view.state.doneToday, 1);
	const notes = host.callsOf("notifications.show");
	assert.equal(notes.length, 1);
	assert.deepEqual(notes[0], {
		title: "Focus done",
		body: "Take a short break.",
	});
	assert.deepEqual(worker.refusals, []);
	await worker.deactivate();
});

test("settings change the lengths and the long-break count", async () => {
	const host = mockHost({
		capabilities: CAPS,
		settings: { focusMinutes: 50, longBreakEvery: 2 },
	});
	const worker = await mountWorker(main, { host, commands: COMMANDS });
	const view = await worker.request("pomo.get");
	assert.equal(view.state.remainingMs, 50 * 60_000);
	assert.equal(view.longEvery, 2);
	await worker.deactivate();
});

test("palette commands toggle and report in words", async () => {
	const host = mockHost({ capabilities: CAPS });
	const worker = await mountWorker(main, { host, commands: COMMANDS });
	assert.equal(await worker.command("pomodoro.toggle"), "Focus running.");
	assert.equal(await worker.command("pomodoro.toggle"), "Focus paused.");
	assert.equal(
		await worker.command("pomodoro.skip"),
		"Skipped. Next: Short break.",
	);
	assert.equal(await worker.command("pomodoro.reset"), "Short break reset.");
	await worker.deactivate();
});
