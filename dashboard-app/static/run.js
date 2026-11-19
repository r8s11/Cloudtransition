// Run tab (templates/pages/run.html) and Today quick tools: skill runner, runner cards and output dialog.
// ── Skill runner (Run tab + Today quick tools) ───────────────
(() => {
	const grids = Array.from(document.querySelectorAll("[data-run-grid]"));
	if (!grids.length) return;

	const history = document.getElementById("runHistory");
	const dialog = document.getElementById("runOutputDialog");
	let pollTimer = null;
	let pollFailCount = 0;
	let prevStatus = {}; // skill -> last announced status, for start/finish announcements
	let historyRows = new Map(); // run id -> history row element, for in-place diff updates

	// Page-level live region that announces only run start/finish transitions,
	// so screen readers hear one message at a time instead of every poll tick.
	const announcer = document.createElement("div");
	announcer.setAttribute("aria-live", "polite");
	announcer.className = "sr-only";
	Object.assign(announcer.style, {
		position: "absolute",
		width: "1px",
		height: "1px",
		padding: 0,
		margin: "-1px",
		overflow: "hidden",
		clip: "rect(0, 0, 0, 0)",
		whiteSpace: "nowrap",
		border: 0,
	});
	document.body.appendChild(announcer);

	function announce(text) {
		announcer.textContent = "";
		announcer.textContent = text;
	}
	let providerModels = {};   // {claude: [...], codex: [...], opencode: [...], openrouter: [...]}
	let providerAvailable = {}; // {claude: true, codex: true, ...}
	let providerUnavailableReason = {};

	/** Make an element with optional class and text. Text is always set via
	 *  textContent, so no value can ever be parsed as markup. */
	function el(tag, cls, text) {
		const node = document.createElement(tag);
		if (cls) node.className = cls;
		if (text !== undefined) node.textContent = text;
		return node;
	}

	/** "provider:id" split at the first colon only. Model ids such as
	 *  "nvidia/…:free" contain a colon themselves; splitting on every colon
	 *  cut the id short, so the lookup missed and the card offered efforts
	 *  the server rejects. */
	function splitModel(value) {
		const text = String(value);
		const at = text.indexOf(":");
		return at < 0 ? [text] : [text.slice(0, at), text.slice(at + 1)];
	}

	/** Human-readable label for a model value ("claude:sonnet" or "sonnet"). */
	function modelLabel(value) {
		const [p, id] = splitModel(value);
		const provider = p === "claude" && !id ? "claude" : p;
		const modelId = p === "claude" && !id ? value : id;
		const list = providerModels[provider] || [];
		const m = list.find((x) => x.id === modelId);
		if (m) return provider === "claude" ? m.label : `${provider} \u00b7 ${m.label}`;
		return value;
	}

	function clear(node) {
		while (node.firstChild) node.removeChild(node.firstChild);
	}

	function outputButton(path, label) {
		const btn = el("button", "action-btn action-btn-ghost", "Output");
		btn.type = "button";
		btn.dataset.output = path || "";
		btn.dataset.outputLabel = label;
		if (label) btn.setAttribute("aria-label", `View output: ${label}`);
		btn.hidden = !path;
		return btn;
	}

	function inputPlaceholder(label, type) {
		if (/youtube/i.test(label)) return "https://www.youtube.com/watch?v=\u2026";
		if (/month/i.test(label)) return "2026-11";
		return type === "url" ? "https://" : "";
	}

	function renderItem(s) {
		const item = el("div", "run-item");
		item.dataset.skill = s.id;

		const head = el("div", "run-item-head");
		const icon = el("span", "run-item-icon", s.icon);
		icon.setAttribute("aria-hidden", "true");
		const text = el("div", "run-item-text");
		// Title row: name plus what the run spends (engine comes from app.py's
		// runner_engine; an older server without the field shows no tag).
		const title = el("div", "run-item-title");
		title.appendChild(el("h4", null, s.label));
		if (s.engine) {
			title.appendChild(el("span", `run-tag run-tag-${s.engine.tier}`, s.engine.label));
		}
		text.appendChild(title);
		text.appendChild(el("p", null, s.blurb));
		head.append(icon, text);
		item.appendChild(head);

		if (s.input_label) {
			const field = el("label", "run-field");
			field.appendChild(el("span", "run-field-label", s.input_label));
			const input = el("input", "run-input");
			input.type = s.input_type || "url";
			// An example value, never a copy of the visible label.
			input.placeholder = inputPlaceholder(s.input_label, input.type);
			input.dataset.runInput = "";
			field.appendChild(input);
			item.appendChild(field);
		}
		if (s.options) {
			const options = el("div", "run-settings-row");
			// ── Model picker (provider-labelled, grouped by provider) ──
			const modelField = el("label", "run-field");
			modelField.appendChild(el("span", "run-field-label", "Model"));
			const modelPicker = el("select", "run-select");
			modelPicker.dataset.runModel = "";
			const allowedProviders = Array.isArray(s.providers) && s.providers.length ? s.providers : null;
			const providerName = (p) =>
				p === "claude" ? "Claude" : p === "opencode" ? "OpenCode" : p.charAt(0).toUpperCase() + p.slice(1);
			const providerLabel = (p) =>
				p === "opencode" ? "OpenCode \u2014 free models" : `${providerName(p)} \u2014 local catalogue`;
			let defaultValue = `claude:${s.model || "sonnet"}`;
			if (allowedProviders) {
				const provider = allowedProviders.find((p) => providerModels[p]?.length);
				defaultValue = provider
					? `${provider}:${providerModels[provider][0].id}`
					: `${allowedProviders[0]}:`;
			}
			for (const [provider, models] of Object.entries(providerModels)) {
				if (allowedProviders && !allowedProviders.includes(provider)) continue;
				if (!models || !models.length) continue;
				const optgroup = document.createElement("optgroup");
				optgroup.label = providerLabel(provider);
				for (const m of models) {
					const option = el(
						"option",
						null,
						provider === "claude" ? m.label : `${provider} \u00b7 ${m.label}`
					);
					// Always provider-prefixed so the card's configured model matches.
					option.value = `${provider}:${m.id}`;
					option.selected = option.value === defaultValue;
					optgroup.appendChild(option);
				}
				modelPicker.appendChild(optgroup);
			}
			if (!modelPicker.options.length) {
				const option = el("option", null, "No available models");
				option.value = "";
				option.disabled = true;
				option.selected = true;
				modelPicker.appendChild(option);
				modelPicker.disabled = true;
			}
			modelField.appendChild(modelPicker);
			options.appendChild(modelField);

			// ── Effort picker (options depend on the selected model) ──
			const effortField = el("label", "run-field");
			effortField.appendChild(el("span", "run-field-label", "Effort"));
			const effortPicker = el("select", "run-select");
			effortPicker.dataset.runEffort = "";
			function setEffortOptions(modelValue) {
				const [p, id] = splitModel(modelValue);
				const list = providerModels[p]?.find((m) => m.id === id)?.efforts || ["default"];
				effortPicker.disabled = !modelPicker.value;
				clear(effortPicker);
				let selected = "default";
				for (const value of list) {
					const option = el("option", null, value);
					option.value = value;
					if (value === selected || (!list.includes("default") && value === list[0])) {
						option.selected = true;
						selected = value;
					}
					effortPicker.appendChild(option);
				}
				return selected;
			}
			setEffortOptions(defaultValue);
			modelPicker.addEventListener("change", () => {
				setEffortOptions(modelPicker.value);
			});
			effortField.appendChild(effortPicker);
			options.appendChild(effortField);

			item.appendChild(options);
			const unavailable = (allowedProviders || Object.keys(providerAvailable))
				.filter((provider) => providerAvailable[provider] === false)
				.map((provider) => `${providerName(provider)}: ${providerUnavailableReason[provider] || "Catalogue unavailable"}`);
			if (unavailable.length) item.appendChild(el("p", "run-status", unavailable.join(" · ")));
		}

		const foot = el("div", "run-item-foot");
		const btn = el("button", "action-btn", "Run");
		btn.type = "button";
		btn.setAttribute("aria-label", `Run ${s.label}`);
		btn.dataset.run = s.id;
		if (s.options && !item.querySelector("[data-run-model]")?.value) {
			btn.setAttribute("aria-disabled", "true");
			btn.classList.add("is-disabled");
		}
		const status = el(
			"span",
			"run-status",
			s.kind === "shell" || s.options
				? (s.options && !item.querySelector("[data-run-model]")?.value ? "No model available" : "Ready")
				: `Ready \u00b7 ${modelLabel(`claude:${s.model || "sonnet"}`)}`,
		);
		status.dataset.statusFor = s.id;
		status.setAttribute("role", "status");
		status.setAttribute("aria-live", "polite");
		const view = outputButton(null, s.label);
		view.dataset.viewFor = s.id;
		foot.append(btn, view, status);
		item.appendChild(foot);
		return item;
	}

	const RUN_STATUS_LABELS = {
		running: "Running",
		done: "Completed",
		failed: "Failed",
		cancelled: "Cancelled",
	};

	// ── Render the buttons from the server catalog ──────────────
	// A grid with data-skills="a,b" shows only those runners, in that order.
	function loadCatalog(force = false) {
		for (const grid of grids) grid.setAttribute("aria-busy", "true");
		// Snapshot any values the user typed or selected before the grids are
		// rebuilt, so a refresh never discards half-filled input or picks.
		const prior = capturedRunnerState();
		const url = force
			? "/api/skills/catalog/refresh"
			: "/api/skills/catalog";
		return fetch(url, force ? { method: "POST" } : {})
			.then((r) => {
				if (!r.ok) throw new Error(`catalog HTTP ${r.status}`);
				return r.json();
			})
			.then((data) => {
				providerModels = data.provider_models || {};
				providerAvailable = data.provider_available || {};
				providerUnavailableReason = data.provider_unavailable_reason || {};
				const byId = new Map(data.skills.map((s) => [s.id, s]));
				for (const grid of grids) {
					clear(grid);
					const only = grid.dataset.skills;
					const list = only
						? only.split(",").map((id) => byId.get(id)).filter(Boolean)
						: data.skills;
					for (const s of list) {
						const item = renderItem(s);
						grid.appendChild(item);
						restoreRunnerState(item, s.id, prior);
					}
					grid.removeAttribute("aria-busy");
				}
				poll(); // paint status of runs already in flight
				return true;
			})
			.catch(() => {
				// Keep any rendered cards; only an empty grid needs the notice.
				for (const grid of grids) {
					grid.removeAttribute("aria-busy");
					if (grid.querySelector(".run-item")) continue;
					clear(grid);
					grid.appendChild(
						el("p", "run-empty", "Could not load the skill catalogue."),
					);
				}
				return false;
			});
	}

	// Snapshot per-skill input text and model/effort selections from the
	// currently rendered cards, keyed by runner id.
	function capturedRunnerState() {
		const state = new Map();
		for (const grid of grids) {
			for (const item of grid.querySelectorAll(".run-item")) {
				const btn = item.querySelector("[data-run]");
				if (!btn) continue;
				const inputEl = item.querySelector("input[data-run-input]");
				const modelEl = item.querySelector("select[data-run-model]");
				const effortEl = item.querySelector("select[data-run-effort]");
				state.set(btn.dataset.run, {
					input: inputEl ? inputEl.value : "",
					model: modelEl ? modelEl.value : null,
					effort: effortEl ? effortEl.value : null,
				});
			}
		}
		return state;
	}

	// Restore a previously captured input value and model/effort picks onto a
	// freshly rendered card. Changing the model regenerates its effort options
	// via the change listener, so effort is reapplied last.
	function restoreRunnerState(item, id, prior) {
		const p = prior.get(id);
		if (!p) return;
		const input = item.querySelector("input[data-run-input]");
		if (input) input.value = p.input;
		const model = item.querySelector("select[data-run-model]");
		if (model && p.model !== null && [...model.options].some((option) => option.value === p.model && !option.disabled)) {
			model.value = p.model;
			model.dispatchEvent(new Event("change"));
		}
		const effort = item.querySelector("select[data-run-effort]");
		if (effort && p.effort !== null && [...effort.options].some((option) => option.value === p.effort)) effort.value = p.effort;
	}

	loadCatalog();
	poll(); // history should not wait for the slower model catalogues

	// ── Refresh model catalogues (Refresh models button) ──────────
	const refreshBtn = document.getElementById("refreshModels");
	const refreshStatus = document.getElementById("refreshModelsStatus");
	const refreshNote = (text) => {
		if (refreshStatus) refreshStatus.textContent = text;
	};
	if (refreshBtn) {
		refreshBtn.addEventListener("click", () => {
			refreshBtn.disabled = true;
			refreshBtn.textContent = "Updating\u2026";
			refreshNote("Refreshing model catalogue\u2026");
			loadCatalog(true)
				.then((ok) => {
					refreshNote(
						ok
							? "Models refreshed."
							: "Model refresh failed; showing the last known list.",
					);
				})
				.finally(() => {
					refreshBtn.disabled = false;
					refreshBtn.textContent = "Refresh models";
				});
		});
	}

	// ── Fire a run ──────────────────────────────────────────────
	function statusEls(skill) {
		return document.querySelectorAll(`[data-status-for="${CSS.escape(skill)}"]`);
	}

	document.addEventListener("click", (e) => {
		const btn = e.target.closest("[data-run]");
		if (!btn) return;

		const item = btn.closest(".run-item");
		const inputEl = item.querySelector("[data-run-input]");
		const skill = btn.dataset.run;
		// role/aria-live are attributes; changing className never clears them.
		const setAll = (text, cls) =>
			statusEls(skill).forEach((s) => {
				s.textContent = text;
				s.className = `run-status ${cls}`;
			});

		// A disabled button loses keyboard focus; stay focusable instead and
		// guard the click so a second tap cannot re-fire while a run is going.
		if (btn.getAttribute("aria-disabled") === "true") return;
		btn.setAttribute("aria-disabled", "true");
		btn.classList.add("is-disabled");
		setAll("Starting\u2026", "is-running");

		fetch("/api/skills/run", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Requested-With": "XMLHttpRequest",
			},
			body: JSON.stringify({
				skill,
				model: item.querySelector("[data-run-model]")?.value || null,
				effort: item.querySelector("[data-run-effort]")?.value || null,
				input: inputEl ? inputEl.value : null,
			}),
		})
			.then((r) => r.json().then((j) => ({ ok: r.ok, body: j })))
			.then(({ ok, body }) => {
				if (!ok) {
					setAll(body.error || "failed to start", "is-failed");
					btn.removeAttribute("aria-disabled");
					btn.classList.remove("is-disabled");
					return;
				}
				setAll("Running\u2026", "is-running");
				poll();
			})
			.catch(() => {
				setAll("network error", "is-failed");
				btn.removeAttribute("aria-disabled");
				btn.classList.remove("is-disabled");
			});
	});

	// ── Poll while anything is running ──────────────────────────
	function poll() {
		fetch("/api/skills/runs")
			.then((r) => r.json())
			.then((data) => {
				renderHistory(data.runs);

				// Poll succeeded: reset the failure counter.
				pollFailCount = 0;

				// Newest run wins per skill.
				const latest = {};
				for (const run of data.runs) {
					if (!(run.skill in latest)) latest[run.skill] = run;
				}

				let anyRunning = false;
				for (const skill of Object.keys(latest)) {
					const run = latest[skill];
					const sel = CSS.escape(skill);
					const running = run.status === "running";
					anyRunning ||= running;
					statusEls(skill).forEach((s) => {
						// Only touch the live region when the text actually changes,
						// so screen readers are not re-announced on every 2s tick.
						const identity = run.model ? ` · ${run.provider} · ${run.model}` : "";
						const nextText = running
							? `Running…${identity}`
							: `${RUN_STATUS_LABELS[run.status] || run.status}${identity} · ${run.duration}${run.status === "failed" ? " · Open Output, then retry" : ""}`;
						const nextCls = `run-status is-${run.status}`;
						if (s.textContent !== nextText || s.className !== nextCls) {
							s.textContent = nextText;
							s.className = nextCls;
						}
					});
					document.querySelectorAll(`[data-run="${sel}"]`).forEach((b) => {
						// Keep the button focusable; use aria-disabled instead of disabled.
						const model = b.closest(".run-item").querySelector("[data-run-model]");
						const blocked = running || (model && !model.value);
						b.setAttribute("aria-disabled", blocked ? "true" : "false");
						b.classList.toggle("is-disabled", Boolean(blocked));
					});
					document.querySelectorAll(`[data-view-for="${sel}"]`).forEach((v) => {
						v.dataset.output = run.output || "";
						v.hidden = !run.output;
					});

					// Announce start/finish transitions once from the page-level region.
					const before = prevStatus[skill];
					if (before !== run.status) {
						prevStatus[skill] = run.status;
						const label = document.querySelector(`[data-run="${sel}"]`)?.closest(".run-item")?.querySelector("h4")?.textContent || skill;
						if (running) {
							announce(`Starting ${label}`);
						} else if (run.status === "done") {
							announce(`${label} completed`);
						} else if (run.status === "failed") {
							announce(`${label} failed`);
						}
					}
				}

				if (anyRunning && !pollTimer) {
					pollTimer = setInterval(poll, 2000);
				} else if (!anyRunning && pollTimer) {
					clearInterval(pollTimer);
					pollTimer = null;
				}
			})
			.catch(() => {
				// A failed poll must not leave the UI stuck on "Running…".
				pollFailCount += 1;
				if (pollFailCount >= 3) {
					announce("Lost contact with the server, retrying…");
					// Re-enable every Run button so the user can try again.
					document.querySelectorAll("[data-run]").forEach((b) => {
						b.setAttribute("aria-disabled", "false");
						b.classList.remove("is-disabled");
					});
				}
				// Keep polling so recovery happens automatically when the server returns.
			});
	}

	function renderHistory(runs) {
		if (!history) return;

		const incoming = new Map();
		for (const r of runs) incoming.set(r.id, r);

		// Remove rows whose run is no longer reported.
		for (const [id, row] of historyRows) {
			if (!incoming.has(id)) {
				history.removeChild(row);
				historyRows.delete(id);
			}
		}

		// Update existing rows in place (preserving any focus/selection inside
		// them) and append only genuinely new rows.
		for (const r of runs) {
			const existing = historyRows.get(r.id);
			if (existing) {
				updateHistoryRow(existing, r);
			} else {
				const row = buildHistoryRow(r);
				history.appendChild(row);
				historyRows.set(r.id, row);
			}
		}

		// Keep the empty state in sync: show it when there are no runs, hide it
		// once there is at least one run row.
		const empty = history.querySelector(".empty-state");
		if (runs.length && empty) {
			history.removeChild(empty);
		} else if (!runs.length && historyRows.size === 0 && !empty) {
			const empty = el("div", "empty-state empty-state-pad");
			empty.appendChild(el("div", "empty-icon", "\u25CB"));
			empty.appendChild(el("p", null, "No runs yet. Start one above."));
			history.appendChild(empty);
		}
	}

	function buildHistoryRow(r) {
		const row = el("div", "run-log-row");
		row.dataset.runId = r.id;
		const dot = el("span", `run-log-dot is-${r.status}`);
		dot.setAttribute("aria-hidden", "true");
		// Status is text, not colour alone; the dot is reinforcement only.
		const status = el("span", `run-log-status is-${r.status}`);
		status.append(
			dot,
			el("span", null, RUN_STATUS_LABELS[r.status] || r.status),
		);
		const label = el("span", "run-log-label", `${r.label}${r.model ? ` · ${r.provider} · ${r.model}` : ""}`);
		label.title = label.textContent;
		const out = el("span", "run-log-out");
		if (r.output) out.appendChild(outputButton(r.output, `${r.label} \u00b7 ${r.started}`));
		else out.textContent = "\u2014";
		row.append(
			status,
			label,
			el("span", "run-log-time", r.started),
			el("span", "run-log-dur", r.duration || (r.status === "running" ? "running\u2026" : "\u2014")),
			out,
		);
		return row;
	}

	function updateHistoryRow(row, r) {
		const status = row.querySelector(".run-log-status");
		const dot = row.querySelector(".run-log-dot");
		const time = row.querySelector(".run-log-time");
		const dur = row.querySelector(".run-log-dur");
		const out = row.querySelector(".run-log-out");
		if (status) {
			const textSpan = status.children[1];
			if (textSpan) textSpan.textContent = RUN_STATUS_LABELS[r.status] || r.status;
			status.className = `run-log-status is-${r.status}`;
		}
		if (dot) dot.className = `run-log-dot is-${r.status}`;
		if (time) time.textContent = r.started;
		if (dur) dur.textContent = r.duration || (r.status === "running" ? "running\u2026" : "\u2014");
		if (out) {
			if (r.output) {
				if (!out.querySelector("button")) {
					out.textContent = "";
					out.appendChild(outputButton(r.output, `${r.label} \u00b7 ${r.started}`));
				}
			} else {
				out.textContent = "\u2014";
			}
		}
	}

	// ── Output viewer ───────────────────────────────────────────
	if (dialog) {
		const body = document.getElementById("runOutputBody");
		const note = document.getElementById("runOutputNote");
		const originalDetails = document.getElementById("runOutputOriginalDetails");
		const originalBody = document.getElementById("runOutputOriginal");
		const stderrDetails = document.getElementById("runOutputStderrDetails");
		const stderrBody = document.getElementById("runOutputStderr");
		const title = document.getElementById("runOutputTitle");
		let outputRequest = 0;

		function textContent(value) {
			if (typeof value === "string") return value;
			if (!Array.isArray(value)) return "";
			return value
				.filter((part) => part && typeof part.text === "string")
				.map((part) => part.text)
				.join("\n");
		}

		function parseRunOutput(raw) {
			const cleaned = raw
				.replace(/\u001b(?:\[[0-?]*[ -/]*[@-~]|\][^\u0007]*(?:\u0007|\u001b\\))/g, "")
				.replace(/\r\n?/g, "\n")
				.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "");
			const stderrMarker = "\n\n--- stderr ---\n";
			const stderrAt = cleaned.indexOf(stderrMarker);
			const stdout =
				stderrAt < 0 ? cleaned : cleaned.slice(0, stderrAt);
			const stderr =
				stderrAt < 0 ? "" : cleaned.slice(stderrAt + stderrMarker.length).trim();
			const candidate = stdout.trim().replace(/^\uFEFF/, "");

			if (!candidate) {
				return {
					text: stderr || "No output was produced.",
					note: stderr ? "Standard error · no standard output" : "",
					stderr: "",
					transformed: Boolean(stderr) || cleaned !== raw,
				};
			}

			try {
				const value = JSON.parse(candidate);
				const metadata = [];
				if (typeof value?.model === "string") metadata.push(value.model);
				if (Number.isFinite(value?.usage?.total_tokens)) {
					metadata.push(`${value.usage.total_tokens.toLocaleString()} tokens`);
				}

				if (value && typeof value === "object" && value.error) {
					const message =
						typeof value.error === "string"
							? value.error
							: value.error.message || value.error.description;
					if (typeof message === "string") {
						return {
							text: message,
							note: ["Provider error", ...metadata].join(" · "),
							stderr,
							transformed: true,
						};
					}
				}

				if (Array.isArray(value?.choices)) {
					const answers = value.choices
						.map((choice) => {
							const message = choice?.message || choice?.delta;
							return textContent(message?.content) || message?.refusal || "";
						})
						.filter(Boolean);
					if (answers.length) {
						return {
							text: answers.join("\n\n"),
							note: metadata.length
								? `Response · ${metadata.join(" · ")}`
								: "Response extracted from provider JSON",
							stderr,
							transformed: true,
						};
					}
				}

				return {
					text:
						typeof value === "string"
							? value
							: JSON.stringify(value, null, 2),
					note: "JSON output formatted",
					stderr,
					transformed: true,
				};
			} catch {
				return {
					text: stdout,
					note: "",
					stderr,
					transformed: cleaned !== raw || stderrAt >= 0,
				};
			}
		}

		function renderRunOutput(raw) {
			const parsed = parseRunOutput(raw);
			body.textContent = parsed.text;
			note.textContent = parsed.note;
			note.hidden = !parsed.note;
			originalBody.textContent = raw;
			originalDetails.hidden = !parsed.transformed;
			stderrBody.textContent = parsed.stderr;
			stderrDetails.hidden = !parsed.stderr;
		}

		document.addEventListener("click", (e) => {
			const btn = e.target.closest("[data-output]");
			if (!btn || !btn.dataset.output) return;
			const request = ++outputRequest;
			title.textContent = `${btn.dataset.outputLabel || "Run output"} — ${btn.dataset.output}`;
			renderRunOutput("Loading\u2026");
			dialog.showModal();
			fetch(`/api/file?path=${encodeURIComponent(btn.dataset.output)}`)
				.then((r) => {
					if (!r.ok) throw new Error(`Output request failed (${r.status}).`);
					return r.json();
				})
				.then((j) => {
					if (request !== outputRequest) return;
					if (typeof j.content !== "string") {
						throw new Error(j.error || "Output file has no readable content.");
					}
					renderRunOutput(j.content);
					announce("Output loaded");
				})
				.catch((error) => {
					if (request !== outputRequest) return;
					renderRunOutput(error.message || "Could not load output.");
				});
		});
		dialog
			.querySelector("[data-close-output]")
			.addEventListener("click", () => dialog.close());
	}
})();

