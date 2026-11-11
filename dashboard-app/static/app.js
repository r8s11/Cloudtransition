document.addEventListener("DOMContentLoaded", () => {
	var tabs = Array.from(document.querySelectorAll('.section-nav [role="tab"]'));
	var panels = document.querySelectorAll('[role="tabpanel"]');

	function activateTab(tab, updateHash) {
		// Deactivate all tabs
		tabs.forEach((t) => {
			t.classList.remove("active");
			t.setAttribute("aria-selected", "false");
			t.setAttribute("tabindex", "-1");
		});

		// Activate selected tab
		tab.classList.add("active");
		tab.setAttribute("aria-selected", "true");
		tab.setAttribute("tabindex", "0");

		// Show correct panel
		panels.forEach((p) => {
			p.classList.remove("active");
		});
		var target = document.getElementById("page-" + tab.dataset.page);
		if (target) {
			target.classList.add("active");
			animateBars(target);
		}

		// Update URL hash
		if (updateHash !== false) {
			history.replaceState(null, "", "#" + tab.dataset.page);
		}
	}

	// Click handler
	tabs.forEach((tab) => {
		tab.addEventListener("click", () => {
			activateTab(tab);
			tab.focus();
		});
	});

	// Keyboard arrow navigation (WAI-ARIA Tabs pattern)
	tabs.forEach((tab) => {
		tab.addEventListener("keydown", (e) => {
			var idx = tabs.indexOf(tab);
			var next;

			if (e.key === "ArrowRight" || e.key === "ArrowDown") {
				e.preventDefault();
				next = tabs[(idx + 1) % tabs.length];
			} else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
				e.preventDefault();
				next = tabs[(idx - 1 + tabs.length) % tabs.length];
			} else if (e.key === "Home") {
				e.preventDefault();
				next = tabs[0];
			} else if (e.key === "End") {
				e.preventDefault();
				next = tabs[tabs.length - 1];
			}

			if (next) {
				activateTab(next);
				next.focus();
			}
		});
	});

	// Restore tab from URL hash on load
	var hash = window.location.hash.replace("#", "");
	if (hash) {
		var matchingTab = tabs.find((t) => t.dataset.page === hash);
		if (matchingTab) {
			activateTab(matchingTab, false);
		}
	}

	// Handle browser back/forward
	window.addEventListener("hashchange", () => {
		var h = window.location.hash.replace("#", "");
		var t = tabs.find((tab) => tab.dataset.page === h);
		if (t) activateTab(t, false);
	});

	// Animate progress bars on load
	animateBars(document.querySelector(".page.active") || document);
});

function animateBars(scope) {
	requestAnimationFrame(() => {
		requestAnimationFrame(() => {
			scope.querySelectorAll(".progress-fill[data-width]").forEach((el) => {
				// data-width is a percentage ("0%", "60%", "100%"); scaleX takes a number.
				var pct = parseFloat(el.dataset.width) / 100;
				el.style.transform = "scaleX(" + pct + ")";
			});
		});
	});
}

