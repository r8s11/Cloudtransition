// Spatial Today hero (templates/pages/today.html, static/spatial.css).
// - Pointer parallax on the reticle and a live clock.
// - Live arcs: the outer arc is the Weekly Review (#routineReviewProgress), the
//   inner arc is how far through the week we are (Monday 00:00 → Sunday 24:00).
// - Lock-on: when something real happens on Today (a task folds, a capture lands
//   in the inbox, a review box is checked, a run starts) the brackets snap in and
//   a ring flashes from the core. Reduced motion keeps the values, skips the motion.
(() => {
	const hero = document.querySelector("[data-fui-hero]");
	if (!hero) return;
	const page = hero.closest(".page") || document;
	const still = window.matchMedia("(prefers-reduced-motion: reduce)");
	const visible = () => !document.hidden && hero.offsetParent !== null;

	const clock = hero.querySelector("[data-fui-clock]");
	const weekArc = hero.querySelector("[data-fui-week]");
	const tick = () => {
		const now = new Date();
		if (clock) {
			clock.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
			clock.dateTime = now.toISOString();
		}
		if (weekArc) {
			const day = (now.getDay() + 6) % 7; // Monday = 0
			const minutes = day * 1440 + now.getHours() * 60 + now.getMinutes();
			const pct = ((minutes / (7 * 1440)) * 100).toFixed(2);
			if (weekArc.dataset.pct !== pct) {
				weekArc.dataset.pct = pct;
				weekArc.setAttribute("stroke-dasharray", `${pct} 100`);
			}
		}
	};
	tick();
	setInterval(() => {
		if (visible()) tick();
	}, 1000);

	// One lock-on at a time; a new event restarts it rather than stacking.
	const lock = hero.querySelector("[data-fui-lock]");
	const flash = hero.querySelector("[data-fui-flash]");
	const reticle = hero.querySelector(".fui-reticle");
	let running = [];
	const lockOn = () => {
		if (still.matches || !visible() || !lock || !flash || !lock.animate) return;
		running.forEach((a) => a.cancel());
		const ease = "cubic-bezier(0.16, 1, 0.3, 1)";
		running = [
			lock.animate(
				[
					{ transform: "scale(1)" },
					{ transform: "scale(0.8) rotate(-8deg)", offset: 0.35 },
					{ transform: "scale(1.03) rotate(1deg)", offset: 0.7 },
					{ transform: "scale(1)" },
				],
				{ duration: 620, easing: ease },
			),
			flash.animate(
				[
					{ opacity: 0.95, transform: "scale(0.6)" },
					{ opacity: 0, transform: "scale(4.4)" },
				],
				{ duration: 720, easing: ease },
			),
			// Brighten the SVG only: a filter on the hero would drop the pills' backdrop blur.
			reticle.animate(
				[{ filter: "brightness(1.4)" }, { filter: "brightness(1)" }],
				{ duration: 520, easing: ease },
			),
		];
	};

	// Weekly Review → outer arc and readout.
	const reviewArc = hero.querySelector("[data-fui-review]");
	const reviewText = hero.querySelector("[data-fui-review-text]");
	const progress = document.getElementById("routineReviewProgress");
	const syncReview = () => {
		const m = /(\d+)\s+of\s+(\d+)/.exec(progress.textContent);
		if (!m || !+m[2]) return;
		const pct = ((100 * +m[1]) / +m[2]).toFixed(2);
		if (reviewArc) reviewArc.setAttribute("stroke-dasharray", `${pct} 100`);
		if (reviewText) reviewText.textContent = `REVIEW ${m[1]}/${m[2]}`;
	};
	if (progress) {
		new MutationObserver(() => {
			syncReview();
			lockOn();
		}).observe(progress, { childList: true, characterData: true, subtree: true });
	}

	// Inbox count mirror; a capture or triage is a lock-on.
	const count = document.getElementById("inboxCount");
	const mirror = hero.querySelector("[data-fui-inbox]");
	if (count && mirror) {
		new MutationObserver(() => {
			if (mirror.textContent === count.textContent) return;
			mirror.textContent = count.textContent;
			lockOn();
		}).observe(count, { childList: true, characterData: true, subtree: true });
	}

	// A task folding on Today (Next up, Inbox) or a run starting is a lock-on.
	// Review checks are covered by the progress observer above.
	new MutationObserver((records) => {
		for (const r of records) {
			const el = r.target;
			const was = r.oldValue || "";
			if (el.classList.contains("task-check") && !el.closest("#routineReviewList")
				&& el.classList.contains("done") && !/\bdone\b/.test(was)) return lockOn();
			if (el.classList.contains("run-status") && el.classList.contains("is-running")
				&& !/\bis-running\b/.test(was)) return lockOn();
		}
	}).observe(page, { attributes: true, attributeFilter: ["class"], attributeOldValue: true, subtree: true });

	// Tilt within ±5.5deg, as in the reference; off for touch and reduced motion.
	const flat = window.matchMedia("(prefers-reduced-motion: reduce), (hover: none)");
	let frame = 0;
	window.addEventListener("pointermove", (e) => {
		if (flat.matches || frame || !visible()) return;
		frame = requestAnimationFrame(() => {
			frame = 0;
			const nx = (2 * e.clientX) / window.innerWidth - 1;
			const ny = (2 * e.clientY) / window.innerHeight - 1;
			hero.style.setProperty("--tilt-x", `${(-ny * 5.5).toFixed(2)}deg`);
			hero.style.setProperty("--tilt-y", `${(nx * 5.5).toFixed(2)}deg`);
		});
	});
})();
