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

/** Persist a checkbox via /api/tasks/toggle. Global so the Today page can
 *  bind rows it adds after a capture. */
function bindTaskCheck(box) {
	function handleToggle() {
		var isDone = box.dataset.done === "true";
		var newDone = !isDone;
		var twins = sameTaskChecks(box);

		// Optimistic UI update
		twins.forEach((b) => paintTaskCheck(b, newDone));

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
				if (!res.ok) return revert();
				// The server may have followed the task to a new line.
				return res.json().then((j) => {
					twins.forEach((b) => {
						b.dataset.line = String(j.line);
					});
				});
			})
			.catch(revert);

		function revert() {
			twins.forEach((b) => paintTaskCheck(b, isDone));
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
	let providerModels = {};   // {claude: [...], codex: [...], opencode: [...], openrouter: [...]}
	let providerAvailable = {}; // {claude: true, codex: true, ...}
	let runnerEfforts = [];     // effort options for the currently selected model

	/** Make an element with optional class and text. Text is always set via
	 *  textContent, so no value can ever be parsed as markup. */
	function el(tag, cls, text) {
		const node = document.createElement(tag);
		if (cls) node.className = cls;
		if (text !== undefined) node.textContent = text;
		return node;
	}

	/** Human-readable label for a model value ("claude:sonnet" or "sonnet"). */
	function modelLabel(value) {
		const [p, id] = String(value).split(":");
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
		btn.hidden = !path;
		return btn;
	}

	function renderItem(s) {
		const item = el("div", "run-item");
		item.dataset.skill = s.id;

		const head = el("div", "run-item-head");
		const icon = el("span", "run-item-icon", s.icon);
		icon.setAttribute("aria-hidden", "true");
		const text = el("div", "run-item-text");
		text.appendChild(el("h4", null, s.label));
		text.appendChild(el("p", null, s.blurb));
		head.append(icon, text);
		item.appendChild(head);

		if (s.input_label) {
			const field = el("label", "run-field");
			field.appendChild(el("span", "run-field-label", s.input_label));
			const input = el("input", "run-input");
			input.type = s.input_type || "url";
			input.placeholder = s.input_label;
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
			const providerLabel = (p) =>
				p === "claude"
					? "Claude"
					: p.charAt(0).toUpperCase() + p.slice(1) + " \u2014 local catalogue";
			let defaultValue = `claude:${s.model || "sonnet"}`;
			for (const [provider, models] of Object.entries(providerModels)) {
				if (!models || !models.length) continue;
				const optgroup = document.createElement("optgroup");
				optgroup.label = providerLabel(provider);
				for (const m of models) {
					const option = el(
						"option",
						null,
						provider === "claude" ? m.label : `${provider} \u00b7 ${m.label}`
					);
					option.value = provider === "claude" ? m.id : `${provider}:${m.id}`;
					option.selected = option.value === defaultValue;
					optgroup.appendChild(option);
				}
				modelPicker.appendChild(optgroup);
			}
			modelField.appendChild(modelPicker);
			options.appendChild(modelField);

			// ── Effort picker (options depend on the selected model) ──
			const effortField = el("label", "run-field");
			effortField.appendChild(el("span", "run-field-label", "Effort"));
			const effortPicker = el("select", "run-select");
			effortPicker.dataset.runEffort = "";
			function setEffortOptions(modelValue) {
				const [p, id] = String(modelValue).split(":");
				const list =
					providerModels[p]?.find((m) => m.id === id)?.efforts || runnerEfforts;
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
		}

		const foot = el("div", "run-item-foot");
		const btn = el("button", "action-btn", "Run");
		btn.type = "button";
		btn.setAttribute("aria-label", `Run ${s.label}`);
		btn.dataset.run = s.id;
		const status = el(
			"span",
			"run-status",
			s.kind === "shell"
				? "no model \u00b7 $0"
				: `default: ${modelLabel(s.model || "sonnet")}`,
		);
		status.dataset.statusFor = s.id;
		status.setAttribute("role", "status");
		status.setAttribute("aria-live", "polite");
		const view = outputButton(null, s.label);
		view.dataset.viewFor = s.id;
		foot.append(btn, view, status);
		item.appendChild(foot);
		const path = el("code", "run-output-path");
		path.dataset.pathFor = s.id;
		path.hidden = true;
		item.appendChild(path);
		return item;
	}

	// ── Render the buttons from the server catalog ──────────────
	// A grid with data-skills="a,b" shows only those runners, in that order.
	function loadCatalog() {
		return fetch("/api/skills/catalog")
			.then((r) => r.json())
			.then((data) => {
				providerModels = data.provider_models || {};
				providerAvailable = data.provider_available || {};
				runnerEfforts = data.effort || [];
				const byId = new Map(data.skills.map((s) => [s.id, s]));
				for (const grid of grids) {
					clear(grid);
					const only = grid.dataset.skills;
					const list = only
						? only.split(",").map((id) => byId.get(id)).filter(Boolean)
						: data.skills;
					for (const s of list) grid.appendChild(renderItem(s));
				}
				poll(); // paint status of runs already in flight
			})
			.catch(() => {
				for (const grid of grids) {
					clear(grid);
					grid.appendChild(el("p", "run-empty", "Could not load skill catalog."));
				}
			});
	}

	loadCatalog();

	// ── Refresh model catalogues (Update models button) ───────────
	const refreshBtn = document.getElementById("refreshModels");
	if (refreshBtn) {
		refreshBtn.addEventListener("click", () => {
			refreshBtn.disabled = true;
			refreshBtn.textContent = "Updating\u2026";
			loadCatalog().finally(() => {
				refreshBtn.disabled = false;
				refreshBtn.textContent = "Update models";
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
		const setAll = (text, cls) =>
			statusEls(skill).forEach((s) => {
				s.textContent = text;
				s.className = `run-status ${cls}`;
			});

		btn.disabled = true;
		setAll("starting\u2026", "is-running");

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
					btn.disabled = false;
					return;
				}
				setAll("running\u2026", "is-running");
				poll();
			})
			.catch(() => {
				setAll("network error", "is-failed");
				btn.disabled = false;
			});
	});

	// ── Poll while anything is running ──────────────────────────
	function poll() {
		fetch("/api/skills/runs")
			.then((r) => r.json())
			.then((data) => {
				renderHistory(data.runs);

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
						s.textContent = running
							? "running\u2026"
							: `${run.status} \u00b7 ${run.duration}`;
						s.className = `run-status is-${run.status}`;
					});
					document.querySelectorAll(`[data-run="${sel}"]`).forEach((b) => {
						b.disabled = running;
					});
					document.querySelectorAll(`[data-view-for="${sel}"]`).forEach((v) => {
						v.dataset.output = run.output || "";
						v.hidden = !run.output;
					});
					document.querySelectorAll(`[data-path-for="${sel}"]`).forEach((p) => {
						p.textContent = run.output || "";
						p.hidden = !run.output;
					});
				}

				if (anyRunning && !pollTimer) {
					pollTimer = setInterval(poll, 2000);
				} else if (!anyRunning && pollTimer) {
					clearInterval(pollTimer);
					pollTimer = null;
				}
			})
			.catch(() => {});
	}

	function renderHistory(runs) {
		if (!history || !runs.length) return;
		clear(history);
		for (const r of runs) {
			const row = el("div", "run-log-row");
			const dot = el("span", `run-log-dot is-${r.status}`);
			dot.setAttribute("aria-hidden", "true");
			const out = el("span", "run-log-out");
			if (r.output) out.appendChild(outputButton(r.output, `${r.label} \u00b7 ${r.started}`));
			else out.textContent = "\u2014";
			row.append(
				dot,
				el("span", "run-log-label", r.label),
				el("span", "run-log-time", r.started),
				el("span", "run-log-dur", r.duration || (r.status === "running" ? "running\u2026" : "\u2014")),
				out,
			);
			history.appendChild(row);
		}
	}

	// ── Output viewer ───────────────────────────────────────────
	if (dialog) {
		const body = document.getElementById("runOutputBody");
		const title = document.getElementById("runOutputTitle");
		document.addEventListener("click", (e) => {
			const btn = e.target.closest("[data-output]");
			if (!btn || !btn.dataset.output) return;
			title.textContent = `${btn.dataset.outputLabel || "Run output"} — ${btn.dataset.output}`;
			body.textContent = "Loading\u2026";
			dialog.showModal();
			fetch(`/api/file?path=${encodeURIComponent(btn.dataset.output)}`)
				.then((r) => r.json())
				.then((j) => {
					body.textContent = j.content ?? j.error ?? "No output.";
				})
				.catch(() => {
					body.textContent = "Could not load output.";
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