// ── Weekly fold map focus mode ────────────────────────────────
(() => {
	var foldColumn = document.querySelector(".fold-column");
	var steps = Array.from(
		document.querySelectorAll(".fold-step[data-fold-label]"),
	);
	var card = document.getElementById("fold-focus-card");
	var title = card && card.querySelector("[data-fold-focus-title]");
	var detail = card && card.querySelector("[data-fold-focus-detail]");
	var progress = card && card.querySelector("[data-fold-focus-progress]");
	var meta = card && card.querySelector("[data-fold-focus-meta]");
	var neuralSvg = card && card.querySelector("[data-fold-neural]");

	if (
		!foldColumn ||
		!steps.length ||
		!card ||
		!title ||
		!detail ||
		!progress ||
		!meta
	) {
		return;
	}

	var taskRows = Array.from(
		document.querySelectorAll(".task-check[data-realm]"),
	).map((box) => {
		var text =
			box.parentElement && box.parentElement.querySelector(".task-text");
		return {
			box: box,
			text: text ? text.textContent.trim().toLowerCase() : "",
		};
	});

	function getFoldScope(step) {
		var label = (step.dataset.foldLabel || "").trim();
		var lowerLabel = label.toLowerCase();
		var directMatches = [];
		var scopeName = "Workday task ledger";

		if (lowerLabel.includes("devops")) {
			scopeName = "DevOps task ledger";
			directMatches = taskRows.filter(
				(row) => row.box.dataset.realm === "devops",
			);
		} else if (lowerLabel.includes("project block")) {
			var projectName = label.replace(/^project block\s*[—-]\s*/i, "").trim();
			var keywords = projectName
				.toLowerCase()
				.split(/[^a-z0-9]+/)
				.filter((word) => word.length > 2 && word !== "week");
			scopeName = projectName + " context";
			directMatches = taskRows.filter((row) =>
				keywords.some((keyword) => row.text.includes(keyword)),
			);
		} else if (lowerLabel.includes("weekend")) {
			scopeName = "Weekend reset";
			directMatches = taskRows.filter((row) =>
				/(money|review|reset|finance)/.test(row.text),
			);
		} else {
			directMatches = taskRows;
		}

		var hasDirectLinks = directMatches.length > 0;
		var rows = hasDirectLinks ? directMatches : taskRows;
		var done = rows.filter((row) => row.box.dataset.done === "true").length;
		var total = rows.length;

		return {
			scopeName: hasDirectLinks ? scopeName : "Workspace task ledger",
			directLinks: hasDirectLinks ? directMatches.length : 0,
			done: done,
			total: total,
		};
	}

	function getFoldGroups(step) {
		var label = (step.dataset.foldLabel || "").trim().toLowerCase();
		var groups = {};
		var matched;

		if (label.includes("devops")) {
			taskRows.forEach(function(row) {
				if (row.box.dataset.realm === "devops") {
					var cat = row.box.closest(".task-item");
					cat = cat && cat.querySelector(".task-cat");
					cat = cat ? cat.textContent.trim() : "devops";
					if (!groups[cat]) groups[cat] = { total: 0, done: 0 };
					groups[cat].total++;
					if (row.box.dataset.done === "true") groups[cat].done++;
				}
			});
		} else if (label.includes("project block")) {
			var projectName = label.replace(/^project block\s*[—-]\s*/i, "").trim();
			var keywords = projectName.split(/[^a-z0-9]+/).filter(function(w) { return w.length > 2 && w !== "week"; });
			taskRows.forEach(function(row) {
				if (keywords.some(function(k) { return row.text.includes(k); })) {
					var cat = row.box.closest(".task-item");
					cat = cat && cat.querySelector(".task-cat");
					cat = cat ? cat.textContent.trim() : "project";
					if (!groups[cat]) groups[cat] = { total: 0, done: 0 };
					groups[cat].total++;
					if (row.box.dataset.done === "true") groups[cat].done++;
				}
			});
		} else if (label.includes("weekend")) {
			taskRows.forEach(function(row) {
				if (/(money|review|reset|finance)/.test(row.text)) {
					var cat = row.box.closest(".task-item");
					cat = cat && cat.querySelector(".task-cat");
					cat = cat ? cat.textContent.trim() : "reset";
					if (!groups[cat]) groups[cat] = { total: 0, done: 0 };
					groups[cat].total++;
					if (row.box.dataset.done === "true") groups[cat].done++;
				}
			});
		} else {
			taskRows.forEach(function(row) {
				var cat = row.box.closest(".task-item");
				cat = cat && cat.querySelector(".task-cat");
				cat = cat ? cat.textContent.trim() : "tasks";
				if (!groups[cat]) groups[cat] = { total: 0, done: 0 };
				groups[cat].total++;
				if (row.box.dataset.done === "true") groups[cat].done++;
			});
		}

		return Object.keys(groups).map(function(name) {
			return { name: name, total: groups[name].total, done: groups[name].done };
		}).sort(function(a, b) { return b.total - a.total; }).slice(0, 8);
	}

	function renderNeuralGraph(step, scope) {
		if (!neuralSvg) return;
		var groups = getFoldGroups(step);
		if (groups.length === 0) {
			neuralSvg.innerHTML = "";
			return;
		}

		var cx = 108, cy = 20;
		var radius = 42;
		var svg = "";
		var totalTasks = scope.total || 1;

		// Connection lines from hub to each satellite
		groups.forEach(function(g, i) {
			var angle = (2 * Math.PI * i / groups.length) - Math.PI / 2;
			var nx = cx + radius * Math.cos(angle);
			var ny = cy + 50 + radius * Math.sin(angle) * 0.6;
			var isActive = g.total > 0;
			svg += '<line class="neural-line' + (isActive ? " is-active" : "") + '" x1="' + cx + '" y1="' + cy + '" x2="' + nx.toFixed(1) + '" y2="' + ny.toFixed(1) + '"/>';
		});

		// Hub node (the focused step)
		svg += '<circle class="neural-dot is-hub" cx="' + cx + '" cy="' + cy + '" r="4"/>';

		// Satellite nodes
		groups.forEach(function(g, i) {
			var angle = (2 * Math.PI * i / groups.length) - Math.PI / 2;
			var nx = cx + radius * Math.cos(angle);
			var ny = cy + 50 + radius * Math.sin(angle) * 0.6;
			var r = 2 + Math.min(g.total, 4);
			var doneClass = g.done === g.total && g.total > 0 ? " is-done" : "";
			// 7px labels overlapped into an unreadable smear; the name and count
			// now ride a hover title. Names come from task files: escape them.
			var name = g.name.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
			svg += '<circle class="neural-dot' + doneClass + '" cx="' + nx.toFixed(1) + '" cy="' + ny.toFixed(1) + '" r="' + r + '">' +
				'<title>' + name + ' — ' + g.done + ' of ' + g.total + ' done</title></circle>';
		});

		neuralSvg.innerHTML = svg;
	}

	function render(step) {
		steps.forEach((item) => {
			var selected = item === step;
			item.classList.toggle("is-focused", selected);
			item.setAttribute("aria-pressed", String(selected));
		});

		var scope = getFoldScope(step);
		var total = scope.total;
		var percent = total ? Math.round((scope.done / total) * 100) : 0;

		title.textContent = scope.scopeName;
		detail.textContent = scope.directLinks
			? scope.done + " of " + total + " linked tasks complete."
			: "No direct task link; showing the full workspace ledger.";
		progress.style.transform = "scaleX(" + percent / 100 + ")";
		meta.textContent =
			step.dataset.foldDay +
			" · " +
			(total - scope.done) +
			" remaining · step " +
			(parseInt(step.dataset.foldIndex, 10) + 1);
		renderNeuralGraph(step, scope);
		card.hidden = false;
	}

	function move(step, offset) {
		var index = steps.indexOf(step);
		var next = steps[(index + offset + steps.length) % steps.length];
		next.focus();
		render(next);
	}

	foldColumn.dataset.foldEnhanced = "true";
	var initial =
		steps.find((step) => step.classList.contains("active")) || steps[0];
	render(initial);

	steps.forEach((step) => {
		step.addEventListener("mouseenter", () => render(step));
		step.addEventListener("focus", () => render(step));
		step.addEventListener("click", () => render(step));
		step.addEventListener("keydown", (event) => {
			if (event.key === "ArrowDown" || event.key === "ArrowRight") {
				event.preventDefault();
				move(step, 1);
			} else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
				event.preventDefault();
				move(step, -1);
			} else if (event.key === "Home") {
				event.preventDefault();
				steps[0].focus();
				render(steps[0]);
			} else if (event.key === "End") {
				event.preventDefault();
				steps[steps.length - 1].focus();
				render(steps[steps.length - 1]);
			} else if (event.key === " " || event.key === "Enter") {
				event.preventDefault();
				render(step);
			} else if (event.key === "Escape") {
				event.preventDefault();
				initial.focus();
				render(initial);
			}
		});
	});
})();

