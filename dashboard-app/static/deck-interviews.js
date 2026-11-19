// Interviews: list–detail selection, filter, stage segments and keyboard.
// Edits still go through app.js; this file only decides which entry shows.
(() => {
	const page = document.getElementById("page-interviews");
	const list = page && page.querySelector("[data-iv-list]");
	if (!list) return;

	const detail = page.querySelector("[data-iv-detail]");
	const filter = page.querySelector("[data-iv-filter]");
	const empty = page.querySelector("[data-iv-empty]");
	const segments = [...page.querySelectorAll("[data-iv-segment]")];
	const KEY = "interviews.selected";
	const SEG_KEY = "interviews.segment";
	const set = (name) => new Set((page.dataset[name] || "").split(",").filter(Boolean));
	const active = set("interviewActive");
	const waiting = set("interviewWaiting");
	const closed = set("interviewClosed");

	const TONES = {
		offer: "ok", onsite: "ok", interviewing: "ok",
		screening: "info", assessment: "info", applied: "info",
		waiting: "warn",
	};
	const groupOf = (status) =>
		closed.has(status) ? "closed" : waiting.has(status) ? "waiting" : active.has(status) ? "active" : "leads";

	const rows = () => [...list.querySelectorAll("[data-iv-row]")];
	const entryFor = (key) =>
		[...page.querySelectorAll("[data-interview]")].find((e) => e.dataset.key === key) || null;
	const rowFor = (key) => rows().find((r) => r.dataset.key === key) || null;
	const narrow = () => window.matchMedia("(max-width: 960px)").matches;
	let segment = "all";
	let current = null;

	// Deck shows the editor open: the update controls are always in reach.
	for (const tools of page.querySelectorAll(".interview-tools")) tools.open = true;
	// Status, priority and next action sit right under the title, above the
	// pipeline; the signal and notes forms stay below. Same elements, so the
	// app.js handlers keep working.
	for (const entry of page.querySelectorAll("[data-interview]")) {
		const main = entry.querySelector(".interview-main");
		const status = entry.querySelector(".interview-group-status");
		const next = entry.querySelector("form[data-interview-next-form]");
		if (!main || !status) continue;
		const quick = document.createElement("div");
		quick.className = "iv-quick";
		quick.append(status);
		if (next) quick.append(next);
		main.after(quick);
	}
	const closedDetails = page.querySelector("details.interview-closed");
	if (closedDetails) closedDetails.open = true;

	function paintRow(row) {
		const status = row.dataset.status;
		const overdue = row.dataset.overdue === "true";
		const dot = row.querySelector("[data-iv-dot]");
		if (dot) dot.dataset.tone = overdue && !closed.has(status) ? "bad" : TONES[status] || "neutral";
		const flag = row.querySelector(".iv-overdue");
		if (flag) flag.hidden = !overdue || closed.has(status);
	}

	const needsAction = (row) =>
		row.dataset.group === "active" || (row.dataset.overdue === "true" && row.dataset.group !== "closed");

	function inSegment(row) {
		if (segment === "all") return true;
		if (segment === "needs") return needsAction(row);
		return row.dataset.group === segment;
	}

	function counts() {
		const all = rows();
		const c = { all: all.length, needs: all.filter(needsAction).length };
		for (const g of ["active", "leads", "waiting", "closed"]) c[g] = all.filter((r) => r.dataset.group === g).length;
		for (const el of page.querySelectorAll("[data-iv-count]")) el.textContent = String(c[el.dataset.ivCount] ?? "");
		return c;
	}

	function regroup(row) {
		const header = list.querySelector(`[data-iv-group="${row.dataset.group}"]`);
		if (!header) return;
		// Insert after the last row of that group (or right after its header).
		let anchor = header;
		let next = header.nextElementSibling;
		while (next && next.matches("[data-iv-row]")) {
			if (next !== row) anchor = next;
			next = next.nextElementSibling;
		}
		if (anchor.nextElementSibling !== row) anchor.after(row);
	}

	// ── Overdrive: stage flow ──────────────────────────────────────────
	// A status change slides the row into its new group (FLIP), rolls the
	// stage counts like an odometer and cross-fades the detail badge.
	// Reduced motion / no WAAPI: everything stays instant.
	const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
	const canAnimate = () => !reduceMotion.matches && typeof Element.prototype.animate === "function";
	const FLOW_EASE = "cubic-bezier(0.16, 1, 0.3, 1)";
	// Segment counts also change on ordinary filtering; mark them during a
	// stage flow so only those rolls animate. Marks survive until the async
	// MutationObserver callback consumes them.
	function markFlow() {
		for (const el of page.querySelectorAll("[data-iv-count]")) el.dataset.flow = "1";
	}

	function rollCount(el, oldText, newText) {
		if (!canAnimate() || el.querySelector(".iv-odo")) return;
		const oldN = Number(oldText);
		const newN = Number(newText);
		if (!Number.isFinite(oldN) || !Number.isFinite(newN) || oldN === newN) return;
		const up = newN > oldN;
		const digits = Math.max(String(oldN).length, String(newN).length);
		const track = document.createElement("span");
		track.className = "iv-odo";
		track.style.minWidth = digits + "ch";
		const col = document.createElement("span");
		col.className = "iv-odo-col";
		const first = document.createElement("span");
		const second = document.createElement("span");
		first.textContent = String(up ? oldN : newN);
		second.textContent = String(up ? newN : oldN);
		col.append(first, second);
		track.append(col);
		el.textContent = "";
		el.append(track);
		const frames = up
			? [{ transform: "translateY(0)" }, { transform: "translateY(-50%)" }]
			: [{ transform: "translateY(-50%)" }, { transform: "translateY(0)" }];
		const anim = col.animate(frames, { duration: 420, easing: FLOW_EASE });
		const done = () => { el.textContent = String(newN); };
		anim.onfinish = done;
		anim.oncancel = done;
	}

	// Stat values change in app.js before the event; segment counts change in
	// counts(). Watch both, but only roll segment counts during a stage flow so
	// ordinary filtering stays instant.
	for (const el of page.querySelectorAll("[data-interview-count], [data-iv-count]")) {
		new MutationObserver((muts) => {
			for (const m of muts) {
				const host = m.target.nodeType === 3 ? m.target.parentElement : m.target;
				if (!host || host.querySelector(".iv-odo")) continue;
				const isStat = host.hasAttribute("data-interview-count");
				const marked = host.dataset.flow === "1";
				if (marked) delete host.dataset.flow;
				if (!isStat && !marked) continue;
				// Only real value edits replace a text node; our own odometer
				// cleanup removes an element, which must not start another roll.
				const removed = m.removedNodes[0];
				if (removed && removed.nodeType !== 3) continue;
				const oldText = m.oldValue ?? (removed ? removed.textContent : "");
				rollCount(host, oldText, host.textContent);
			}
		}).observe(el, { characterData: true, characterDataOldValue: true, childList: true, subtree: true });
	}

	function snapshotRects() {
		const map = new Map();
		for (const r of rows()) if (!r.hidden) map.set(r, r.getBoundingClientRect());
		return map;
	}

	function flipFrom(before, focusRow) {
		if (!canAnimate()) return;
		for (const r of rows()) {
			if (r.hidden) continue;
			const now = r.getBoundingClientRect();
			const was = before.get(r);
			if (was) {
				const dx = was.left - now.left;
				const dy = was.top - now.top;
				if (dx || dy) {
					r.animate(
						[{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "translate(0, 0)" }],
						{ duration: 380, easing: FLOW_EASE },
					);
				}
			} else if (r === focusRow) {
				r.animate(
					[{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "translateY(0)" }],
					{ duration: 320, easing: FLOW_EASE },
				);
			}
		}
	}

	function apply() {
		const q = (filter.value || "").trim().toLowerCase();
		let shown = 0;
		for (const row of rows()) {
			const visible = inSegment(row) && (!q || row.dataset.search.includes(q));
			row.hidden = !visible;
			if (visible) shown += 1;
		}
		for (const header of list.querySelectorAll("[data-iv-group]")) {
			let any = false;
			let next = header.nextElementSibling;
			while (next && next.matches("[data-iv-row]")) {
				if (!next.hidden) any = true;
				next = next.nextElementSibling;
			}
			header.hidden = !any;
		}
		empty.hidden = shown > 0;
		list.hidden = shown === 0;
		for (const b of segments) b.setAttribute("aria-pressed", String(b.dataset.ivSegment === segment));
		const visibleRows = rows().filter((r) => !r.hidden);
		if (!current || !visibleRows.some((r) => r.dataset.key === current)) {
			select(visibleRows[0] ? visibleRows[0].dataset.key : null, { focus: false });
		}
		detail.hidden = shown === 0;
	}

	function select(key, { focus = false, reveal = false } = {}) {
		current = key;
		for (const row of rows()) {
			const on = row.dataset.key === key;
			row.setAttribute("aria-selected", String(on));
			row.tabIndex = on ? 0 : -1;
		}
		for (const entry of page.querySelectorAll("[data-interview]")) {
			entry.classList.toggle("is-current", entry.dataset.key === key);
		}
		if (!key) return;
		try {
			sessionStorage.setItem(KEY, key);
		} catch {
			// Selection memory is optional.
		}
		const row = rowFor(key);
		if (row) row.scrollIntoView({ block: "nearest" });
		if (focus && row) row.focus({ preventScroll: true });
		if (reveal && narrow()) {
			const entry = entryFor(key);
			if (entry) {
				entry.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
				entry.focus({ preventScroll: true });
			}
		}
	}

	function move(step) {
		const visible = rows().filter((r) => !r.hidden);
		if (!visible.length) return;
		const at = visible.findIndex((r) => r.dataset.key === current);
		let idx;
		if (step === "first") idx = 0;
		else if (step === "last") idx = visible.length - 1;
		else idx = Math.min(visible.length - 1, Math.max(0, (at < 0 ? 0 : at) + step));
		select(visible[idx].dataset.key, { focus: true });
	}

	function openDetail() {
		const entry = current && entryFor(current);
		if (!entry) return;
		if (narrow()) entry.scrollIntoView({ block: "start" });
		const first =
			entry.querySelector('[data-interview-select="status"]') ||
			entry.querySelector("select, input, textarea, button");
		(first || entry).focus();
	}

	list.addEventListener("click", (e) => {
		const row = e.target.closest("[data-iv-row]");
		if (!row) return;
		select(row.dataset.key, { focus: true, reveal: true });
	});

	for (const b of segments) {
		b.addEventListener("click", () => {
			segment = b.dataset.ivSegment;
			try {
				sessionStorage.setItem(SEG_KEY, segment);
			} catch {
				// Optional.
			}
			apply();
		});
	}

	filter.addEventListener("input", apply);
	filter.addEventListener("keydown", (e) => {
		if (e.key === "Escape") {
			filter.value = "";
			apply();
			const row = current && rowFor(current);
			if (row) row.focus();
		} else if (e.key === "ArrowDown") {
			e.preventDefault();
			move(0);
		}
	});

	page.querySelector("[data-iv-back]")?.addEventListener("click", () => {
		const row = current && rowFor(current);
		list.scrollIntoView({ block: "start" });
		if (row) row.focus({ preventScroll: true });
	});

	const typing = (el) => el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));

	document.addEventListener("keydown", (e) => {
		if (!page.classList.contains("active") || e.metaKey || e.ctrlKey || e.altKey) return;
		if (document.querySelector("dialog[open]")) return;
		const t = e.target;
		if (e.key === "/" && !typing(t)) {
			e.preventDefault();
			filter.focus();
			filter.select();
			return;
		}
		const inList = list.contains(t);
		const inDetail = detail.contains(t);
		if (e.key === "Escape" && inDetail) {
			const row = current && rowFor(current);
			if (row) {
				e.preventDefault();
				row.focus();
				if (narrow()) row.scrollIntoView({ block: "center" });
			}
			return;
		}
		if (typing(t) || (!inList && t !== document.body && t !== page)) return;
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
				if (!inList) return;
				e.preventDefault();
				move("first");
				break;
			case "End":
				if (!inList) return;
				e.preventDefault();
				move("last");
				break;
			case "Enter":
			case "ArrowRight":
				if (!inList) return;
				e.preventDefault();
				openDetail();
				break;
		}
	});

	page.addEventListener("interview:status", (e) => {
		const key = e.detail.row.dataset.key;
		const row = rowFor(key);
		if (!row) return;
		const before = snapshotRects();
		markFlow();
		row.dataset.status = e.detail.data.status;
		row.dataset.group = groupOf(e.detail.data.status);
		regroup(row);
		paintRow(row);
		counts();
		// Keep the edited application on screen even if it left the segment.
		const keep = current;
		apply();
		if (keep === key && row.hidden) {
			segment = "all";
			apply();
			select(key);
		}
		flipFrom(before, row);
		if (canAnimate() && current === key) {
			const badge = entryFor(key)?.querySelector("[data-interview-status]");
			badge?.animate([{ opacity: 0.25 }, { opacity: 1 }], { duration: 300, easing: "ease-out" });
		}
	});

	page.addEventListener("interview:next", (e) => {
		const row = rowFor(e.detail.row.dataset.key);
		if (!row) return;
		const before = snapshotRects();
		markFlow();
		const data = e.detail.data;
		row.dataset.overdue = data.overdue ? "true" : "false";
		const meta = row.querySelector(".iv-row-meta");
		let time = meta.querySelector("time");
		const date = data.next_step && data.next_step.date;
		if (date) {
			if (!time) {
				time = document.createElement("time");
				meta.prepend(time);
			}
			time.dateTime = date;
			time.textContent = date;
		} else if (time) {
			time.remove();
		}
		paintRow(row);
		counts();
		flipFrom(before, row);
	});

	for (const row of rows()) paintRow(row);
	const c = counts();
	let savedSeg = null;
	let savedKey = null;
	try {
		savedSeg = sessionStorage.getItem(SEG_KEY);
		savedKey = sessionStorage.getItem(KEY);
	} catch {
		// Optional.
	}
	segment = savedSeg && segments.some((b) => b.dataset.ivSegment === savedSeg) ? savedSeg : c.needs ? "needs" : "all";
	if (savedKey && rowFor(savedKey)) current = savedKey;
	apply();
	if (current) select(current);
})();
