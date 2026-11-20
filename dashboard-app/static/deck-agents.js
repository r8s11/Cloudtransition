// Deck: agents tab interactions. Loaded after app.js.
// List–detail directory: filter, select-and-update, keyboard flow. Read-only.
(() => {
	const page = document.getElementById("page-agents");
	const root = page && page.querySelector("[data-agents]");
	if (!root) return;

	const list = root.querySelector("#agentsList");
	const detail = root.querySelector("#agentsDetail");
	const items = Array.from(list.querySelectorAll("[data-agent-item]"));
	const panes = Array.from(detail.querySelectorAll("[data-agent-pane]"));
	const search = page.querySelector("#agentsFilter");
	const segments = Array.from(page.querySelectorAll("[data-agents-view]"));
	const empty = list.querySelector("[data-agents-empty]");
	const count = page.querySelector("[data-agents-count]");
	const narrow = window.matchMedia("(max-width: 960px)");
	const KEY = "deck.agents.selected";
	let view = "all";
	let current = null;

	const rowOf = (item) => item.querySelector("[data-agent-row]");
	const itemOf = (slug) => items.find((i) => i.dataset.agentItem === slug);
	const visible = () => items.filter((i) => !i.hidden);

	function select(slug, persist = true) {
		const item = itemOf(slug);
		if (!item) return;
		current = slug;
		for (const i of items) {
			const row = rowOf(i);
			const on = i === item;
			row.classList.toggle("is-selected", on);
			row.tabIndex = on ? 0 : -1;
			if (on) row.setAttribute("aria-current", "true");
			else row.removeAttribute("aria-current");
		}
		for (const pane of panes) pane.hidden = pane.dataset.agentPane !== slug;
		if (persist) {
			try {
				sessionStorage.setItem(KEY, slug);
			} catch {
				// Private mode: selection simply is not remembered.
			}
		}
	}

	function focusRow() {
		const item = itemOf(current);
		if (item && !item.hidden) rowOf(item).focus();
		else if (visible().length) rowOf(visible()[0]).focus();
		else search.focus();
	}

	function move(to) {
		const shown = visible();
		if (!shown.length) return;
		const at = shown.findIndex((i) => i.dataset.agentItem === current);
		let next;
		if (to === "first") next = 0;
		else if (to === "last") next = shown.length - 1;
		else next = at < 0 ? 0 : Math.min(shown.length - 1, Math.max(0, at + to));
		select(shown[next].dataset.agentItem);
		rowOf(shown[next]).focus();
	}

	function openDetail() {
		const pane = panes.find((p) => p.dataset.agentPane === current);
		if (!pane) return;
		if (narrow.matches) detail.scrollIntoView({ block: "start" });
		pane.focus({ preventScroll: !narrow.matches });
	}

	function matches(item, q) {
		if (q && !item.dataset.search.includes(q)) return false;
		if (view === "runnable") return item.dataset.runnable === "1";
		if (view === "warnings") return item.dataset.warnings !== "0";
		if (view === "nohub") return item.dataset.hub === "0";
		return true;
	}

	function applyFilter() {
		const q = search.value.trim().toLowerCase();
		for (const item of items) item.hidden = !matches(item, q);
		const shown = visible();
		empty.hidden = shown.length > 0;
		count.textContent = shown.length
			? `${shown.length} of ${items.length} agents shown`
			: "No agent matches this filter.";
		if (shown.length && !shown.some((i) => i.dataset.agentItem === current)) {
			select(shown[0].dataset.agentItem);
		}
	}

	function setView(name) {
		view = name;
		for (const b of segments) b.setAttribute("aria-pressed", String(b.dataset.agentsView === name));
		applyFilter();
	}

	list.addEventListener("click", (e) => {
		const row = e.target.closest("[data-agent-row]");
		if (!row) return;
		select(row.dataset.agentRow);
		if (narrow.matches) openDetail();
	});
	for (const b of segments) b.addEventListener("click", () => setView(b.dataset.agentsView));
	search.addEventListener("input", applyFilter);
	page.querySelector("[data-agents-clear]").addEventListener("click", () => {
		search.value = "";
		setView("all");
		search.focus();
	});
	page.querySelector("[data-agents-back]").addEventListener("click", focusRow);
	page.addEventListener("click", (e) => {
		const btn = e.target.closest("[data-agents-scroll]");
		const target = btn && document.getElementById(btn.dataset.agentsScroll);
		if (!target) return;
		target.scrollIntoView({ block: "start" });
		target.focus({ preventScroll: true });
	});

	const editable = (el) =>
		el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));

	document.addEventListener("keydown", (e) => {
		if (!page.classList.contains("active") || e.defaultPrevented) return;
		if (e.metaKey || e.ctrlKey || e.altKey) return;
		if (document.querySelector("dialog[open]")) return;
		const t = e.target;

		if (t === search) {
			if (e.key === "ArrowDown" || e.key === "Enter") {
				e.preventDefault();
				focusRow();
			} else if (e.key === "Escape") {
				e.preventDefault();
				if (search.value) {
					search.value = "";
					applyFilter();
				} else {
					focusRow();
				}
			}
			return;
		}
		if (editable(t)) return;

		if (e.key === "/") {
			e.preventDefault();
			search.focus();
			search.select();
			return;
		}
		if (e.key === "Escape" && detail.contains(t)) {
			e.preventDefault();
			focusRow();
			return;
		}
		const inList = list.contains(t);
		// j/k also work with nothing focused; arrows, Home and End keep page scrolling outside the list.
		if (!inList && !((t === document.body || t === page) && (e.key === "j" || e.key === "k"))) return;

		switch (e.key) {
			case "ArrowDown":
			case "j":
				e.preventDefault();
				move(1);
				break;
			case "ArrowUp":
			case "k":
				e.preventDefault();
				move(-1);
				break;
			case "Home":
				e.preventDefault();
				move("first");
				break;
			case "End":
				e.preventDefault();
				move("last");
				break;
			case "Enter": {
				const row = inList && t.closest("[data-agent-row]");
				if (!row) break;
				e.preventDefault();
				select(row.dataset.agentRow);
				openDetail();
				break;
			}
		}
	});

	let saved = null;
	try {
		saved = sessionStorage.getItem(KEY);
	} catch {
		// No storage: fall back to the server default.
	}
	select(itemOf(saved) ? saved : root.dataset.default, false);
})();
