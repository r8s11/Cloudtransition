// `orca plugin check` renders the panel once per scenario, each with the worker on a fresh host.
import { defineCheck } from "orca/testing";

const now = Date.now();
const base = { phase: "focus", cycle: 1, day: "2000-01-01", doneToday: 0 };

export default defineCheck({
	fresh: {},
	running: {
		storage: {
			timer: {
				...base,
				status: "running",
				endsAt: now + 18 * 60_000,
				remainingMs: 0,
			},
		},
	},
	paused: {
		storage: {
			timer: {
				...base,
				status: "paused",
				endsAt: null,
				remainingMs: 7 * 60_000 + 30_000,
			},
		},
	},
});
