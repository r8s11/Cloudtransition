// The timer face. The worker owns the clock; this panel draws its state and sends presses.
// The countdown is a <RelativeTime>, which Orca keeps current without the panel polling.
import {
	atom,
	Badge,
	Box,
	Button,
	Callout,
	Heading,
	plugin,
	read,
	RelativeTime,
	Row,
	set,
	Stack,
	Text,
	type PanelContext,
} from "orca";
import type { TimerView } from "./protocol";
import { clock, PHASE_LABEL } from "./timer";

const view = atom<TimerView | null>(null);
const failure = atom<string | null>(null);

type Action = "pomo.start" | "pomo.pause" | "pomo.reset" | "pomo.skip";

async function send(name: Action | "pomo.get"): Promise<void> {
	try {
		set(view, await plugin.request(name));
		set(failure, null);
	} catch (error) {
		set(failure, error instanceof Error ? error.message : String(error));
	}
}

export function setup(ctx: PanelContext): void {
	let due: ReturnType<typeof setTimeout> | undefined;
	ctx.subscriptions.push(
		plugin.on("pomo.changed", (next) => {
			set(view, next);
			// One check just after the end, in case the worker was stopped and missed it.
			clearTimeout(due);
			const endsAt = next.state.endsAt;
			if (next.state.status === "running" && endsAt !== null) {
				due = setTimeout(
					() => void send("pomo.get"),
					Math.max(0, endsAt - Date.now()) + 1500,
				);
			}
		}),
	);
	ctx.signal.addEventListener("abort", () => clearTimeout(due));
	void send("pomo.get");
}

export default function Panel() {
	const current = read(view);
	const error = read(failure);
	if (!current) {
		return error ? (
			<Callout tone="danger" title="Timer unavailable" icon="error">
				<Text>{error}</Text>
			</Callout>
		) : (
			<Text muted>Loading…</Text>
		);
	}
	const { state, longEvery } = current;
	const running = state.status === "running" && state.endsAt !== null;
	const statusBadge =
		state.status === "running" ? (
			<Badge tone="accent">Running</Badge>
		) : state.status === "paused" ? (
			<Badge tone="warning">Paused</Badge>
		) : (
			<Badge>Ready</Badge>
		);
	const sessionNumber =
		state.phase === "focus"
			? Math.min(state.cycle + 1, longEvery)
			: state.cycle;
	return (
		<Stack gap="md">
			<Row justify="between">
				<Heading level={2}>{PHASE_LABEL[state.phase]}</Heading>
				{statusBadge}
			</Row>
			<Box border radius="md" padding="md" align="center">
				{running ? (
					<Stack gap="xs" align="center">
						<Heading level={1}>
							<RelativeTime at={state.endsAt as number} format="duration" />{" "}
							left
						</Heading>
						<Text muted size="sm">
							Ends at{" "}
							{new Date(state.endsAt as number).toLocaleTimeString([], {
								hour: "numeric",
								minute: "2-digit",
							})}
						</Text>
					</Stack>
				) : (
					<Heading level={1}>{clock(state.remainingMs)}</Heading>
				)}
			</Box>
			<Row gap="xs" wrap>
				{running ? (
					<Button icon="pause" onPress={() => send("pomo.pause")}>
						Pause
					</Button>
				) : (
					<Button
						icon="play"
						tone="accent"
						variant="solid"
						onPress={() => send("pomo.start")}
					>
						{state.status === "paused" ? "Resume" : "Start"}
					</Button>
				)}
				<Button icon="next" variant="ghost" onPress={() => send("pomo.skip")}>
					Skip
				</Button>
				<Button
					icon="refresh"
					variant="ghost"
					disabled={state.status === "idle"}
					onPress={() => send("pomo.reset")}
				>
					Reset
				</Button>
			</Row>
			<Text muted size="sm">
				Session {sessionNumber} of {longEvery} · {state.doneToday} focus{" "}
				{state.doneToday === 1 ? "session" : "sessions"} today
			</Text>
			{error ? (
				<Callout tone="danger" title="Last action failed" icon="error">
					<Text>{error}</Text>
				</Callout>
			) : null}
		</Stack>
	);
}
