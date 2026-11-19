document.addEventListener("DOMContentLoaded", () => {
	var tabs = Array.from(document.querySelectorAll('.section-nav [role="tab"]'));
	var panels = document.querySelectorAll('[role="tabpanel"]');

	var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
	var pageTransition = null;
	var pendingApply = null;

	// Smooth page-to-page change (washi ↔ deck/spatial): the incoming face
	// expands in a circular wipe from the tab that triggered it, so dark→light
	// and light→dark read as one world opening over the other. Reduced motion,
	// no View Transitions, or a transition already in flight: instant, as before.
	// A request that arrives mid-flight applies immediately and cancels the
	// queued apply, so rapid clicks never snap back to a stale tab.
	function withPageTransition(origin, mutate) {
		if (!origin || !document.startViewTransition || reduceMotion.matches || pageTransition) {
			pendingApply = null;
			mutate();
			return;
		}
		pendingApply = mutate;
		pageTransition = document.startViewTransition(() => {
			const apply = pendingApply;
			pendingApply = null;
			if (apply) apply();
		});
		const clear = () => {
			pageTransition = null;
		};
		pageTransition.finished.then(clear, clear);
		pageTransition.ready
			.then(() => {
				const radius = Math.hypot(
					Math.max(origin.x, innerWidth - origin.x),
					Math.max(origin.y, innerHeight - origin.y),
				);
				document.documentElement.animate(
					{
						clipPath: [
							`circle(0px at ${origin.x}px ${origin.y}px)`,
							`circle(${radius}px at ${origin.x}px ${origin.y}px)`,
						],
					},
					{
						duration: 460,
						easing: "cubic-bezier(0.4, 0, 0.2, 1)",
						pseudoElement: "::view-transition-new(root)",
					},
				);
			})
			.catch(() => {});
	}

	function tabOrigin(tab, event) {
		if (event && (event.clientX || event.clientY)) {
			return { x: event.clientX, y: event.clientY };
		}
		const rect = tab.getBoundingClientRect();
		return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
	}

	function activateTab(tab, updateHash, origin) {
		const mutate = () => {
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
		};
		if (origin) withPageTransition(origin, mutate);
		else mutate();
	}

	// Click handler
	tabs.forEach((tab) => {
		tab.addEventListener("click", (e) => {
			activateTab(tab, undefined, tabOrigin(tab, e));
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
				activateTab(next, undefined, tabOrigin(next));
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
		if (t) activateTab(t, false, tabOrigin(t));
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

	// Today repeats Next up and Inbox rows; count each task once. The later
	// Tasks-tab copy wins because it carries the category pill.
	var taskRows = Array.from(
		new Map(
			Array.from(
				document.querySelectorAll(".task-check[data-realm]"),
				(box) => [box.dataset.realm + ":" + box.dataset.line, box],
			),
		).values(),
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

// ── Workspace map deep links ────────────────────────────────
// Any link with data-map-query (Today: Recent artifacts) points the embedded
// viewer at that filter, e.g. "folder=artifacts"; its href switches the tab.
document.addEventListener("click", (e) => {
	const link = e.target.closest("[data-map-query]");
	const frame = document.getElementById("workspaceMapFrame");
	if (link && frame) frame.src = "/workspace-map/?" + link.dataset.mapQuery;
});

// Today → Shortcuts → Find a file: hand the text to the map and switch tabs.
document.getElementById("mapFindForm")?.addEventListener("submit", (e) => {
	e.preventDefault();
	const q = e.target.elements.q.value.trim();
	const frame = document.getElementById("workspaceMapFrame");
	if (frame) frame.src = "/workspace-map/" + (q ? "?q=" + encodeURIComponent(q) : "");
	window.location.hash = "#workspace-map";
});

// A Daily row with data-focus (Today: Second brain) jumps to that control.
document.addEventListener("click", (e) => {
	const link = e.target.closest("[data-focus]");
	const target = link && document.getElementById(link.dataset.focus);
	if (!target) return;
	e.preventDefault();
	target.focus();
});