// ── Realm filter pills ────────────────────────────────────────
(() => {
	var pills = document.querySelectorAll(".realm-pill");
	var sections = document.querySelectorAll(".realm-section");

	pills.forEach((pill) => {
		pill.addEventListener("click", () => {
			pills.forEach((p) => {
				p.classList.remove("active");
			});
			pill.classList.add("active");

			var realm = pill.dataset.realm;
			sections.forEach((sec) => {
				if (realm === "all" || sec.dataset.realmSection === realm) {
					sec.style.display = "";
				} else {
					sec.style.display = "none";
				}
			});
		});
	});
})();

// ── Interactive task checkboxes ───────────────────────────────
/** Paint one checkbox (and its row) as done/undone. */
function paintTaskCheck(box, done) {
	box.dataset.done = String(done);
	box.setAttribute("aria-checked", String(done));
	box.textContent = done ? "\u2713" : "";
	box.classList.toggle("done", done);
	var textEl = box.nextElementSibling;
	if (textEl) textEl.classList.toggle("done", done);
	var row = box.closest(".task-item");
	if (row) row.classList.toggle("task-done-row", done);
}

/** Every rendering of the same task (Today and Tasks show some twice). */
function sameTaskChecks(box) {
	return Array.from(
		document.querySelectorAll(".task-check[data-realm]"),
	).filter(
		(b) => b.dataset.realm === box.dataset.realm && b.dataset.text === box.dataset.text,
	);
}

function updateRoutineReviewProgress() {
	var list = document.getElementById("routineReviewList");
	var status = document.getElementById("routineReviewProgress");
	if (!list || !status) return;
	var checks = list.querySelectorAll('.task-check[data-realm="routine"]');
	var done = Array.from(checks).filter((check) => check.dataset.done === "true").length;
	status.textContent = `${done} of ${checks.length} checked`;
}

function setRoutineSaveStatus(message, isError = false) {
	var status = document.getElementById("routineSaveStatus");
	if (!status) return;
	status.textContent = message;
	status.classList.toggle("is-error", isError);
}

/** Persist a checkbox via /api/tasks/toggle. Global so the Today page can
 *  bind rows it adds after a capture. */
function bindTaskCheck(box) {
	function handleToggle() {
		if (box.getAttribute("aria-disabled") === "true") return;
		var isDone = box.dataset.done === "true";
		var newDone = !isDone;
		var twins = sameTaskChecks(box);
		var isRoutine = box.dataset.realm === "routine";

		twins.forEach((b) => paintTaskCheck(b, newDone));
		updateRoutineReviewProgress();
		if (isRoutine) {
			twins.forEach((b) => b.setAttribute("aria-disabled", "true"));
			setRoutineSaveStatus("Saving to routine.md\u2026");
		}

		fetch("/api/tasks/toggle", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Requested-With": "XMLHttpRequest",
			},
			body: JSON.stringify({
				realm: box.dataset.realm,
				line: parseInt(box.dataset.line, 10),
				done: newDone,
				text: box.dataset.text,
			}),
		})
			.then((res) => {
				if (!res.ok) {
					return res.json().catch(() => ({})).then((result) => {
						throw new Error(result.error || `HTTP ${res.status}`);
					});
				}
				return res.json();
			})
			.then((result) => {
				twins.forEach((b) => {
					b.dataset.line = String(result.line);
				});
				if (isRoutine) setRoutineSaveStatus("Saved to routine.md.");
			})
			.catch((error) => {
				revert();
				if (isRoutine) {
					setRoutineSaveStatus(`Not saved: ${error.message}`, true);
				}
			})
			.finally(() => {
				if (isRoutine) {
					twins.forEach((b) => b.removeAttribute("aria-disabled"));
				}
			});

		function revert() {
			twins.forEach((b) => paintTaskCheck(b, isDone));
			updateRoutineReviewProgress();
		}
	}

	box.addEventListener("click", handleToggle);
	box.addEventListener("keydown", (e) => {
		if (e.key === " " || e.key === "Enter") {
			e.preventDefault();
			handleToggle();
		}
	});
}

