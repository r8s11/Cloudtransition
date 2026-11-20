/* Calendar reads and local schedules. Publishing belongs to the server worker. */
(() => {
  const $ = (id) => document.getElementById(id);
  const card = $("calendarCard");
  if (!card) return;
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  let snapshot = null;
  let reviewed = null;
  let busy = false;
  const configForm = $("calendarConfigForm");
  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }
  async function request(path, data) {
    const response = await fetch(`/api/calendar${path}`, {
      method: data === undefined ? "GET" : "POST",
      headers: data === undefined ? {} : {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
      ...(data === undefined ? {} : {body: JSON.stringify(data)}),
      signal: AbortSignal.timeout(45000),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Calendar request failed; local work is unchanged.");
    return result;
  }
  function say(message, settings = false) {
    $(settings ? "calendarSettingsStatus" : "calendarStatus").textContent = message;
  }
  function googleLink(value) {
    try {
      const url = new URL(value);
      return url.protocol === "https:" && ["calendar.google.com", "tasks.google.com", "www.google.com"].includes(url.hostname) ? url.href : null;
    } catch { return null; }
  }
  function scheduleText(schedule) {
    if (schedule.date) return `${schedule.date} · Task`;
    if (schedule.start) return `${schedule.start} – ${schedule.end} · ${schedule.timezone} · Event`;
    return "Needs date · local only";
  }
  function addItem(list, item, detail) {
    const li = node("li");
    const body = node("div");
    body.append(node("strong", item.title || "Untitled event"), node("p", detail, "calendar-note"));
    li.append(body);
    const link = googleLink(item.url);
    if (link) {
      const a = node("a", "Open in Google", "calendar-google-link");
      a.href = link; a.target = "_blank"; a.rel = "noopener noreferrer";
      li.append(a);
    }
    list.append(li);
  }
  function options(container, choices, selected, name) {
    const active = document.activeElement;
    if (container.contains(active)) return;
    container.replaceChildren();
    for (const choice of choices) {
      const label = node("label", undefined, "calendar-choice");
      const input = node("input"); input.type = "checkbox"; input.name = name; input.value = choice.id;
      input.checked = selected.includes(choice.id);
      input.disabled = choice.available === false;
      label.append(input, node("span", `${choice.name}${choice.file ? ` · ${choice.file}` : ""}${choice.available === false ? ` — Unavailable: ${choice.reason}` : ""}`));
      container.append(label);
    }
    if (!choices.length) container.append(node("p", "Connect and Refresh to load choices.", "calendar-note"));
  }
  function selectChoices(select, choices, selected) {
    if (document.activeElement === select) return;
    select.replaceChildren(new Option("Choose destination", ""));
    for (const choice of choices) select.add(new Option(choice.name, choice.id));
    select.value = selected || "";
  }
  function render(data, updateSettings = false) {
    snapshot = data;
    const agenda = data.agenda || {};
    const config = data.config || {};
    const connection = data.connection || {};
    $("calendarTimezone").textContent = agenda.timezone || config.timezone || zone;
    $("calendarConnection").textContent = `Calendar: ${connection.calendar || "disconnected"} · Google Tasks: ${connection.tasks || "disconnected"}. Connect Google Calendar on the Mac when disconnected; reconnect only the rejected grant.`;
    $("calendarPause").hidden = !data.enabled;
    $("calendarUpdated").textContent = `${data.enabled ? "Automation enabled" : data.status === "disabled" ? "Automation off" : "Automation paused"} · ${agenda.updated ? `Last successful refresh: ${agenda.updated}` : "No successful refresh yet"}. ${data.pause_note || "A request already in progress may finish."}`;
    const failures = Object.values(agenda.errors || {});
    const status = agenda.state;
    say(["ready", "empty"].includes(status) ? ((agenda.items || []).length ? "Upcoming events and tracked Google Tasks" : "No upcoming events") : status === "partial" ? "Some sources unavailable — successful results remain visible; stale rows are labeled." : status === "stale" ? "Unavailable — showing stale results from the last successful refresh. Refresh to retry." : "Calendar unavailable or not connected. Open Settings, connect on the Mac, then Refresh.");
    if (failures.length) say(`${$("calendarStatus").textContent} ${failures.join(" · ")}`);
    if (agenda.truncated) say(`${$("calendarStatus").textContent} Results truncated; open Google for the full agenda.`);
    const list = $("calendarAgenda"); list.replaceChildren();
    for (const item of agenda.items || []) {
      let when = item.date || "";
      if (item.start && !item.all_day) {
        const start = new Date(item.start);
        when = Number.isNaN(start.getTime()) ? item.start : new Intl.DateTimeFormat(undefined, {timeZone: agenda.timezone || config.timezone || zone, dateStyle: "medium", timeStyle: "short"}).format(start);
      }
      addItem(list, item, `${when}${item.all_day ? " · All day" : ""} · ${item.kind === "task" ? "Task" : "Event"} · ${item.calendar || item.source || "Google"}${item.stale ? " · Stale" : ""}`);
    }
    const outcomes = $("calendarOutcomeList"); outcomes.replaceChildren();
    for (const item of data.outcomes || []) addItem(outcomes, item, `${["published", "already_published"].includes(item.status) ? "Added to Google" : "Needs review"} · ${item.kind || ""} · ${item.source || ""} · ${item.status}`);
    $("calendarOutcomes").hidden = !(data.outcomes || []).length;
    if (updateSettings) {
      options($("calendarReadChoices"), data.choices?.calendars || [], config.calendars || [], "calendars");
      options($("calendarSourceChoices"), data.sources || [], config.sources || [], "sources");
      selectChoices(configForm.elements.event_calendar, (data.choices?.calendars || []).filter(c => c.writable), config.event_calendar);
      selectChoices(configForm.elements.tasklist, data.choices?.tasklists || [], config.tasklist);
      configForm.elements.timezone.value = config.timezone || zone;
    }
  }
  function config() {
    return {calendars: Array.from(configForm.querySelectorAll('[name="calendars"]:checked'), el => el.value), event_calendar: configForm.elements.event_calendar.value,
      tasklist: configForm.elements.tasklist.value, timezone: configForm.elements.timezone.value, sources: Array.from(configForm.querySelectorAll('[name="sources"]:checked'), el => el.value)};
  }
  function resetReview() {
    reviewed = null; $("calendarReview").hidden = true; $("calendarConsent").checked = false; $("calendarEnable").disabled = true;
  }
  async function refresh() {
    if (busy) return;
    busy = true; $("calendarRefresh").disabled = true; say("Loading events…");
    try { render(await request("/refresh", {}), true); }
    catch (error) { say(`Unavailable — ${error.message} Last displayed data is stale.`); }
    finally { busy = false; $("calendarRefresh").disabled = false; }
  }
  $("calendarRefresh").addEventListener("click", refresh);
  $("calendarPause").addEventListener("click", async () => {
    try {
      render(await request("/pause", {})); resetReview();
      const message = "Automation paused. A request already in progress may finish.";
      say(message); say(message, true);
    }
    catch (error) { say(error.message); }
  });
  configForm.addEventListener("change", resetReview);
  configForm.addEventListener("submit", async event => {
    event.preventDefault(); resetReview(); say("Reviewing allowed sources…", true);
    try {
      reviewed = await request("/preview", config());
      $("calendarBacklog").replaceChildren();
      for (const item of reviewed.backlog || []) addItem($("calendarBacklog"), item, `${item.source} · ${scheduleText(item.schedule || {})} · ${item.destination || ""} · ${item.status}`);
      if (!(reviewed.backlog || []).length) $("calendarBacklog").append(node("li", "No eligible backlog. Future explicitly scheduled work from these sources follows the same rule."));
      $("calendarReviewDestinations").textContent = `${reviewed.disclosure} Read calendars: ${reviewed.config.calendars.join(", ")}. Event destination: ${reviewed.config.event_calendar}. Tasks list: ${reviewed.config.tasklist}. Timezone: ${reviewed.config.timezone}. Sources: ${reviewed.config.sources.map(id => snapshot.sources.find(s => s.id === id)?.file || id).join(", ")}.`;
      $("calendarReview").hidden = false; say("Review exact sources, destinations and outgoing titles before enabling.", true);
    } catch (error) { say(error.message, true); }
  });
  $("calendarSaveView").addEventListener("click", async () => {
    try { render(await request("/config", config()), true); resetReview(); say("View saved. Automation is off; Refresh to read the selected calendars.", true); await refresh(); }
    catch (error) { say(error.message, true); }
  });
  $("calendarConsent").addEventListener("change", event => { $("calendarEnable").disabled = !event.target.checked || !reviewed; });
  $("calendarEnable").addEventListener("click", async () => {
    if (!reviewed || !$("calendarConsent").checked) return;
    $("calendarEnable").disabled = true;
    try { render(await request("/enable", {config: reviewed.config, review: reviewed.review}), true); resetReview(); say("Automation enabled for the reviewed policy. The server checks every 60 seconds.", true); }
    catch (error) { say(error.message, true); resetReview(); }
  });

  function field(label, name, type, value = "") {
    const wrap = node("label", label);
    const input = node("input"); input.className = "run-input"; input.name = name; input.type = type; input.value = value;
    wrap.append(input); return wrap;
  }
  function fields(container, schedule = {}) {
    container.classList.add("calendar-fields");
    const label = node("label", "Schedule type"); const mode = node("select"); mode.name = "calendar_mode"; mode.className = "run-input";
    mode.add(new Option("Local only / no date", "local")); mode.add(new Option("Date → Task", "task")); mode.add(new Option("Time → Event", "event"));
    mode.value = schedule.start ? "event" : schedule.date ? "task" : "local"; label.append(mode);
    const day = field("Task date", "calendar_date", "date", schedule.date);
    const start = field("Event start (local time)", "calendar_start", "datetime-local", schedule.start);
    const end = field("Event end (local time)", "calendar_end", "datetime-local", schedule.end);
    const tz = field("Event timezone (IANA)", "calendar_timezone", "text", schedule.timezone || snapshot?.config?.timezone || zone);
    container.append(label, day, start, end, tz);
    const update = () => {
      day.hidden = mode.value !== "task";
      for (const el of [start, end, tz]) el.hidden = mode.value !== "event";
      day.querySelector("input").required = mode.value === "task";
      for (const el of [start, end, tz]) el.querySelector("input").required = mode.value === "event";
    };
    mode.addEventListener("change", update); update();
  }
  function readSchedule(form) {
    const f = name => form.querySelector(`[name="calendar_${name}"]`)?.value || "";
    if (f("mode") === "task") {
      if (!f("date")) throw new Error("Choose an explicit task date.");
      return {date: f("date")};
    }
    if (f("mode") === "event") {
      if (!f("start") || !f("end") || !f("timezone")) throw new Error("Events require explicit start, end and IANA timezone.");
      return {start: f("start"), end: f("end"), timezone: f("timezone")};
    }
    return {};
  }
  function attachTaskButtons(root = document) {
    root.querySelectorAll('.task-check[data-calendar-source]').forEach(box => {
      const row = box.closest(".task-item");
      if (!row || row.querySelector(".calendar-schedule-button")) return;
      const button = node("button", "Schedule", "action-btn action-btn-ghost calendar-schedule-button"); button.type = "button";
      button.dataset.calendarTask = "true"; row.append(button);
    });
  }
  document.addEventListener("calendar:capture", event => attachTaskButtons(event.detail));
  document.addEventListener("click", event => {
    const button = event.target.closest(".calendar-schedule-button");
    if (!button) return;
    const row = button.closest(".task-item, .calendar-interview-action");
    const existing = row.querySelector(".calendar-schedule-form");
    if (existing) { existing.hidden = !existing.hidden; button.setAttribute("aria-expanded", String(!existing.hidden)); if (!existing.hidden) existing.querySelector("select").focus(); return; }
    const box = row.querySelector(".task-check");
    const form = node("form", undefined, "calendar-schedule-form");
    const title = node("h4", "Schedule underlying local action");
    const inputs = node("div"); fields(inputs, JSON.parse(button.dataset.calendarSchedule || box?.dataset.calendarSchedule || "{}"));
    const note = node("p", "Saves locally first. Removing a date does not delete an existing Google item. Published source edits require review.", "calendar-note");
    const actions = node("div", undefined, "calendar-actions");
    const save = node("button", "Save schedule", "action-btn"); save.type = "submit";
    const close = node("button", "Close", "action-btn action-btn-ghost"); close.type = "button";
    close.addEventListener("click", () => { form.hidden = true; button.setAttribute("aria-expanded", "false"); button.focus(); });
    actions.append(save, close);
    const status = node("p", undefined, "run-status"); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    form.append(title, inputs, note, actions, status); row.append(form); button.setAttribute("aria-expanded", "true");
    form.querySelector("select").focus();
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const focusBefore = document.activeElement;
      save.disabled = true;
      try {
        const schedule = readSchedule(form);
        const payload = button.dataset.calendarInterview ? JSON.parse(button.dataset.calendarInterview) : {source: box.dataset.calendarSource, line: Number(box.dataset.line), text: box.dataset.text};
        const result = await request("/schedule", {...payload, schedule});
        button.dataset.calendarSchedule = JSON.stringify(schedule);
        for (const item of (result.items || []).filter(item => item.text === payload.text.replace(/\s*<!--\s*calendar:[\s\S]*?-->/g, "").trim())) {
          document.querySelectorAll('.task-check[data-calendar-source]').forEach(check => {
            if (check.dataset.realm === item.realm && check.dataset.text === payload.text) {
              check.dataset.line = item.line; check.dataset.text = item.raw_text; check.dataset.calendarSchedule = JSON.stringify(item.schedule);
            }
          });
        }
        status.textContent = result.message; load(false);
      } catch (error) { status.textContent = `Not saved: ${error.message}`; }
      finally {
        save.disabled = false;
        if (focusBefore === save && document.activeElement === document.body) save.focus();
      }
    });
  });
  function updateInterviews(row, data) {
    row.querySelectorAll(".calendar-interview-action").forEach(el => el.remove());
    const main = row.querySelector(".interview-main");
    const steps = data.calendar_steps || [];
    for (const step of steps) {
      const wrap = node("div", undefined, "calendar-interview-action");
      const label = steps.length > 1 ? `Add to calendar · step ${step.index + 1}` : "Add to calendar";
      const button = node("button", label, "action-btn action-btn-ghost calendar-schedule-button"); button.type = "button";
      button.dataset.calendarInterview = JSON.stringify({source: "interviews", company: data.company, role: data.role, index: step.index, text: step.task});
      button.dataset.calendarSchedule = JSON.stringify(step.schedule); wrap.append(node("span", step.task), button); main.append(wrap);
    }
  }
  window.dashboardCalendar = {readSchedule, updateInterviews};
  document.querySelectorAll("[data-calendar-fields]").forEach(el => fields(el));
  attachTaskButtons();
  async function load(settings) {
    try { render(await request(""), settings); }
    catch (error) { say(`Unavailable — ${error.message}`); }
  }
  load(true).then(refresh);
  setInterval(() => {
    if (!document.hidden && $("page-today").classList.contains("active") && !$("calendarSettings").open) refresh();
  }, 60000);
})();
