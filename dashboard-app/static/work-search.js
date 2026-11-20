/* Explicit completed activities; no status-to-activity inference. */
(() => {
  const root = document.getElementById("workSearch");
  if (!root) return;
  const form = document.getElementById("workSearchForm");
  const period = document.getElementById("workSearchPeriod");
  const list = document.getElementById("workSearchActivities");
  const summary = document.getElementById("workSearchSummary");
  const status = document.getElementById("workSearchStatus");
  const saveStatus = document.getElementById("workSearchSaveStatus");
  const copyWeek = document.getElementById("workSearchCopy");
  const reportText = document.getElementById("workSearchText");
  const editor = document.getElementById("workSearchEditor");
  const application = document.getElementById("workSearchApplication");
  const saveButton = form.querySelector('[type="submit"]');
  const newButton = document.getElementById("workSearchNew");
  let generation = 0;
  let saving = false;
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    node.className = className;
    node.textContent = text;
    return node;
  };
  const say = (node, text, failed = false) => {
    node.textContent = text;
    node.className = `run-status ${failed ? "is-failed" : ""}`;
  };
  async function request(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed. Check the entered details and try again.");
    return data;
  }
  async function copy(text) {
    document.getElementById("workSearchManual").hidden = true;
    try {
      await navigator.clipboard.writeText(text);
      say(status, "Copied.");
    } catch {
      const manual = document.getElementById("workSearchManual");
      const selectedText = document.getElementById("workSearchClipboard");
      manual.hidden = false;
      selectedText.value = text;
      selectedText.focus();
      selectedText.select();
      let copied = false;
      try { copied = document.execCommand("copy"); } catch { /* Manual selection remains available. */ }
      manual.hidden = copied;
      say(status, copied ? "Copied." : "Clipboard unavailable. Copy the selected text below.", !copied);
    }
  }
  function reset() {
    form.reset();
    form.elements.id.value = crypto.randomUUID();
    say(saveStatus, "");
    editor.querySelector("summary").textContent = "Log a completed activity";
  }
  function edit(row) {
    if (saving) return;
    application.value = "";
    for (const key of ["id", "date", "activity_type", "description", "position", "employer", "address", "result"]) {
      form.elements[key].value = row[key];
    }
    say(saveStatus, "Editing saved activity. Save to replace this entry, or choose New activity.");
    editor.querySelector("summary").textContent = "Edit completed activity";
    editor.open = true;
    form.elements.date.focus();
  }
  function render(data) {
    period.elements.start.value = data.start;
    reportText.value = data.text;
    copyWeek.disabled = data.activities.length === 0;
    summary.textContent = `${data.start} – ${data.end} · ${data.activities.length} recorded ${data.activities.length === 1 ? "activity" : "activities"}`;
    list.replaceChildren();
    if (!data.activities.length) {
      list.append(element("p", "run-empty", "No completed activities recorded for this week. Log an activity below; missing records do not prove no activity occurred."));
      return;
    }
    for (const row of data.activities) {
      const article = element("article", "work-search-activity", "");
      const heading = element("div", "work-search-heading", "");
      heading.append(element("h4", "", `${row.employer} — ${row.description}`));
      const actions = element("div", "work-search-actions", "");
      const copyButton = element("button", "action-btn action-btn-ghost", "Copy activity");
      copyButton.type = "button";
      copyButton.addEventListener("click", () => copy(row.text));
      const editButton = element("button", "action-btn action-btn-ghost", "Edit activity");
      editButton.type = "button";
      editButton.addEventListener("click", () => edit(row));
      actions.append(copyButton, editButton);
      heading.append(actions);
      article.append(heading);
      if (row.missing.length) article.append(element("p", "interview-note", `Missing: ${row.missing.join(", ")}. Review before using this report.`));
      const fields = element("dl", "work-search-fields", "");
      for (const field of row.fields) {
        const group = element("div", "work-search-field", "");
        group.append(element("dt", "", field.label), element("dd", "", field.value || "Not recorded"));
        const button = element("button", "action-btn action-btn-ghost", "Copy field");
        button.type = "button";
        button.disabled = !field.value;
        button.setAttribute("aria-label", `Copy ${field.label} for ${row.employer} on ${row.date}`);
        button.addEventListener("click", () => copy(field.value));
        group.append(button);
        fields.append(group);
      }
      article.append(fields);
      list.append(article);
    }
  }
  async function load(start = "") {
    const current = ++generation;
    copyWeek.disabled = true;
    document.getElementById("workSearchManual").hidden = true;
    list.replaceChildren();
    reportText.value = "";
    list.setAttribute("aria-busy", "true");
    summary.textContent = "Loading recorded activities…";
    say(status, "");
    try {
      const data = await request(`/api/career/work-search${start ? `?start=${encodeURIComponent(start)}` : ""}`);
      if (current !== generation) return;
      render(data);
    } catch (error) {
      if (current !== generation) return;
      summary.textContent = "Report unavailable";
      say(status, `${error.message} Choose Show week to retry.`, true);
    } finally {
      if (current === generation) list.setAttribute("aria-busy", "false");
    }
  }
  period.addEventListener("submit", (event) => {
    event.preventDefault();
    load(period.elements.start.value);
  });
  application.addEventListener("change", () => {
    const selected = application.selectedOptions[0];
    if (!selected.value) return;
    form.elements.employer.value = selected.dataset.employer;
    form.elements.position.value = selected.dataset.position;
    // A job location is not a verified employer address.
    form.elements.address.value = "";
    form.elements.result.value = "";
  });
  copyWeek.addEventListener("click", () => copy(reportText.value));
  newButton.addEventListener("click", () => { reset(); form.elements.date.focus(); });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saving) return;
    saving = true;
    saveButton.disabled = true;
    newButton.disabled = true;
    say(saveStatus, "Saving completed activity…");
    const payload = Object.fromEntries(new FormData(form));
    try {
      await request("/api/career/work-search", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
        body: JSON.stringify(payload),
      });
      // Keep the ID after save so retrying or correcting does not duplicate it.
      editor.querySelector("summary").textContent = "Edit completed activity";
      say(saveStatus, "Activity saved. Choose New activity to log another.");
      const start = period.elements.start.value;
      const day = new Date(`${payload.date}T12:00:00Z`);
      const first = new Date(`${start}T12:00:00Z`);
      const weekStart = start
        ? new Date(first.getTime() + Math.floor((day - first) / (7 * 86400000)) * 7 * 86400000).toISOString().slice(0, 10)
        : payload.date;
      await load(weekStart);
    } catch (error) {
      say(saveStatus, `Not saved: ${error.message}`, true);
    } finally {
      saving = false;
      saveButton.disabled = false;
      newButton.disabled = false;
    }
  });
  reset();
  load();
})();