document.querySelectorAll(".task-check[data-realm]").forEach(bindTaskCheck);
updateRoutineReviewProgress();

// ── Copy-prompt buttons (Update sheet, Actualize money) ──────
document.addEventListener("click", (e) => {
	var btn = e.target.closest("[data-copy-prompt]");
	if (!btn) return;

	var template = document.getElementById(btn.dataset.promptId);
	var status = document.querySelector("[data-copy-status]");
	var text = template ? template.content.textContent.trim() : "";

	function copied() {
		btn.textContent = "\u2713 Prompt copied - paste into opencode";
		if (status) status.textContent = "";
		if (btn.dataset.label) {
			setTimeout(() => {
				btn.textContent = btn.dataset.label;
			}, 2500);
		}
	}

	function fallback() {
		var ta = document.createElement("textarea");
		ta.value = text;
		ta.style.position = "fixed";
		ta.style.opacity = "0";
		document.body.appendChild(ta);
		ta.select();
		var ok = false;
		try {
			ok = document.execCommand("copy");
		} catch (err) {
			ok = false;
		}
		document.body.removeChild(ta);
		if (ok) copied();
		else if (status)
			status.textContent = "Clipboard blocked - copy from your browser.";
	}

	if (!text) {
		if (status) status.textContent = "Prompt template not found.";
		return;
	}

	if (navigator.clipboard && navigator.clipboard.writeText) {
		navigator.clipboard.writeText(text).then(copied).catch(fallback);
	} else {
		fallback();
	}
});

// ── Multi-select Prompt Generation (Future Prompts realm) ──────
(() => {
	const bar = document.getElementById("promptGenBar");
	const countEl = document.getElementById("promptSelCount");
	const genBtn = document.getElementById("generatePromptBtn");
	const clearBtn = document.getElementById("clearSelectionBtn");
	if (!bar || !countEl || !genBtn || !clearBtn) return;

	const checkboxes = Array.from(document.querySelectorAll(".task-select-input[data-realm='prompts']"));
	const taskItems = new Map();
	checkboxes.forEach(cb => {
		const line = cb.dataset.line;
		const item = document.querySelector(`.task-item[data-task-line="${line}"][data-task-realm="prompts"]`);
		if (item) taskItems.set(line, { checkbox: cb, item, text: cb.dataset.text });
	});

	function updateUI() {
		const selected = Array.from(taskItems.values()).filter(t => t.checkbox.checked);
		const count = selected.length;
		countEl.textContent = count;
		genBtn.disabled = count === 0;
		bar.hidden = count === 0;
		selected.forEach(t => t.item.classList.add("selected"));
		Array.from(taskItems.values()).filter(t => !t.checkbox.checked).forEach(t => t.item.classList.remove("selected"));
	}

	checkboxes.forEach(cb => {
		cb.addEventListener("change", updateUI);
	});

	clearBtn.addEventListener("click", () => {
		checkboxes.forEach(cb => { cb.checked = false; });
		updateUI();
	});

	function generatePrompt(selectedItems) {
		const itemsText = selectedItems.map(t => `- ${t.text}`).join("\n");
		return `Use the appropriate skills to implement the following tasks from the CloudTransition dashboard Future Prompts list:

${itemsText}

Context:
- These are tasks from the CloudTransition dashboard Future Prompts list
- Follow the superpowers workflow: check for relevant skills first
- Implement with tests and verification
- Update the todo list when complete`;
	}

	function copyToClipboard(text) {
		if (navigator.clipboard && navigator.clipboard.writeText) {
			return navigator.clipboard.writeText(text);
		}
		const ta = document.createElement("textarea");
		ta.value = text;
		ta.style.position = "fixed";
		ta.style.opacity = "0";
		document.body.appendChild(ta);
		ta.select();
		try {
			document.execCommand("copy");
		} finally {
			document.body.removeChild(ta);
		}
		return Promise.resolve();
	}

	genBtn.addEventListener("click", () => {
		const selected = Array.from(taskItems.values()).filter(t => t.checkbox.checked);
		if (selected.length === 0) return;

		const prompt = generatePrompt(selected);
		copyToClipboard(prompt).then(() => {
			const originalText = genBtn.textContent;
			genBtn.textContent = "✓ Copied! Paste into opencode";
			setTimeout(() => { genBtn.textContent = originalText; }, 2500);
		}).catch(() => {
			const originalText = genBtn.textContent;
			genBtn.textContent = "✗ Copy failed";
			setTimeout(() => { genBtn.textContent = originalText; }, 1500);
		});
	});
})();

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

