// Today's "Now" card (templates/pages/today.html, core/now.py) and the
// one-tap "Mark applied" on Today and the Interviews tab.
//
// Mark applied posts /api/interviews/applied: the server logs an `applied`
// timeline entry for today, parks the row as `waiting` and schedules a
// follow-up a week out in one write. The plan depends on that count, so a
// success reloads the page and the server recomputes Now.
(() => {
	const say = (button, text) => {
		const status = button.closest(".now-card")?.querySelector("[data-now-status]");
		if (status) status.textContent = text;
		else button.title = text;
	};

	document.addEventListener("click", async (e) => {
		const mark = e.target.closest("[data-mark-applied]");
		if (mark) {
			e.preventDefault();
			if (mark.disabled) return;
			const key = mark.dataset.markApplied || "";
			const cut = key.indexOf("|");
			const company = key.slice(0, cut);
			const role = key.slice(cut + 1);
			const label = mark.textContent;
			mark.disabled = true;
			mark.textContent = "Saving…";
			try {
				const res = await fetch("/api/interviews/applied", {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						"X-Requested-With": "XMLHttpRequest",
					},
					body: JSON.stringify({ company, role }),
				});
				const body = await res.json().catch(() => ({}));
				if (!res.ok || !body.ok) throw new Error(body.error || `HTTP ${res.status}`);
				mark.textContent = "Applied";
				say(mark, `Logged ${company} as applied today; follow-up scheduled.`);
				setTimeout(() => location.reload(), 600);
			} catch (err) {
				mark.disabled = false;
				mark.textContent = label;
				say(mark, `Not saved: ${err.message}`);
			}
			return;
		}

		const scroll = e.target.closest("[data-now-scroll]");
		if (scroll) {
			document.getElementById(scroll.dataset.nowScroll)?.scrollIntoView({
				block: "start",
				behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
			});
			return;
		}

		if (e.target.closest("[data-now-refresh]")) location.reload();
	});

	// The plan is built for one routine block; once it ends, say so instead of
	// silently showing the wrong directive. Never reloads on its own: a form on
	// the page may hold unsaved text.
	const card = document.querySelector(".now-card[data-now-until]");
	const until = card && Date.parse(card.dataset.nowUntil);
	if (!until) return;
	const check = () => {
		if (Date.now() >= until) {
			card.querySelector("[data-now-stale]").hidden = false;
			clearInterval(timer);
		}
	};
	const timer = setInterval(check, 60_000);
	document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && check());
	check();
})();
