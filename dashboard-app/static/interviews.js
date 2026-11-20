// Interviews tab (templates/pages/interviews.html): inline tracker edits and Interview mode dialog.

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
	const waitingStatuses = new Set(
		(page.dataset.interviewWaiting || "").split(",").filter(Boolean),
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
		if (window.dashboardCalendar) window.dashboardCalendar.updateInterviews(row, data);
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
		page.dispatchEvent(new CustomEvent("interview:next", { detail: { row, data } }));
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
				// The deck list regroups its row; the detail stays on this entry.
				page.dispatchEvent(
					new CustomEvent("interview:status", { detail: { row, data: body.row } }),
				);
				const deck = page.classList.contains("deck");
				// Closed threads leave the live cards for the collapsed Closed list;
				// reopening a row sends it back to the card its new status belongs to.
				let target
				if (closedStatuses.has(body.row.status)) {
					target = page.querySelector("[data-interview-list-closed]");
				} else {
					const sectionKey = waitingStatuses.has(body.row.status)
						? "waiting"
						: activeStatuses.has(body.row.status)
							? "active"
							: "leads";
					target = page.querySelector(
						`[data-interview-section="${sectionKey}"] [data-interview-list]`,
					);
				}
				if (target) {
					if (row.parentElement !== target) target.appendChild(row);
				} else if (deck) {
					// List–detail view: the entry stays put; deck-interviews.js regroups the list row.
				} else if (waitingStatuses.has(body.row.status)) {
					// No Waiting card rendered yet; the server builds it on reload.
					window.location.reload();
					return;
				} else if (closedStatuses.has(body.row.status)) {
					// No Closed list on the page yet; the next load will show it.
					row.remove();
				}
				if (status) {
					const at = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
					status.textContent = `Saved ${at}`;
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