// ── Today page: capture + second brain ───────────────────────
(() => {
	const captureForm = document.getElementById("captureForm");
	if (!captureForm) return;

	function post(url, payload) {
		return fetch(url, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Requested-With": "XMLHttpRequest",
			},
			body: JSON.stringify(payload),
		}).then((r) => r.json().then((j) => ({ ok: r.ok, body: j })));
	}

	/** FastAPI validation errors arrive as {detail: [...]}; brain.py as
	 *  {message}; our own handlers as {error}. */
	function errorText(body) {
		if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join("; ");
		return body.error || body.message || "failed";
	}

	// ── Capture → TASKS.md ## Inbox ─────────────────────────────
	const captureInput = document.getElementById("captureText");
	const captureStatus = document.getElementById("captureStatus");
	const inboxList = document.getElementById("inboxList");
	const inboxCount = document.getElementById("inboxCount");
	const inboxEmpty = document.getElementById("inboxEmpty");

	captureForm.addEventListener("submit", (e) => {
		e.preventDefault();
		const submit = captureForm.querySelector("button");
		submit.disabled = true;
		post("/api/capture", { text: captureInput.value })
			.then(({ ok, body }) => {
				if (!ok) {
					captureStatus.textContent = errorText(body);
					captureStatus.className = "run-status is-failed";
					return;
				}
				const row = document.createElement("div");
				row.className = "task-item";
				const box = document.createElement("div");
				box.className = "task-check";
				box.setAttribute("role", "checkbox");
				box.tabIndex = 0;
				box.setAttribute("aria-label", body.text);
				box.dataset.realm = body.realm;
				box.dataset.line = String(body.line);
				box.dataset.text = body.text;
				const span = document.createElement("span");
				span.className = "task-text";
				span.textContent = body.text;
				row.append(box, span);
				paintTaskCheck(box, false);
				inboxList.appendChild(row);
				bindTaskCheck(box);
				inboxCount.textContent = String(inboxList.children.length);
				inboxEmpty.hidden = true;
				captureInput.value = "";
				captureStatus.textContent = `added to TASKS.md:${body.line}`;
				captureStatus.className = "run-status is-done";
			})
			.catch(() => {
				captureStatus.textContent = "network error";
				captureStatus.className = "run-status is-failed";
			})
			.finally(() => {
				submit.disabled = false;
				captureInput.focus();
			});
	});

	// ── Second brain: ask ───────────────────────────────────────
	const askForm = document.getElementById("brainAskForm");
	const answer = document.getElementById("brainAnswer");

	askForm.addEventListener("submit", (e) => {
		e.preventDefault();
		const q = askForm.elements.q.value.trim();
		answer.textContent = "Searching\u2026";
		fetch(`/api/brain/query?q=${encodeURIComponent(q)}`)
			.then((r) => r.json().then((j) => ({ ok: r.ok, body: j })))
			.then(({ ok, body }) => {
				answer.textContent = "";
				if (!ok || !body.evidence || !body.evidence.length) {
					answer.textContent = ok ? body.message || "No match." : errorText(body);
					return;
				}
				for (const ev of body.evidence) {
					const cite = document.createElement("div");
					cite.className = "brain-cite";
					cite.textContent = `${ev.path}:${ev.start_line}-${ev.end_line}`;
					const text = document.createElement("p");
					text.className = "brain-text";
					text.textContent = ev.text;
					answer.append(cite, text);
				}
			})
			.catch(() => {
				answer.textContent = "network error";
			});
	});

	// ── Second brain: remember ──────────────────────────────────
	const saveForm = document.getElementById("brainSaveForm");
	const saveStatus = document.getElementById("brainSaveStatus");

	saveForm.addEventListener("submit", (e) => {
		e.preventDefault();
		const f = saveForm.elements;
		saveStatus.textContent = "saving\u2026";
		saveStatus.className = "run-status is-running";
		post("/api/brain/remember", {
			title: f.title.value,
			summary: f.summary.value,
			body: f.body.value,
		})
			.then(({ ok, body }) => {
				if (!ok) {
					saveStatus.textContent = errorText(body);
					saveStatus.className = "run-status is-failed";
					return;
				}
				saveForm.reset();
				saveStatus.textContent = `saved ${body.path}`;
				saveStatus.className = "run-status is-done";
			})
			.catch(() => {
				saveStatus.textContent = "network error";
				saveStatus.className = "run-status is-failed";
			});
	});
})();


// ── Workspace map deep links ────────────────────────────────
// Any link with data-map-query (Today: Recent artifacts) points the embedded
// viewer at that filter, e.g. "folder=artifacts"; its href switches the tab.
document.addEventListener("click", (e) => {
	const link = e.target.closest("[data-map-query]");
	const frame = document.getElementById("workspaceMapFrame");
	if (link && frame) frame.src = "/workspace-map/?" + link.dataset.mapQuery;
});

