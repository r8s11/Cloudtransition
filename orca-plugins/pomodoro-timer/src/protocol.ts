// The panel <-> worker contract, declared once: src/panel.tsx and src/worker.ts both read it.
import type { TimerState } from "./timer";

export interface TimerView {
	state: TimerState;
	/** Focus sessions per long break, from Settings. */
	longEvery: number;
}

declare module "orca" {
	interface PluginRequests {
		/** Current timer; finishes a phase whose end has already passed. */
		"pomo.get": { output: TimerView };
		/** Starts or resumes; no-op while running. */
		"pomo.start": { output: TimerView };
		"pomo.pause": { output: TimerView };
		/** Back to the start of the current phase, stopped. */
		"pomo.reset": { output: TimerView };
		/** Ends the current phase now without counting it. */
		"pomo.skip": { output: TimerView };
	}
	interface PluginPanelEvents {
		/** Posted to every open panel after the timer changes. */
		"pomo.changed": TimerView;
	}
}
