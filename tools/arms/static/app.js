/* ARMS weekly review UI. Vanilla JS, no external assets.
   Every piece of report / memory / feedback text is inserted with textContent
   (never innerHTML), so source content cannot inject markup. */
"use strict";

(() => {
	const $ = (id) => document.getElementById(id);

	const state = {
		status: null,
		report: null, // /api/report response
		reportNotice: null,
		cart: [], // [{suggestion_id, comment}]
		feedback: [],
		feedbackError: null,
		filter: "parked",
	};

	// ── helpers ──────────────────────────────────────────────

	function h(tag, props, ...kids) {
		const el = document.createElement(tag);
		for (const [key, val] of Object.entries(props || {})) {
			if (val === null || val === undefined || val === false) continue;
			if (key === "class") el.className = val;
			else if (key === "text") el.textContent = val;
			else if (key.startsWith("on") && typeof val === "function") el.addEventListener(key.slice(2), val);
			else el.setAttribute(key, val === true ? "" : String(val));
		}
		for (const kid of kids.flat()) {
			if (kid === null || kid === undefined || kid === false) continue;
			el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
		}
		return el;
	}

	const asObj = (x) => (x && typeof x === "object" && !Array.isArray(x) ? x : {});
	const asArr = (x) => (Array.isArray(x) ? x : []);

	/** Unknown stays unknown: null/undefined are never shown as 0. */
	function fmt(v) {
		if (v === null || v === undefined || v === "") return "unknown";
		if (typeof v === "number") return Number.isFinite(v) ? v.toLocaleString() : "unknown";
		if (typeof v === "boolean") return v ? "yes" : "no";
		if (Array.isArray(v)) return v.length ? v.map(fmt).join(", ") : "none";
		if (typeof v === "object") return JSON.stringify(v);
		return String(v);
	}

	function announce(msg) {
		$("live").textContent = "";
		setTimeout(() => ($("live").textContent = msg), 30);
	}

	class ApiFail extends Error {
		constructor(message, status, data) {
			super(message);
			this.status = status;
			this.data = data;
		}
	}

	async function api(method, path, body) {
		const opts = { method, headers: { Accept: "application/json" }, credentials: "same-origin" };
		if (method !== "GET") {
			opts.headers["Content-Type"] = "application/json";
			opts.body = JSON.stringify(body === undefined ? {} : body);
		}
		let res;
		try {
			res = await fetch(path, opts);
		} catch (_err) {
			throw new ApiFail("Cannot reach the local server. Is app.py still running?", 0, null);
		}
		let data = null;
		try {
			data = await res.json();
		} catch (_err) {
			/* non-JSON body */
		}
		if (!res.ok) throw new ApiFail((data && data.error) || `Request failed (${res.status})`, res.status, data);
		return data;
	}

	const stateBox = (kind, text, ...extra) =>
		h("div", { class: `state state-${kind}`, role: kind === "error" ? "alert" : null }, text, ...extra);

	function chip(text, cls) {
		return h("span", { class: `chip ${cls ? `chip-${cls}` : ""}`, text });
	}

	const GLYPH = { pass: "✓", warn: "!", fail: "✕", unknown: "?" };
	const statusChip = (s) => chip(`${GLYPH[s] || "?"} ${fmt(s)}`, GLYPH[s] ? s : "unknown");

	function setBusy(btn, busy, busyText, idleText) {
		btn.disabled = busy;
		btn.setAttribute("aria-busy", busy ? "true" : "false");
		if (busyText) btn.textContent = busy ? busyText : idleText;
	}

	function table(caption, cols, rows) {
		return h(
			"div",
			{ class: "table-wrap", role: "region", "aria-label": caption, tabindex: "0" },
			h(
				"table",
				{},
				h("caption", { class: "sr-only", text: caption }),
				h("thead", {}, h("tr", {}, cols.map((c) => h("th", { scope: "col", text: c })))),
				h("tbody", {}, rows.map((r) => h("tr", {}, r.map((cell) => h("td", {}, cell))))),
			),
		);
	}

	// ── report ───────────────────────────────────────────────

	const reportData = () => (state.report && state.report.status === "ok" ? asObj(state.report.report) : null);

	function renderReport() {
		const box = $("report-body");
		box.replaceChildren();
		box.setAttribute("aria-busy", "false");
		const meta = $("report-meta");
		const r = state.report;

		if (state.reportNotice) box.append(stateBox(state.reportNotice.kind, state.reportNotice.text));

		if (!r) {
			meta.textContent = "Report unavailable.";
			return;
		}
		if (r.status === "missing") {
			meta.textContent = "No report generated yet.";
			box.append(
				stateBox(
					"warn",
					"There is no routine report yet. Use “Refresh report” to generate one, or run ",
					h("code", { text: "python3 tools/arms/routines.py" }),
					". Expected file: ",
					h("code", { text: fmt(r.path) }),
				),
			);
			return;
		}
		if (r.status === "invalid") {
			meta.textContent = "Report file could not be read.";
			box.append(stateBox("error", `The report file is unreadable: ${fmt(r.message)}`));
			return;
		}

		const rep = reportData() || {};
		const gen = ["checks", "inventory", "usage", "suggestions"].map((k) => asObj(rep[k]).generated_at).find(Boolean);
		meta.textContent = `Generated ${fmt(gen)} · file updated ${fmt(r.modified)}`;
		box.append(checksBlock(asObj(rep.checks)), inventoryBlock(asObj(rep.inventory)), usageBlock(asObj(rep.usage)));
	}

	function checksBlock(checks) {
		const wrap = h("div", {}, h("h3", { text: "Checks" }));
		const items = asArr(checks.items);
		const summary = asObj(checks.summary);
		const cost = asObj(checks.cost);
		wrap.append(
			h(
				"div",
				{ class: "stat-row" },
				["pass", "warn", "fail", "unknown"].map((k) => chip(`${GLYPH[k]} ${k} ${fmt(summary[k])}`, k)),
				chip(`API tokens ${fmt(cost.api_tokens)}`),
				chip(`API USD ${fmt(cost.api_usd)}`),
			),
		);
		if (cost.note) wrap.append(h("p", { class: "hint", text: String(cost.note) }));
		if (!items.length) {
			wrap.append(stateBox("idle", "The report contains no checks."));
			return wrap;
		}
		wrap.append(
			h(
				"ul",
				{ class: "list" },
				items.map((it) => {
					const o = asObj(it);
					const ev = asArr(o.evidence);
					return h(
						"li",
						{ class: "item" },
						h("div", { class: "item-head" }, statusChip(o.status), h("span", { class: "item-title", text: fmt(o.title || o.id) })),
						(o.message || o.detail) && h("p", { text: String(o.message || o.detail) }),
						ev.length > 0 &&
							h("details", {}, h("summary", { text: `Evidence (${ev.length})` }), h("ul", {}, ev.map((e) => h("li", { text: fmt(e) })))),
					);
				}),
			),
		);
		return wrap;
	}

	function inventoryBlock(inv) {
		const items = asArr(inv.items);
		const wrap = h("div", {}, h("h3", { text: "Routine inventory" }));
		const counts = asObj(inv.counts);
		const countKeys = Object.keys(counts);
		if (countKeys.length) wrap.append(h("div", { class: "stat-row" }, countKeys.map((k) => chip(`${k} ${fmt(counts[k])}`))));
		if (!items.length) {
			wrap.append(stateBox("idle", "No routines were inventoried."));
		} else {
			wrap.append(
				table(
					"Routine inventory",
					["Name", "Kind", "Status", "Schedule", "Classification", "Model spend", "External", "Review mode", "Token telemetry"],
					items.map((it) => {
						const o = asObj(it);
						return [
							h("span", { class: "item-title", text: fmt(o.name || o.id) }),
							fmt(o.kind),
							chip(fmt(o.status), o.status === "installed-loaded" ? "installed-loaded" : o.status === "unknown" ? "unknown" : ""),
							fmt(o.schedule === null ? "none" : o.schedule),
							fmt(o.classification),
							fmt(o.model_spend),
							fmt(o.external),
							fmt(o.review_mode),
							fmt(o.token_telemetry),
						];
					}),
				),
			);
			const noted = items.filter((it) => asObj(it).summary || asObj(it).notes);
			if (noted.length)
				wrap.append(
					h(
						"details",
						{ class: "item" },
						h("summary", { text: `Routine notes (${noted.length})` }),
						h("ul", {}, noted.map((it) => h("li", { text: `${fmt(asObj(it).name)}: ${fmt(asObj(it).summary || asObj(it).notes)}` }))),
					),
				);
		}
		const unknown = asArr(inv.unknown);
		if (unknown.length) wrap.append(stateBox("warn", `Could not determine: ${unknown.map(fmt).join("; ")}`));
		return wrap;
	}

	function usageBlock(u) {
		const wrap = h("div", {}, h("h3", { text: "Session usage" }));
		if (!Object.keys(u).length) {
			wrap.append(stateBox("idle", "The report has no usage section."));
			return wrap;
		}
		wrap.append(
			h(
				"div",
				{ class: "stat-row" },
				chip(`status ${fmt(u.status)}`, u.status === "ok" ? "pass" : u.status === "partial" ? "warn" : "unknown"),
				chip(`window ${fmt(u.window_days)} days`),
			),
		);
		if (u.window_start || u.window_end) wrap.append(h("p", { class: "hint", text: `${fmt(u.window_start)} → ${fmt(u.window_end)}` }));

		const sources = asArr(u.sources);
		if (sources.length)
			wrap.append(
				table(
					"Usage sources",
					["Source", "Tool", "Available", "Sessions", "Reason"],
					sources.map((s) => {
						const o = asObj(s);
						return [fmt(o.id), fmt(o.tool), fmt(o.available), fmt(o.sessions), fmt(o.reason === null ? "" : o.reason)];
					}),
				),
			);

		const totals = asObj(u.totals);
		const keys = Object.keys(totals);
		if (keys.length)
			wrap.append(h("h3", { text: "Totals" }), h("dl", { class: "kv" }, keys.map((k) => [h("dt", { text: k.replace(/_/g, " ") }), h("dd", { text: fmt(totals[k]) })]).flat()));

		const cache = asObj(u.cache);
		if (Object.keys(cache).length) {
			const ratio = cache.read_ratio;
			wrap.append(
				h("p", { class: "hint", text: `Cache read ratio: ${typeof ratio === "number" ? `${(ratio * 100).toFixed(1)}%` : "unknown"}` }),
				...(asArr(cache.observations).length > 0 ? [h("ul", { class: "hint" }, asArr(cache.observations).map((o) => h("li", { text: fmt(o) })))] : []),
			);
		}

		const days = asArr(u.by_day);
		if (days.length) {
			const peak = Math.max(1, ...days.map((d) => Number(asObj(d).sessions) || 0));
			wrap.append(
				h("h3", { text: "By day" }),
				table(
					"Sessions by day",
					["Date", "Sessions", ""],
					days.slice(-31).map((d) => {
						const o = asObj(d);
						const bar = h("span", { class: "crease", "aria-hidden": "true" });
						bar.style.width = `${Math.round(((Number(o.sessions) || 0) / peak) * 100)}%`;
						return [fmt(o.date), fmt(o.sessions), bar];
					}),
				),
			);
		}

		const skills = asObj(u.skills);
		if (Object.keys(skills).length)
			wrap.append(
				h("h3", { text: "Skill usage" }),
				asArr(skills.items).length
					? table(
							"Skill usage",
							["Skill", "Invocations"],
							asArr(skills.items).map((s) => [fmt(asObj(s).name || asObj(s).skill || asObj(s).id), fmt(asObj(s).count ?? asObj(s).invocations)]),
						)
					: stateBox("warn", `Skill usage ${fmt(skills.status)}: ${fmt(skills.reason === null ? "" : skills.reason)}`),
			);

		const est = asObj(u.estimate);
		if (Object.keys(est).length)
			wrap.append(
				h("h3", { text: "Cost estimate" }),
				stateBox(est.status === "supplied-rates" ? "ok" : "warn", `Estimate ${fmt(est.status)}${est.usd !== null && est.usd !== undefined ? ` · ${fmt(est.usd)} USD` : ""}. ${fmt(est.reason === null ? "" : est.reason)}`.trim()),
			);
		const notes = asArr(u.notes);
		if (notes.length) wrap.append(h("ul", { class: "hint" }, notes.map((n) => h("li", { text: fmt(n) }))));
		return wrap;
	}

	async function loadReport() {
		try {
			state.report = await api("GET", "/api/report");
		} catch (err) {
			state.report = null;
			state.reportNotice = { kind: "error", text: err.message };
		}
		renderReport();
		renderSuggestions();
		renderCart();
	}

	async function refreshReport() {
		const btn = $("refresh-btn");
		setBusy(btn, true, "Refreshing…", "Refresh report");
		state.reportNotice = { kind: "idle", text: "Running deterministic checks locally…" };
		renderReport();
		try {
			state.report = await api("POST", "/api/report/refresh", {});
			state.reportNotice = { kind: "ok", text: "Report refreshed. No model calls were made." };
			announce("Report refreshed");
		} catch (err) {
			const stderr = err.data && err.data.stderr ? ` — ${err.data.stderr}` : "";
			state.reportNotice = { kind: "error", text: `Refresh failed: ${err.message}${stderr}` };
			announce("Report refresh failed");
		} finally {
			setBusy(btn, false, "Refreshing…", "Refresh report");
		}
		renderReport();
		renderSuggestions();
		renderCart();
	}

	// ── suggestions & cart ───────────────────────────────────

	const suggestionBlock = () => asObj((reportData() || {}).suggestions);
	const suggestionList = () => asArr(suggestionBlock().items).map(asObj).filter((s) => typeof s.id === "string");
	const inCart = (id) => state.cart.some((c) => c.suggestion_id === id);

	function renderSuggestions() {
		const box = $("sugg-list");
		const meta = $("sugg-meta");
		box.replaceChildren();
		if (!state.report) {
			meta.textContent = "Report unavailable.";
			box.append(stateBox("error", "Suggestions need the routine report, which could not be loaded."));
			return;
		}
		if (state.report.status !== "ok") {
			meta.textContent = "No report.";
			box.append(stateBox("warn", "No suggestions yet: the routine report has not been generated."));
			return;
		}
		const block = suggestionBlock();
		const list = suggestionList();
		meta.textContent = `Window ${fmt(block.window_days)} days · threshold ${fmt(block.threshold)} repeats · ${list.length} suggestion(s)`;
		if (!list.length) {
			box.append(stateBox("idle", "This report contains no suggestions. See the notes below for why (an empty list is not proof that nothing repeats)."));
		} else {
			box.append(
				h(
					"ul",
					{ class: "list" },
					list.map((s) => {
						const picked = inCart(s.id);
						const cb = h("input", {
							type: "checkbox",
							id: `sg-${s.id}`,
							"aria-label": `Add to cart: ${fmt(s.title)}`,
							checked: picked,
							onchange: () => toggleCart(s.id),
						});
						cb.checked = picked;
						return h(
							"li",
							{ class: `item sugg${picked ? " in-cart" : ""}` },
							cb,
							h(
								"div",
								{},
								h("label", { for: `sg-${s.id}`, class: "item-title", text: fmt(s.title) }),
								h(
									"div",
									{ class: "item-meta", text: `${fmt(s.tool)} · ${fmt(s.evidence_count)} observation(s)${asArr(s.days).length ? ` · ${asArr(s.days).slice(0, 7).join(", ")}` : ""} · ${s.id}` },
								),
								s.summary && h("p", { text: String(s.summary) }),
								s.proposed_action &&
									h("div", { class: "action-text" }, h("strong", { text: "Proposed action — never executed" }), String(s.proposed_action)),
								h(
									"div",
									{ class: "stat-row" },
									chip(s.safe_to_schedule ? "safe to schedule" : "not marked safe to schedule"),
									chip(`model spend ${fmt(s.model_spend)}`),
									s.requires_approval ? chip("requires approval") : null,
								),
							),
						);
					}),
				),
			);
		}
		const notes = asArr(block.notes);
		if (notes.length) box.append(h("ul", { class: "hint" }, notes.map((n) => h("li", { text: fmt(n) }))));
	}

	let saveTimer = null;
	let saveChain = Promise.resolve();

	function setCartState(text, isError) {
		const el = $("cart-state");
		el.textContent = text;
		el.style.color = isError ? "var(--red)" : "";
	}

	function scheduleSave() {
		setCartState("Unsaved changes…");
		clearTimeout(saveTimer);
		saveTimer = setTimeout(saveCart, 500);
	}

	function saveCart() {
		clearTimeout(saveTimer);
		saveTimer = null;
		saveChain = saveChain.then(async () => {
			setCartState("Saving…");
			try {
				await api("PUT", "/api/cart", { items: state.cart });
				setCartState("Saved");
				return true;
			} catch (err) {
				setCartState(`Not saved: ${err.message}`, true);
				return false;
			}
		});
		return saveChain;
	}

	function toggleCart(id) {
		const at = state.cart.findIndex((c) => c.suggestion_id === id);
		if (at >= 0) state.cart.splice(at, 1);
		else state.cart.push({ suggestion_id: id, comment: "" });
		renderSuggestions();
		renderCart();
		scheduleSave();
		announce(at >= 0 ? "Removed from cart" : "Added to cart");
	}

	function renderCart() {
		const box = $("cart-list");
		box.replaceChildren();
		$("cart-count").textContent = String(state.cart.length);
		const bySid = new Map(suggestionList().map((s) => [s.id, s]));
		if (!state.cart.length) {
			box.append(stateBox("idle", "The cart is empty. Tick suggestions to collect them with comments."));
		} else {
			box.append(
				h(
					"ul",
					{ class: "list" },
					state.cart.map((entry) => {
						const s = bySid.get(entry.suggestion_id);
						const title = s ? fmt(s.title) : entry.suggestion_id;
						const ta = h("textarea", {
							rows: 2,
							maxlength: (state.status && state.status.limits.cart_comment) || 2000,
							"aria-label": `Comment for ${title}`,
							placeholder: "Comment (optional)",
							oninput: (ev) => {
								entry.comment = ev.target.value;
								scheduleSave();
							},
						});
						ta.value = entry.comment || "";
						return h(
							"li",
							{ class: "cart-item" },
							h(
								"div",
								{ class: "item-head" },
								h("span", { class: "item-title", text: title }),
								!s && chip(state.report && state.report.status === "ok" ? "not in current report" : "report not loaded", "warn"),
								h("button", { type: "button", class: "btn btn-small", "aria-label": `Remove ${title} from cart`, onclick: () => toggleCart(entry.suggestion_id), text: "Remove" }),
							),
							ta,
						);
					}),
				),
			);
		}
		updateCartButtons();
	}

	function updateCartButtons() {
		$("copy-btn").disabled = !state.cart.length && !$("cart-with-feedback").checked;
		$("clear-cart-btn").disabled = !state.cart.length;
	}

	async function copyCart() {
		const btn = $("copy-btn");
		setBusy(btn, true, "Preparing…", "Copy selection as Markdown");
		try {
			if (saveTimer) await saveCart();
			else await saveChain;
			const withFb = $("cart-with-feedback").checked;
			const d = await api("GET", `/api/cart/markdown${withFb ? "?feedback=1" : ""}`);
			const preview = $("cart-preview");
			preview.value = d.markdown;
			try {
				await navigator.clipboard.writeText(d.markdown);
				setCartState(`Copied ${d.selected} suggestion(s)`);
				announce("Copied to clipboard");
			} catch (_err) {
				preview.focus();
				preview.select();
				setCartState("Clipboard blocked — text selected; press Ctrl/⌘+C", true);
			}
		} catch (err) {
			setCartState(`Copy failed: ${err.message}`, true);
		} finally {
			setBusy(btn, false, "Preparing…", "Copy selection as Markdown");
			updateCartButtons();
		}
	}

	async function loadCart() {
		try {
			const d = await api("GET", "/api/cart");
			state.cart = asArr(d.items).map((c) => ({ suggestion_id: String(asObj(c).suggestion_id), comment: String(asObj(c).comment || "") }));
			setCartState("");
		} catch (err) {
			setCartState(`Cart could not be loaded: ${err.message}`, true);
		}
		renderSuggestions();
		renderCart();
	}

	// ── memory ───────────────────────────────────────────────

	function renderQuery(d) {
		const out = $("q-result");
		out.replaceChildren();
		const msg = d.message ? ` ${d.message}` : "";
		switch (d.status) {
			case "ok": {
				const ev = asArr(d.evidence);
				out.append(
					h("p", { class: "hint", text: `${ev.length} passage(s) · ${fmt(d.files_opened)} file(s) opened · ${fmt(d.elapsed_ms)} ms` }),
					h(
						"div",
						{ class: "evidence" },
						ev.map((e) => {
							const o = asObj(e);
							return h("div", { class: "item" }, h("div", { class: "item-meta", text: `${fmt(o.path)}:${fmt(o.start_line)}–${fmt(o.end_line)}` }), h("pre", { text: String(o.text ?? "") }));
						}),
					),
					...(d.pointer ? [h("p", { class: "hint", text: `Related pointer (not opened): ${d.pointer}` })] : []),
				);
				break;
			}
			case "no_match":
				out.append(stateBox("warn", `No memory matched that question.${msg}`));
				break;
			case "stale":
			case "not_indexed":
				out.append(
					stateBox("warn", `The memory index is ${d.status === "stale" ? "out of date" : "missing"}.${msg} Rebuild it with: `, h("code", { text: "python3 second-brain/brain.py index" })),
				);
				break;
			case "empty_question":
				out.append(stateBox("warn", "Type a question first."));
				break;
			default:
				out.append(stateBox("warn", `Memory CLI returned status “${fmt(d.status)}”.${msg}`));
		}
	}

	async function runQuery(ev) {
		ev.preventDefault();
		const input = $("q");
		const question = input.value.trim();
		const out = $("q-result");
		input.removeAttribute("aria-invalid");
		if (!question || question.startsWith("-")) {
			input.setAttribute("aria-invalid", "true");
			out.replaceChildren(stateBox("error", question ? "A question cannot start with “-”." : "Enter a question."));
			input.focus();
			return;
		}
		const btn = $("q-btn");
		setBusy(btn, true, "Searching…", "Search");
		out.replaceChildren(stateBox("idle", "Searching memory…"));
		try {
			renderQuery(await api("POST", "/api/memory/query", { question }));
			announce("Search finished");
		} catch (err) {
			out.replaceChildren(stateBox("error", `Search failed: ${err.message}`));
		} finally {
			setBusy(btn, false, "Searching…", "Search");
		}
	}

	async function runRemember(ev) {
		ev.preventDefault();
		const form = $("remember-form");
		const out = $("m-result");
		const body = { title: $("m-title").value.trim(), summary: $("m-summary").value.trim(), body: $("m-body").value.trim() };
		let bad = null;
		for (const [key, id] of [["title", "m-title"], ["summary", "m-summary"], ["body", "m-body"]]) {
			const empty = !body[key];
			$(id).toggleAttribute("aria-invalid", empty);
			if (empty) $(id).setAttribute("aria-invalid", "true");
			if (empty && !bad) bad = id;
		}
		if (bad) {
			out.replaceChildren(stateBox("error", "Title, summary and body are all required."));
			$(bad).focus();
			return;
		}
		const btn = $("m-btn");
		setBusy(btn, true, "Saving…", "Save memory");
		out.replaceChildren(stateBox("idle", "Saving…"));
		try {
			const d = await api("POST", "/api/memory/remember", body);
			form.reset();
			updateCounters();
			out.replaceChildren(stateBox("ok", `Saved as ${fmt(d.path)}${d.id ? ` (id ${d.id})` : ""}.`));
			announce("Memory saved");
		} catch (err) {
			out.replaceChildren(stateBox("error", `Not saved: ${err.message}`));
		} finally {
			setBusy(btn, false, "Saving…", "Save memory");
		}
	}

	function updateCounters() {
		for (const [id, out] of [["m-title", "m-title-n"], ["m-summary", "m-summary-n"], ["m-body", "m-body-n"]]) {
			const el = $(id);
			$(out).textContent = `${el.value.length}/${el.getAttribute("maxlength")}`;
		}
	}

	// ── feedback ─────────────────────────────────────────────

	function renderFeedback() {
		const box = $("fb-list");
		box.replaceChildren();
		const parked = state.feedback.filter((f) => f.status === "parked").length;
		$("parked-count").textContent = String(parked);
		if (state.feedbackError) {
			box.append(stateBox("error", `Feedback could not be loaded: ${state.feedbackError}`));
			return;
		}
		const shown = state.feedback
			.filter((f) => state.filter === "all" || f.status === state.filter)
			.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
		if (!shown.length) {
			box.append(stateBox("idle", state.filter === "all" ? "No feedback has been parked yet." : `No ${state.filter} feedback.`));
			return;
		}
		box.append(
			h(
				"ul",
				{ class: "list fb" },
				shown.map((f) => {
					const actions = [];
					if (f.status === "parked") actions.push(["Mark reviewed", "reviewed"], ["Dismiss", "dismissed"]);
					else if (f.status === "reviewed") actions.push(["Back to parked", "parked"], ["Dismiss", "dismissed"]);
					else if (f.status === "dismissed") actions.push(["Re-park", "parked"]);
					return h(
						"li",
						{ class: "item" },
						h("div", { class: "item-head" }, h("span", { class: "item-title", text: fmt(f.target_skill) }), chip(fmt(f.status), f.status === "resolved" ? "pass" : "")),
						h("div", { class: "item-meta", text: `${fmt(f.id)} · ${fmt(f.created_at)}` }),
						f.principle && h("p", {}, h("strong", { text: "Principle: " }), String(f.principle)),
						f.comments && h("p", { class: "quote", text: String(f.comments) }),
						f.resolution && h("p", {}, h("strong", { text: "Resolution: " }), String(f.resolution)),
						f.applied_principle && h("p", {}, h("strong", { text: "Applied principle: " }), String(f.applied_principle)),
						actions.length > 0 &&
							h(
								"div",
								{ class: "fb-actions" },
								actions.map(([label, status]) =>
									h("button", { type: "button", class: "btn btn-small", "aria-label": `${label}: feedback for ${fmt(f.target_skill)}`, onclick: () => setFeedbackStatus(f.id, status), text: label }),
								),
							),
					);
				}),
			),
		);
	}

	async function loadFeedback() {
		try {
			state.feedback = asArr((await api("GET", "/api/feedback")).items).map(asObj);
			state.feedbackError = null;
		} catch (err) {
			state.feedbackError = err.message;
		}
		renderFeedback();
	}

	async function setFeedbackStatus(id, status) {
		try {
			await api("POST", "/api/feedback/status", { id, status });
			announce(`Marked ${status}`);
		} catch (err) {
			$("fb-result").replaceChildren(stateBox("error", `Status not changed: ${err.message}`));
		}
		await loadFeedback();
	}

	async function parkFeedback(ev) {
		ev.preventDefault();
		const out = $("fb-result");
		const body = { target_skill: $("fb-target").value.trim(), principle: $("fb-principle").value.trim(), comments: $("fb-comments").value.trim() };
		$("fb-target").toggleAttribute("aria-invalid", false);
		if (!body.target_skill || (!body.principle && !body.comments)) {
			if (!body.target_skill) $("fb-target").setAttribute("aria-invalid", "true");
			out.replaceChildren(stateBox("error", "Name the target skill and give a principle or comments."));
			(body.target_skill ? $("fb-comments") : $("fb-target")).focus();
			return;
		}
		const btn = $("fb-btn");
		setBusy(btn, true, "Parking…", "Park feedback");
		try {
			const item = await api("POST", "/api/feedback", body);
			$("fb-principle").value = "";
			$("fb-comments").value = "";
			out.replaceChildren(stateBox("ok", `Parked as ${item.id}. The skill file was not touched.`));
			announce("Feedback parked");
			await loadFeedback();
		} catch (err) {
			out.replaceChildren(stateBox("error", `Not parked: ${err.message}`));
		} finally {
			setBusy(btn, false, "Parking…", "Park feedback");
		}
	}

	// ── status, navigation, keyboard ─────────────────────────

	async function loadStatus() {
		try {
			state.status = await api("GET", "/api/status");
		} catch (err) {
			return;
		}
		$("artifacts-link").hidden = !state.status.artifacts_available;
		$("skill-list").replaceChildren(...asArr(state.status.known_skills).map((n) => h("option", { value: n })));
		if (!state.status.routines_available) {
			$("refresh-btn").disabled = true;
			$("refresh-help").textContent = "tools/arms/routines.py is not present, so the report cannot be refreshed from here.";
		}
		if (!state.status.brain_available) {
			$("q-result").replaceChildren(stateBox("warn", "second-brain/brain.py is not present; memory search and save will fail until it is."));
		}
	}

	function trackSteps() {
		const links = [...document.querySelectorAll(".fold-steps a")];
		let queued = false;
		const update = () => {
			queued = false;
			let current = links[0];
			for (const a of links) {
				const sec = document.getElementById(a.dataset.step);
				if (sec && sec.getBoundingClientRect().top <= 140) current = a;
			}
			for (const a of links) {
				if (a === current) a.setAttribute("aria-current", "true");
				else a.removeAttribute("aria-current");
			}
		};
		window.addEventListener("scroll", () => {
			if (!queued) {
				queued = true;
				requestAnimationFrame(update);
			}
		}, { passive: true });
		update();
	}

	function onKeydown(ev) {
		const t = ev.target;
		const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
		if (ev.key === "/" && !typing && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
			ev.preventDefault();
			$("q").focus();
			$("q").scrollIntoView({ block: "center" });
		} else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey) && t && t.form) {
			ev.preventDefault();
			t.form.requestSubmit();
		}
	}

	function init() {
		$("today").textContent = new Date().toLocaleDateString(undefined, { weekday: "short", year: "numeric", month: "short", day: "numeric" });
		$("refresh-btn").addEventListener("click", refreshReport);
		$("copy-btn").addEventListener("click", copyCart);
		$("clear-cart-btn").addEventListener("click", () => {
			state.cart = [];
			renderSuggestions();
			renderCart();
			scheduleSave();
			announce("Cart cleared");
		});
		$("cart-with-feedback").addEventListener("change", updateCartButtons);
		$("query-form").addEventListener("submit", runQuery);
		$("remember-form").addEventListener("submit", runRemember);
		$("fb-form").addEventListener("submit", parkFeedback);
		$("fb-filter").addEventListener("change", (ev) => {
			state.filter = ev.target.value;
			renderFeedback();
		});
		for (const id of ["m-title", "m-summary", "m-body"]) $(id).addEventListener("input", updateCounters);
		document.addEventListener("keydown", onKeydown);
		updateCounters();
		trackSteps();
		loadStatus().then(() => {
			if (state.status) {
				for (const [id, key] of [["q", "question"], ["m-title", "title"], ["m-summary", "summary"], ["m-body", "body"], ["fb-target", "target_skill"], ["fb-principle", "principle"], ["fb-comments", "comments"]]) {
					$(id).setAttribute("maxlength", state.status.limits[key]);
				}
				updateCounters();
			}
		});
		loadReport();
		loadCart();
		loadFeedback();
	}

	init();
})();
