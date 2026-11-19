// Today tab (templates/pages/today.html): capture form and second brain.
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
		let schedule;
		try {
			schedule = window.dashboardCalendar.readSchedule(captureForm);
		} catch (error) {
			captureStatus.textContent = error.message;
			submit.disabled = false;
			return;
		}
		post("/api/capture", { text: captureInput.value, schedule })
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
				box.dataset.text = body.raw_text || body.text;
				box.dataset.calendarSource = body.realm;
				box.dataset.calendarSchedule = JSON.stringify(body.schedule || {});
				box.dataset.line = String(body.line);
				const span = document.createElement("span");
				span.className = "task-text";
				span.textContent = body.text;
				row.append(box, span);
				paintTaskCheck(box, false);
				inboxList.appendChild(row);
				document.dispatchEvent(new CustomEvent("calendar:capture", { detail: row }));
				bindTaskCheck(box);
				inboxCount.textContent = String(inboxList.children.length);
				inboxEmpty.hidden = true;
				captureForm.reset();
				captureStatus.textContent = `Saved locally to TASKS.md:${body.line}. Google outcome appears in Upcoming calendar.`;
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
					// shortcut: /workspace-file serves only files in the Workspace map
					// index, so a cite outside it (agent runtime data) opens a 404.
					const cite = document.createElement("a");
					cite.className = "brain-cite";
					cite.href = "/workspace-file/" + ev.path.split("/").map(encodeURIComponent).join("/");
					cite.target = "_blank";
					cite.rel = "noopener noreferrer";
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


