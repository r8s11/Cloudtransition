// Deck: run tab interactions. Loaded after app.js. Presentation only:
// filtering, counts and collapse memory; runs still start from app.js.
(() => {
	const page = document.getElementById("page-run");
	const filter = document.getElementById("runFilter");
	const empty = document.getElementById("runFilterEmpty");
	const design = document.getElementById("designRuns");
	if (!page || !filter) return;

	const sections = Array.from(page.querySelectorAll(".run-section"));
	const DESIGN_KEY = "run.designRuns.open";

	function apply() {
		const q = filter.value.trim().toLowerCase();
		let shown = 0;
		for (const section of sections) {
			const items = section.querySelectorAll(".run-item");
			let visible = 0;
			for (const item of items) {
				const text = `${item.querySelector("h4")?.textContent || ""} ${item.querySelector(".run-item-text p")?.textContent || ""}`;
				const match = !q || text.toLowerCase().includes(q);
				item.hidden = !match;
				if (match) visible++;
			}
			const count = section.querySelector("[data-run-count]");
			if (count) count.textContent = items.length ? (q ? `${visible}/${items.length}` : String(items.length)) : "";
			// While filtering, hide sections without hits; never touch the user's open state.
			section.hidden = Boolean(q) && items.length > 0 && visible === 0;
			if (q && visible && section === design && !design.open) design.open = true;
			shown += visible;
		}
		empty.hidden = !q || shown > 0;
	}

	filter.addEventListener("input", apply);
	filter.addEventListener("keydown", (e) => {
		if (e.key === "Escape" && filter.value) {
			e.preventDefault();
			e.stopPropagation();
			filter.value = "";
			apply();
		}
	});

	document.addEventListener("keydown", (e) => {
		if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
		if (!page.classList.contains("active")) return;
		const t = e.target;
		if (t.closest?.("input, textarea, select, [contenteditable]")) return;
		e.preventDefault();
		filter.focus();
		filter.select();
	});

	// app.js rebuilds the grids after each catalogue load; re-filter then.
	const observer = new MutationObserver(apply);
	for (const grid of page.querySelectorAll("[data-run-grid]")) observer.observe(grid, { childList: true });

	if (design) {
		try {
			const saved = localStorage.getItem(DESIGN_KEY);
			if (saved !== null) design.open = saved === "1";
		} catch {}
		design.addEventListener("toggle", () => {
			if (filter.value.trim()) return; // auto-opened by a filter hit
			try {
				localStorage.setItem(DESIGN_KEY, design.open ? "1" : "0");
			} catch {}
		});
	}

	apply();

	// Activity jump: on narrow screens the log sits below every tool.
	const jump = page.querySelector("[data-run-jump]");
	const history = document.getElementById("runHistory");
	if (jump && history) {
		jump.addEventListener("click", () => {
			history.scrollIntoView({ block: "start" });
			history.setAttribute("tabindex", "-1");
			history.focus({ preventScroll: true });
		});
		const count = jump.querySelector("[data-run-jump-count]");
		const recount = () => {
			const running = history.querySelectorAll(".is-running").length;
			count.textContent = running ? `${running} running` : "";
		};
		new MutationObserver(recount).observe(history, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
		recount();
	}
})();