// ── Interviews tab: inline tracker edits ────────────────────
// Every control writes through a small JSON endpoint and updates the row in
// place; status changes also move the row between the two cards. Notes and
// signals are saved without a reload, so the tab stays usable during a call.
(() => {
	const page = document.getElementById("page-interviews");
	if (!page) return;

	const activeStatuses = new Set(
		(page.dataset.interviewActive || "").split(",").filter(Boolean),
	);
	const closedStatuses = new Set(
		(page.dataset.interviewClosed || "").split(",").filter(Boolean),
	);

	function post(url, payload) {
		return fetch(url, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Requested-With": "XMLHttpRequest",
			},
			body: JSON.stringify(payload),
		}).then((r) => r.json().then((j) => ({ ok: r.ok, body: j })));
	}

	function errorText(body) {
		if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join("; ");
		return body.error || body.message || "failed";
	}

	const keyOf = (row) => ({
		company: row.dataset.company,
		role: row.dataset.role,
	});

	function feedback(form, text, kind) {
		const el = form.querySelector("[data-interview-feedback]");
		if (!el) return;
		el.textContent = text;
		el.className = `run-status ${kind}`;
	}

	function setCounts(counts) {
		if (!counts) return;
		for (const el of page.querySelectorAll("[data-interview-count]")) {
			const key = el.dataset.interviewCount;
			if (key in counts) el.textContent = String(counts[key]);
		}
	}

	function paintStatus(row, data) {
		const status = row.querySelector("[data-interview-status]");
		if (status) {
			status.textContent = data.status_label;
			status.className = `badge ${data.status_badge}`;
		}
		const priority = row.querySelector("[data-interview-priority]");
		if (priority) {
			priority.textContent = `${data.priority_label} priority`;
			priority.className = `badge ${data.priority_badge}`;
		}
	}

	function paintNext(row, data) {
		const line = row.querySelector("[data-interview-next]");
		if (!line) return;
		line.hidden = !data.next_step;
		row.querySelector("[data-interview-next-task]").textContent = data.next_step
			? data.next_step.task
			: "";
		row.querySelector("[data-interview-next-date]").textContent = data.next_step
			? data.next_step.date
			: "";
		row.querySelector("[data-interview-overdue]").hidden = !data.overdue;
	}

	function paintSignal(row, data) {
		const line = row.querySelector("[data-interview-last]");
		if (!line || !data.last_event) return;
		line.hidden = false;
		row.querySelector("[data-interview-last-date]").textContent = data.last_event.date;
		row.querySelector("[data-interview-last-stage]").textContent = data.last_event.stage
			? ` \u2014 ${data.last_event.stage}`
			: "";
	}

	// Status/priority selects save immediately; a status change can move the row.
	for (const select of page.querySelectorAll("[data-interview-select]")) {
		select.dataset.initial = select.value;
	}

	page.addEventListener("change", (e) => {
		const select = e.target.closest("[data-interview-select]");
		if (!select) return;
		const row = select.closest("[data-interview]");
		const status = row.querySelector("[data-interview-field-status]");
		select.disabled = true;
		post("/api/interviews/field", {
			...keyOf(row),
			field: select.dataset.interviewSelect,
			value: select.value,
		})
			.then(({ ok, body }) => {
				if (!ok) {
					select.value = select.dataset.initial;
					select.disabled = false;
					if (status) {
						status.textContent = errorText(body);
						status.className = "run-status is-failed";
					}
					return;
				}
				select.dataset.initial = select.value;
				select.disabled = false;
				paintStatus(row, body.row);
				setCounts(body.counts);
				// Closed threads leave the live cards for the collapsed Closed list;
				// reopening a row sends it back to the card its new status belongs to.
				let target
				if (closedStatuses.has(body.row.status)) {
					target = page.querySelector("[data-interview-list-closed]");
				} else {
					const sectionKey = activeStatuses.has(body.row.status) ? "active" : "leads";
					target = page.querySelector(
						`[data-interview-section="${sectionKey}"] [data-interview-list]`,
					);
				}
				if (target) {
					if (row.parentElement !== target) target.appendChild(row);
				} else if (closedStatuses.has(body.row.status)) {
					// No Closed list on the page yet; the next load will show it.
					row.remove();
				}
				if (status) {
					status.textContent = "Saved.";
					status.className = "run-status is-done";
				}
			})
			.catch(() => {
				select.value = select.dataset.initial;
				select.disabled = false;
				if (status) {
					status.textContent = "network error";
					status.className = "run-status is-failed";
				}
			});
	});

	page.addEventListener("submit", (e) => {
		const form = e.target;
		const row = form.closest("[data-interview]");
		if (!row) return;

		if (form.matches("[data-interview-next-form]")) {
			e.preventDefault();
			const fields = form.elements;
			feedback(form, "Saving\u2026", "is-running");
			post("/api/interviews/next-step", {
				...keyOf(row),
				task: fields.task.value,
				date: fields.date.value,
			})
				.then(({ ok, body }) => {
					if (!ok) {
						feedback(form, errorText(body), "is-failed");
						return;
					}
					paintNext(row, body.row);
					feedback(form, "Next action saved.", "is-done");
				})
				.catch(() => feedback(form, "network error", "is-failed"));
			return;
		}

		if (form.matches("[data-interview-signal-form]")) {
			e.preventDefault();
			const fields = form.elements;
			feedback(form, "Logging\u2026", "is-running");
			post("/api/interviews/timeline", {
				...keyOf(row),
				date: fields.date.value,
				stage: fields.stage.value,
				notes: fields.notes.value,
			})
				.then(({ ok, body }) => {
					if (!ok) {
						feedback(form, errorText(body), "is-failed");
						return;
					}
					paintSignal(row, body.row);
					fields.stage.value = "";
					fields.notes.value = "";
					feedback(form, "Signal logged.", "is-done");
				})
				.catch(() => feedback(form, "network error", "is-failed"));
			return;
		}

		if (form.matches("[data-interview-notes-form]")) {
			e.preventDefault();
			feedback(form, "Saving\u2026", "is-running");
			post("/api/interviews/text", {
				...keyOf(row),
				field: "interview_notes",
				text: form.elements.notes.value,
			})
				.then(({ ok, body }) => {
					feedback(
						form,
						ok ? "Notes saved." : errorText(body),
						ok ? "is-done" : "is-failed",
					);
				})
				.catch(() => feedback(form, "network error", "is-failed"));
		}
	});

	// New application: appended to the tracker, then reloaded so the server's
	// ordering and counts are the ones on screen.
	// ── Agents on the Interviews tab ──────────────────────────
	// A row button only fills the matching runner card; the card's own run
	// button starts the agent, so no model call happens on a stray tap.
	page.addEventListener("click", (e) => {
		const fill = e.target.closest("[data-agent-fill]");
		if (fill) {
			const item = page.querySelector(
				`#interviewAgents .run-item[data-skill="${CSS.escape(fill.dataset.agentFill)}"]`,
			);
			const input = item && item.querySelector("[data-run-input]");
			if (!input) return;
			input.value = fill.dataset.agentInput;
			item.scrollIntoView({ block: "center" });
			(item.querySelector("[data-run]") || input).focus();
			return;
		}
		const lead = e.target.closest("[data-agent-lead]");
		if (!lead || lead.disabled) return;
		const status = document.getElementById("interviewLeadStatus");
		const say = (text, cls) => {
			status.textContent = text;
			status.className = `run-status ${cls}`;
		};
		lead.disabled = true;
		say("Adding\u2026", "is-running");
		post("/api/interviews/create", {
			company: lead.dataset.company,
			role: lead.dataset.role,
			status: "new_lead",
			priority: "medium",
			location: lead.dataset.location,
			salary_range: lead.dataset.salary,
			job_url: lead.dataset.url,
		})
			.then(({ ok, body }) => {
				if (!ok) {
					say(errorText(body), "is-failed");
					lead.disabled = false;
					return;
				}
				window.location.reload();
			})
			.catch(() => {
				say("network error", "is-failed");
				lead.disabled = false;
			});
	});

	const addForm = document.getElementById("interviewAddForm");
	const addStatus = document.getElementById("interviewAddStatus");
	if (addForm) {
		addForm.addEventListener("submit", (e) => {
			e.preventDefault();
			const f = addForm.elements;
			addStatus.textContent = "Adding\u2026";
			addStatus.className = "run-status is-running";
			const button = addForm.querySelector("button[type=submit]");
			button.disabled = true;
			post("/api/interviews/create", {
				company: f.company.value,
				role: f.role.value,
				status: f.status.value,
				priority: f.priority.value,
				location: f.location.value,
				salary_range: f.salary_range.value,
				job_url: f.job_url.value,
				next_step: f.next_step.value,
				date: f.date.value,
			})
				.then(({ ok, body }) => {
					if (!ok) {
						addStatus.textContent = errorText(body);
						addStatus.className = "run-status is-failed";
						button.disabled = false;
						return;
					}
					window.location.reload();
				})
				.catch(() => {
					addStatus.textContent = "network error";
					addStatus.className = "run-status is-failed";
					button.disabled = false;
				});
		});
	}

	// ── Interview mode dialog ─────────────────────────────────
	// One application, everything needed while the call is live: who you are
	// talking to, resume/posting/prep links, the tracker's job-fit notes, the
	// history, and three editable blocks (questions, preparation, notes).
	const dialog = document.getElementById("interviewMode");
	if (dialog) {
		const $ = (id) => document.getElementById(id);
		const fields = {
			interview_questions: $("interviewModeQuestions"),
			interview_preparation: $("interviewModePreparation"),
			interview_notes: $("interviewModeNotes"),
		};
		const el = (tag, className, text) => {
			const node = document.createElement(tag);
			if (className) node.className = className;
			if (text) node.textContent = text;
			return node;
		};

		function fileLink(label, href, note) {
			const row = el("div", "interview-dialog-file");
			if (href) {
				const a = el("a", "interview-dialog-file-link", label);
				a.href = href;
				a.target = "_blank";
				a.rel = "noopener noreferrer";
				row.appendChild(a);
			} else {
				row.appendChild(el("span", "interview-dialog-file-link is-missing", label));
			}
			if (note) row.appendChild(el("span", "interview-dialog-file-note", note));
			return row;
		}

		function paint(row) {
			$("interviewModeTitle").textContent = row.company;
			$("interviewModeRole").textContent = row.role;
			const meta = [row.status_label, row.location, row.salary]
				.filter(Boolean)
				.join(" \u00b7 ");
			$("interviewModeMeta").textContent = meta;

			const resume = $("interviewModeResume");
			resume.hidden = !row.resume_href;
			if (row.resume_href) resume.href = row.resume_href;
			const posting = $("interviewModePosting");
			posting.hidden = !row.url;
			if (row.url) posting.href = row.url;
			if (row.sheet_href) $("interviewModeSheet").href = row.sheet_href;

			const contacts = $("interviewModeContacts");
			contacts.textContent = "";
			for (const c of row.contacts || []) {
				const line = el("div", "interview-dialog-contact");
				line.appendChild(el("strong", "", c.name || "Contact"));
				if (c.role) line.appendChild(el("span", "interview-dialog-contact-role", c.role));
				if (c.email) {
					const mail = el("a", "interview-dialog-contact-email", c.email);
					mail.href = `mailto:${c.email}`;
					line.appendChild(mail);
				}
				contacts.appendChild(line);
			}
			$("interviewModeNoContacts").hidden = (row.contacts || []).length > 0;

			const files = $("interviewModeFiles");
			files.textContent = "";
			if (row.resume) {
				files.appendChild(
					fileLink(row.resume.split("/").pop(), row.resume_href, row.resume_href ? "resume/" + row.resume : "missing under resume/"),
				);
			}
			for (const f of row.prep_files || []) {
				files.appendChild(fileLink(f.label, f.href, f.href ? "" : "recorded, file missing"));
			}
			if (!files.children.length) {
				files.appendChild(el("p", "interview-dialog-hint", "No resume or prep files recorded for this application."));
			}

			// Job Reader's extraction, when one exists for this row. Text only.
			const reading = $("interviewModeReading");
			reading.textContent = "";
			const sections = (row.agent && row.agent.reading && row.agent.reading.sections) || [];
			for (const s of sections) {
				reading.appendChild(el("p", "interview-dialog-hint", s.label));
				const list = el("ul", "interview-dialog-history");
				for (const text of s.items) list.appendChild(el("li", "interview-dialog-event", text));
				reading.appendChild(list);
			}
			$("interviewModeReadingSection").hidden = !sections.length;

			const fit = $("interviewModeFitSection");
			fit.hidden = !row.fit_notes;
			$("interviewModeFit").textContent = row.fit_notes || "";

			const history = $("interviewModeHistory");
			history.textContent = "";
			for (const h of row.history || []) {
				const item = el("li", "interview-dialog-event");
				item.appendChild(el("span", "interview-dialog-event-date", h.date));
				item.appendChild(el("span", "interview-dialog-event-stage", h.stage));
				if (h.notes) item.appendChild(el("span", "interview-dialog-event-notes", h.notes));
				history.appendChild(item);
			}
			$("interviewModeHistorySection").hidden = !(row.history || []).length;

			for (const [field, input] of Object.entries(fields)) {
				input.value = row[
					field === "interview_questions"
						? "questions"
						: field === "interview_preparation"
							? "preparation"
							: "notes"
				] || "";
				input.dataset.initial = input.value;
			}
		}

		function open(row) {
			dialog.dataset.company = row.company;
			dialog.dataset.role = row.role;
			paint(row);
			for (const status of dialog.querySelectorAll("[data-interview-dialog-status]")) {
				status.textContent = "";
				status.className = "run-status";
			}
			if (typeof dialog.showModal === "function") dialog.showModal();
			else dialog.setAttribute("open", "");
		}

		// Never leave the previous application's text on screen: during a call,
		// stale notes would read as if they belonged to this one.
		function fail(reason) {
			dialog.dataset.company = "";
			$("interviewModeTitle").textContent = "Could not load this application";
			$("interviewModeRole").textContent = reason;
			$("interviewModeMeta").textContent = "";
			$("interviewModeContacts").textContent = "";
			$("interviewModeNoContacts").hidden = true;
			$("interviewModeFiles").textContent = "";
			$("interviewModeFitSection").hidden = true;
			$("interviewModeHistorySection").hidden = true;
			$("interviewModeResume").hidden = true;
			$("interviewModePosting").hidden = true;
			for (const input of Object.values(fields)) input.value = "";
			if (typeof dialog.showModal === "function") dialog.showModal();
		}

		// One fetch path for both entry points: a pipeline row's button and
		// Today's “Interview mode” quick action.
		function openFor(company, role) {
			const query = new URLSearchParams({ company, role }).toString();
			fetch(`/api/interviews/detail?${query}`)
				.then((r) => r.json().then((j) => ({ ok: r.ok, body: j })))
				.then(({ ok, body }) => (ok ? open(body.row) : fail(errorText(body))))
				.catch(() => fail("network error"));
		}

		page.addEventListener("click", (e) => {
			const trigger = e.target.closest("[data-interview-mode]");
			if (!trigger) return;
			const row = trigger.closest("[data-interview]");
			if (!row) return;
			openFor(row.dataset.company, row.dataset.role);
		});

		// Today's quick action: the href switches to the Interviews tab, and the
		// dialog opens on top of it without a reload.
		document.addEventListener("click", (e) => {
			const trigger = e.target.closest("[data-interview-open]");
			if (!trigger) return;
			const [company, role] = (trigger.dataset.interviewOpen || "").split("|");
			if (company && role) openFor(company, role);
		});

		dialog.addEventListener("click", (e) => {
			if (e.target.closest("[data-close-interview]")) {
				dialog.close();
				return;
			}
			const save = e.target.closest("[data-interview-save]");
			if (!save) return;
			const field = save.dataset.interviewSave;
			const input = fields[field];
			const status = save.parentElement.querySelector("[data-interview-dialog-status]");
			if (!input || !dialog.dataset.company) return;
			save.disabled = true;
			status.textContent = "Saving\u2026";
			status.className = "run-status is-running";
			post("/api/interviews/text", {
				company: dialog.dataset.company,
				role: dialog.dataset.role,
				field,
				text: input.value,
			})
				.then(({ ok, body }) => {
					save.disabled = false;
					if (!ok) {
						status.textContent = errorText(body);
						status.className = "run-status is-failed";
						return;
					}
					input.dataset.initial = input.value;
					status.textContent = "Saved.";
					status.className = "run-status is-done";
					// The page's own notes box shows the same field.
					if (field === "interview_notes") {
						const row = [...page.querySelectorAll("[data-interview]")].find(
							(r) =>
								r.dataset.company === dialog.dataset.company &&
								r.dataset.role === dialog.dataset.role,
						);
						const pageNotes = row && row.querySelector("textarea[name=notes]");
						if (pageNotes) pageNotes.value = input.value;
					}
				})
				.catch(() => {
					save.disabled = false;
					status.textContent = "network error";
					status.className = "run-status is-failed";
				});
		});
	}
})();
