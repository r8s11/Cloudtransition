// Tasks tab (templates/pages/tasks.html): realm filter pills and multi-select prompt generation.
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

