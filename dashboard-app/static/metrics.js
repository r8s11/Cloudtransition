/* Read-only server operations: snapshots, bounded history, and source coverage. */
(() => {
	const page = document.getElementById("page-metrics");
	if (!page) return;
	const $ = (selector) => page.querySelector(selector);
	const refresh = $("#metrics-refresh");
	const hostSelect = $("#metrics-host");
	const windowSelect = $("#metrics-window");
	let snapshot = null;
	let history = null;
	let selected = "parrot";
	let snapshotTimer = null;
	let historyTimer = null;
	let fetching = false;
	let snapshotFailed = false;
	let historyRequest = null;
	let historyGeneration = 0;
	let historyLoading = false;
	let historyFailed = false;
	let containerLimit = 20;
	let serviceLimit = 20;
	let processLimit = 20;
	let charts = null;
	let chartsLoading = true;
	let chartsRequest = null;
	let chartsGeneration = 0;
	let rankBy = "cpu";

	function node(tag, text, className) {
		const element = document.createElement(tag);
		if (text !== undefined) element.textContent = text;
		if (className) element.className = className;
		return element;
	}
	function text(selector, value) { $(selector).textContent = value; }
	function numeric(value, digits = 0) {
		return Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : "—";
	}
	function percent(value) { return Number.isFinite(value) ? value.toFixed(1) + "%" : "—"; }
	function bytes(value, rate = false) {
		if (!Number.isFinite(value) || value < 0) return "—";
		const units = ["B", "KiB", "MiB", "GiB", "TiB"];
		let index = 0;
		while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
		return value.toFixed(index || (rate && value > 0 && value < 1) ? 1 : 0) + " " + units[index] + (rate ? "/s" : "");
	}
	function capacity(total, available) {
		if (!Number.isFinite(total) || !Number.isFinite(available) || total <= 0 || available < 0 || available > total) return "—";
		return ((total - available) / 1024 ** 3).toFixed(1) + " / " + (total / 1024 ** 3).toFixed(1) + " GiB";
	}
	function uptime(seconds) {
		if (!Number.isFinite(seconds) || seconds < 0) return "—";
		const minutes = Math.floor(seconds / 60), hours = Math.floor(minutes / 60);
		return hours >= 24 ? Math.floor(hours / 24) + "d " + hours % 24 + "h" : hours ? hours + "h " + minutes % 60 + "m" : minutes + "m";
	}
	function date(seconds, full = false) {
		const value = new Date(Number.isFinite(seconds) ? seconds * 1000 : NaN);
		return Number.isFinite(value.getTime()) ? (full ? value.toLocaleString() : value.toLocaleTimeString()) : "—";
	}
	function badge(label, state = "unknown") {
		const element = node("span", label, "metrics-state");
		element.dataset.state = state;
		return element;
	}
	function rows(selector, values) {
		const body = $(selector);
		body.replaceChildren();
		for (const valuesInRow of values) {
			const row = node("tr");
			valuesInRow.forEach((value, index) => {
				const cell = node(index === 0 ? "th" : "td");
				if (index === 0) cell.scope = "row";
				cell.append(value instanceof Node ? value : document.createTextNode(String(value ?? "—")));
				row.append(cell);
			});
			body.append(row);
		}
	}
	function tableVisible(selector, visible) {
		const table = $(selector);
		table.hidden = !visible;
		table.parentElement.hidden = !visible;
	}
	function hostData() { return snapshot?.infrastructure?.hosts?.[selected]; }
	function activityData() { return snapshot?.activity?.hosts?.[selected]; }
	function sourceMessage(source, kind) {
		if (!source || source.status === "unavailable") return kind + " source is unavailable. Current health is unknown.";
		if (source.status === "not_exported") return kind + " metrics are not exported for this server.";
		return "No " + kind.toLowerCase() + " rows in the current source response.";
	}

	function renderOverview() {
		for (const card of page.querySelectorAll("[data-host]")) {
			const name = card.dataset.host;
			const original = snapshot?.infrastructure?.hosts?.[name];
			const state = ["up", "down", "pending"].includes(original?.status) ? original.status : "unknown";
			const host = state === "up" ? original : null;
			const values = {
				status: !snapshot && !snapshotFailed ? "Checking" : { up: "Telemetry live", down: "Exporter down", pending: "Awaiting telemetry", unknown: "Unavailable" }[state],
				os_name: host?.os_name || "OS not exported",
				cpu_percent: percent(host?.cpu_percent), memory_percent: percent(host?.memory_percent), disk_percent: percent(host?.disk_percent),
				cpu_threads: Number.isFinite(host?.cpu_threads) ? numeric(host.cpu_threads) + " logical CPUs" : "—",
				memory_capacity: capacity(host?.memory_total_bytes, host?.memory_available_bytes),
				disk_capacity: capacity(host?.disk_total_bytes, host?.disk_available_bytes),
				volume_label: host?.system_volume ? "Volume " + host.system_volume : "System volume", uptime: uptime(host?.uptime_seconds),
				detail: state === "up" ? (host.exporter_job || "Host exporter") : state === "down" ? "Usage cleared; exporter is not responding." : state === "pending" ? "No host series received." : "Monitoring query unavailable.",
			};
			for (const element of card.querySelectorAll("[data-host-field]")) element.textContent = values[element.dataset.hostField];
			card.querySelector("[data-host-field='status']").dataset.state = state;
			card.dataset.selected = String(name === selected);
			card.querySelector("[data-select-host]").setAttribute("aria-pressed", String(name === selected));
		}
		for (const row of page.querySelectorAll("[data-project]")) {
			const project = snapshot?.projects?.find((item) => item.name === row.dataset.project);
			const labels = { up: "Responding", unknown: "Unavailable", unmonitored: "Not monitored" };
			const label = row.querySelector("[data-project-status]");
			label.textContent = labels[project?.status] || "Unavailable";
			label.dataset.state = project?.status || "unknown";
		}
	}

	function renderResources() {
		const original = hostData();
		const host = original?.status === "up" ? original : null;
		const platform = host?.platform || "unknown";
		text("#ops-server-context", selected + " · " + (host?.os_name || "OS not exported") + " · " + (host?.exporter_job || "source unavailable"));
		const readings = [["Logical CPUs", numeric(host?.cpu_threads)], ["Processes", numeric(host?.process_count)], ["Threads", numeric(host?.thread_count)]];
		if (platform === "windows") readings.push(["Processor queue", numeric(host?.processor_queue_length)]);
		else readings.push(["Load · 1 / 5 / 15 min", ["load1", "load5", "load15"].map((key) => numeric(host?.[key], 2)).join(" / ")], ["Runnable / blocked", numeric(host?.processes_running) + " / " + numeric(host?.processes_blocked)], ["CPU I/O wait", percent(host?.cpu_wait_percent)]);
		readings.push(["Swap / pagefile used", Number.isFinite(host?.swap_used_bytes) && Number.isFinite(host?.swap_total_bytes) ? bytes(host.swap_used_bytes) + " / " + bytes(host.swap_total_bytes) : "—"]);
		if (platform !== "windows") readings.push(["CPU / memory / I/O pressure", ["cpu_pressure_percent", "memory_pressure_percent", "io_pressure_percent"].map((key) => percent(host?.[key])).join(" / ")]);
		rows("#ops-resources-body", readings);
		rows("#ops-network-body", [["Ethernet / Wi-Fi", bytes(host?.physical_receive_bytes_per_second, true), bytes(host?.physical_transmit_bytes_per_second, true)], ["Tailscale", bytes(host?.tailscale_receive_bytes_per_second, true), bytes(host?.tailscale_transmit_bytes_per_second, true)]]);
		const facts = [["Kernel / build", host?.kernel], ["Architecture", host?.architecture], ["Memory available", bytes(host?.memory_available_bytes)], ["System volume available", bytes(host?.disk_available_bytes)], ["Exporter", host?.exporter_job], ["Instance", host?.exporter_instance], ["Sample · Prometheus clock", date(host?.sample_timestamp, true)]];
		$("#ops-host-facts").replaceChildren(...facts.map(([label, value]) => { const group = node("div"); group.append(node("dt", label), node("dd", value || "—")); return group; }));
		const volumes = Array.isArray(host?.volumes) ? host.volumes : [];
		tableVisible("#ops-volumes-table", volumes.length > 0);
		$("#ops-volumes-status").hidden = Boolean(volumes.length);
		text("#ops-volumes-status", host ? "No real volume metrics exported." : "Volume readings unavailable.");
		rows("#ops-volumes-body", volumes.map((volume) => [volume.name + (volume.name === host.system_volume ? " (system)" : ""), percent(volume.used_percent), bytes(volume.available_bytes) + " / " + bytes(volume.total_bytes), percent(volume.inode_used_percent), volume.readonly === true ? "Read-only" : volume.readonly === false ? "Read/write" : "Unknown"]));
		const disks = Array.isArray(host?.disks) ? host.disks : [];
		tableVisible("#ops-disks-table", disks.length > 0);
		$("#ops-disks-status").hidden = Boolean(disks.length);
		text("#ops-disks-status", host ? "Physical disk I/O is not exported." : "Disk I/O unavailable.");
		rows("#ops-disks-body", disks.map((disk) => [disk.device, bytes(disk.read_bytes_per_second, true), bytes(disk.write_bytes_per_second, true), percent(disk.busy_percent), numeric(disk.io_in_progress, 2)]));
	}

	function renderWorkloads() {
		const activity = activityData();
		const search = $("#ops-workload-search").value.trim().toLowerCase();
		const filter = $("#ops-service-filter").value;
		const processes = activity?.processes;
		const processRows = (processes?.rows || []).filter((item) => (item.name + " " + item.pid).toLowerCase().includes(search));
		text("#ops-processes-count", processes ? "· " + numeric(processes.total) + " observed" + (processes.limited ? " (source limit reached)" : "") : "");
		tableVisible("#ops-processes-table", processRows.length > 0);
		$("#ops-processes-status").hidden = processes?.status === "ok" && processRows.length > 0;
		text("#ops-processes-status", processes?.status === "ok" ? "No fresh processes match this filter." : sourceMessage(processes, "Per-process performance"));
		rows("#ops-processes-body", processRows.slice(0, processLimit).map((item) => [item.name, item.pid ?? "—", numeric(item.cpu_cores, 3), bytes(item.memory_bytes), numeric(item.threads), uptime(item.uptime_seconds)]));
		$("#ops-processes-more").hidden = processRows.length <= processLimit;
		text("#ops-processes-more", "Show more processes (" + Math.min(processLimit, processRows.length) + " / " + processRows.length + ")");
		const containers = activity?.containers;
		const containerRows = (containers?.rows || []).filter((item) => (item.name + " " + item.image).toLowerCase().includes(search));
		text("#ops-containers-count", containers ? "· " + numeric(containers.total) + " exported" : "");
		tableVisible("#ops-containers-table", containerRows.length > 0);
		$("#ops-containers-status").hidden = containers?.status === "ok" && containerRows.length > 0;
		text("#ops-containers-status", containers?.status === "ok" ? (containerRows.length ? "" : "No containers match this filter.") : sourceMessage(containers, "Container performance"));
		rows("#ops-containers-body", containerRows.slice(0, containerLimit).map((item) => {
			const title = node("span"); title.append(node("strong", item.name), node("small", String(item.image || "image not exported").split("@")[0]));
			const health = item.health || "unknown";
			return [title, numeric(item.cpu_cores, 3), bytes(item.memory_bytes), bytes(item.receive_bytes_per_second, true) + " / " + bytes(item.transmit_bytes_per_second, true), uptime(item.uptime_seconds), badge(health, health === "healthy" ? "up" : health === "unhealthy" ? "down" : "unknown")];
		}));
		$("#ops-containers-more").hidden = containerRows.length <= containerLimit;
		text("#ops-containers-more", "Show more containers (" + Math.min(containerLimit, containerRows.length) + " / " + containerRows.length + ")");
		const services = activity?.services;
		const serviceRows = (services?.rows || []).filter((item) => {
			const state = String(item.state || "unknown").toLowerCase();
			return (item.name + " " + item.display_name).toLowerCase().includes(search) && (filter === "all" || filter === state || (filter === "other" && !["running", "stopped"].includes(state)));
		});
		text("#ops-services-count", services ? "· " + numeric(services.total) + " exported" + (services.limited ? " (source limit reached)" : "") : "");
		tableVisible("#ops-services-table", serviceRows.length > 0);
		$("#ops-services-status").hidden = services?.status === "ok" && serviceRows.length > 0;
		text("#ops-services-status", services?.status === "ok" ? "No services match this filter." : sourceMessage(services, "Service state"));
		rows("#ops-services-body", serviceRows.slice(0, serviceLimit).map((item) => {
			const title = node("span"); title.append(node("strong", item.name), node("small", item.display_name || ""));
			return [title, item.state || "Unknown", item.start_mode || "—", item.pid ?? "—"];
		}));
		$("#ops-services-more").hidden = serviceRows.length <= serviceLimit;
		text("#ops-services-more", "Show more services (" + Math.min(serviceLimit, serviceRows.length) + " / " + serviceRows.length + ")");
		const probes = activity?.probes;
		const probeRows = probes?.rows || [];
		tableVisible("#ops-probes-table", probeRows.length > 0);
		$("#ops-probes-status").hidden = Boolean(probeRows.length);
		text("#ops-probes-status", sourceMessage(probes, "Target probe"));
		rows("#ops-probes-body", probeRows.map((item) => [item.service, String(item.kind || "unknown").toUpperCase(), item.target, badge(item.status || "unknown", item.status), Number.isFinite(item.duration_seconds) ? numeric(item.duration_seconds * 1000, 1) + " ms" : "—"]));
	}

	function renderActivity() {
		const activity = activityData(), logs = activity?.logs;
		const countsAvailable = logs && logs.queries?.counts !== "unavailable" && Number.isFinite(logs.total_count);
		text("#ops-log-summary", countsAvailable ? numeric(logs.total_count) + " events / 15 min · " + (Number.isFinite(logs.error_count) ? numeric(logs.error_count) + " error-labelled (" + numeric(logs.severity_known_count) + " severity-indexed)" : "severity not indexed") : "Activity counts unavailable");
		text("#ops-logs-status", !logs || logs.status === "unavailable" ? "Log source unavailable; this does not mean there was no activity." : logs.queries?.recent === "unavailable" ? "Recent log query unavailable; any activity counts are shown independently." : !logs.rows?.length ? "No log entries received in this window." : "");
		$("#ops-log-sources").replaceChildren(...(logs?.sources || []).slice(0, 12).map((source) => node("span", source.name + " · " + numeric(source.count))));
		const list = $("#ops-log-entries");
		const expanded = new Set([...list.querySelectorAll("details[open]")].map((item) => item.dataset.entry));
		const focusedEntry = document.activeElement.closest(".ops-log-entry")?.dataset.entry;
		list.replaceChildren();
		for (const entry of logs?.rows || []) {
			const detail = node("details", undefined, "ops-log-entry");
			detail.dataset.entry = entry.id || String(entry.timestamp) + ":" + entry.source;
			detail.open = expanded.has(detail.dataset.entry);
			const summary = node("summary");
			summary.append(node("time", date(entry.timestamp)), badge(entry.level || "unknown", ["error", "critical", "fatal"].includes(entry.level) ? "down" : "unknown"), node("strong", entry.source || "Unknown source"), node("span", String(entry.message || "").split("\n")[0].slice(0, 140)));
			detail.append(summary, node("pre", entry.message || "No message exported."));
			const item = node("li"); item.append(detail); list.append(item);
			if (focusedEntry === detail.dataset.entry) summary.focus({ preventScroll: true });
		}
		const coverage = [];
		if (!snapshot) coverage.push("Snapshot unavailable. Current host, workload, and log states are unknown.");
		else {
			const host = hostData();
			coverage.push(host?.status === "up" ? "Host telemetry received from " + (host.exporter_job || "an exporter") + ". Missing platform-specific values stay unavailable." : "Host telemetry is " + (host?.status || "unavailable") + "; no machine uptime claim is inferred.");
			for (const [key, label] of [["containers", "Container performance"], ["services", "System service states"], ["probes", "Target reachability probes"]]) coverage.push(label + ": " + (activity?.[key]?.status || "unavailable") + (activity?.[key]?.limited ? " · source row limit reached" : "") + ".");
			if (activity?.containers?.status === "not_exported" && logs?.sources?.some((item) => item.job === "docker")) coverage.push("Docker activity is present in logs, but this host does not export container CPU/memory metrics.");
			coverage.push("Per-process source: " + (activity?.processes?.status || "unavailable").replaceAll("_", " ") + ". Process names/PIDs and performance are shown only when exported.");
			coverage.push("GPU telemetry: " + (activity?.coverage?.gpu || "unavailable").replaceAll("_", " ") + ". No utilization is inferred from CPU activity.");
			coverage.push("AI job progress, token usage, and inference costs are not exported by these sources.");
		}
		$("#ops-coverage-list").replaceChildren(...coverage.map((message) => node("li", message)));
	}

	function svgNode(tag, attributes, textValue) {
		const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
		for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
		if (textValue !== undefined) element.textContent = textValue;
		return element;
	}
	function renderHistory() {
		const chart = $("#metrics-history-chart"); chart.replaceChildren();
		if (historyLoading) { chart.append(node("p", "Loading " + windowSelect.value + " of retained samples…")); return; }
		if (!history || history.status !== "ok") { chart.append(node("p", "History source unavailable. Current readings remain independent.")); return; }
		const series = history.hosts?.[selected] || {};
		const fields = ["cpu_percent", "memory_percent", "disk_percent"];
		const usable = fields.some((key) => series[key]?.some((point) => Number.isFinite(point[0]) && Number.isFinite(point[1])));
		if (!usable || !(history.end > history.start)) { chart.append(node("p", "No retained host samples in this window. No values are filled in.")); return; }
		const width = Math.max(200, Math.round(chart.clientWidth || 800)), right = width - 12;
		const valid = (point) => Number.isFinite(point[0]) && Number.isFinite(point[1]) && point[1] >= 0 && point[1] <= 100 && point[0] >= history.start && point[0] <= history.end;
		const names = ["CPU", "memory", "system volume"];
		const summary = fields.map((field, index) => {
			const values = (series[field] || []).filter(valid).map((point) => point[1]);
			return names[index] + (values.length ? " " + Math.min(...values).toFixed(1) + "–" + Math.max(...values).toFixed(1) + "%" : " no samples");
		}).join(", ");
		const svg = svgNode("svg", { viewBox: `0 0 ${width} 180`, role: "img", "aria-label": selected + " utilization over " + history.window + ": " + summary });
		svg.append(svgNode("title", {}, "Recorded host utilization, 0 to 100 percent"), svgNode("desc", {}, "CPU solid, memory dashed, system volume dotted. Gaps represent missing samples. Time is based on Prometheus."));
		for (const tick of [0, 50, 100]) {
			const y = 148 - tick * 1.28;
			svg.append(svgNode("line", { x1: 36, x2: right, y1: y, y2: y, class: "ops-chart-grid" }), svgNode("text", { x: 36, y: y + 4, "text-anchor": "end", class: "ops-chart-label" }, tick + "%"));
		}
		fields.forEach((field, index) => {
			let path = "", previous = null;
			const points = [...(series[field] || [])].sort((a, b) => a[0] - b[0]);
			for (const [timestamp, value] of points) {
				if (!Number.isFinite(timestamp) || !Number.isFinite(value) || value < 0 || value > 100 || timestamp < history.start || timestamp > history.end) { previous = null; continue; }
				const x = 36 + (timestamp - history.start) / (history.end - history.start) * (right - 36), y = 148 - value * 1.28;
				path += (previous === null || timestamp - previous > history.step_seconds * 1.6 ? "M" : "L") + x.toFixed(2) + "," + y.toFixed(2);
				previous = timestamp;
			}
			if (points.length === 1 && path) {
				const [timestamp, value] = points[0];
				svg.append(svgNode("circle", { cx: 36 + (timestamp - history.start) / (history.end - history.start) * (right - 36), cy: 148 - value * 1.28, r: 2.5, class: "ops-history-point ops-history-series-" + index }));
			}
			if (path) svg.append(svgNode("path", { d: path, class: "ops-history-line ops-history-series-" + index, fill: "none" }));
		});
		timeLabels(svg, history.start, history.end, 36, right, 174);
		chart.append(svg);
		const byTime = new Map();
		fields.forEach((field, index) => { for (const point of series[field] || []) if (valid(point)) { if (!byTime.has(point[0])) byTime.set(point[0], ["—", "—", "—"]); byTime.get(point[0])[index] = percent(point[1]); } });
		chart.append(dataTable("Host utilization", ["Time", "CPU busy", "Memory used", "System volume used"], [...byTime.entries()].sort((a, b) => a[0] - b[0]).map(([t, values]) => [date(t, history.end - history.start > 21600), ...values])));
	}
	/* ── Charts: hand-drawn SVG; missing samples stay gaps, never zero ── */
	const HOST_FIELDS = ["cpu_percent", "memory_percent", "disk_percent"];
	function widthOf(element) { return Math.max(240, Math.round(element.clientWidth || 520)); }
	function axisTime(seconds, start, end) {
		const label = date(seconds).replace(/:\d\d(\s|$)/, "$1");
		const first = new Date(start * 1000), last = new Date(end * 1000);
		if (!Number.isFinite(first.getTime()) || !Number.isFinite(last.getTime()) || first.toDateString() === last.toDateString()) return label;
		return new Date(seconds * 1000).toLocaleDateString(undefined, { weekday: "short" }) + " " + label;
	}
	function timeLabels(svg, start, end, x0, x1, y) {
		for (const [ratio, anchor] of [[0, "start"], [0.5, "middle"], [1, "end"]]) {
			svg.append(svgNode("text", { x: x0 + ratio * (x1 - x0), y, "text-anchor": anchor, class: "ops-chart-label" }, axisTime(start + ratio * (end - start), start, end)));
		}
	}
	function linePath(points, start, end, step, xOf, yOf) {
		let path = "", previous = null;
		for (const [timestamp, value] of points) {
			if (!Number.isFinite(timestamp) || !Number.isFinite(value) || timestamp < start || timestamp > end) { previous = null; continue; }
			path += (previous === null || timestamp - previous > step * 1.6 ? "M" : "L") + xOf(timestamp).toFixed(1) + "," + yOf(value).toFixed(1);
			previous = timestamp;
		}
		return path;
	}
	const openTables = new Set();
	function dataTable(caption, headers, rowsData) {
		const details = node("details", undefined, "ops-chart-data"), table = node("table", undefined, "ops-table");
		details.dataset.table = caption; details.open = openTables.has(caption);
		details.addEventListener("toggle", () => { if (details.open) openTables.add(caption); else openTables.delete(caption); });
		details.append(node("summary", "Data table"));
		table.append(node("caption", caption, "metrics-visually-hidden"));
		const head = node("tr"); headers.forEach((label) => { const cell = node("th", label); cell.scope = "col"; head.append(cell); });
		table.append(head);
		for (const values of rowsData) { const row = node("tr"); values.forEach((value) => row.append(node("td", value))); table.append(row); }
		details.append(table); return details;
	}

	function renderHostCharts() {
		const historyOk = history?.status === "ok" && history.end > history.start;
		for (const card of page.querySelectorAll("[data-host]")) {
			const name = card.dataset.host, host = snapshot?.infrastructure?.hosts?.[name];
			const live = host?.status === "up";
			for (const field of HOST_FIELDS) {
				const bar = card.querySelector(`[data-host-bar='${field}']`), value = live ? host[field] : null;
				bar.dataset.empty = String(!Number.isFinite(value));
				bar.querySelector("i").style.transform = "scaleX(" + (Number.isFinite(value) ? Math.min(100, Math.max(0, value)) / 100 : 0) + ")";
				const spark = card.querySelector(`[data-host-spark='${field}']`);
				spark.replaceChildren();
				const points = historyOk ? (history.hosts?.[name]?.[field] || []).filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1])) : [];
				if (!snapshot) { spark.append(node("small", snapshotFailed ? "Snapshot unavailable" : "Loading…")); continue; }
				if (!live) { spark.append(node("small", "No samples yet")); continue; }
				if (!historyOk) { spark.append(node("small", historyFailed ? "History unavailable" : "Loading history…")); continue; }
				if (!points.length) { spark.append(node("small", "No samples in " + history.window)); continue; }
				const values = points.map((p) => p[1]), low = Math.min(...values), high = Math.max(...values);
				// Never tighter than a 10-point band so small jitter is not exaggerated.
				const span = Math.max(10, high - low), floor = Math.max(0, Math.min(100 - span, (low + high) / 2 - span / 2));
				const w = 160, h = 28;
				const svg = svgNode("svg", { viewBox: `0 0 ${w} ${h}`, preserveAspectRatio: "none", role: "img", "aria-label": `${name} ${field.replace("_percent", "")} ${low.toFixed(1)}–${high.toFixed(1)}% over ${history.window}` });
				svg.append(svgNode("path", { d: linePath(points, history.start, history.end, history.step_seconds, (t) => (t - history.start) / (history.end - history.start) * w, (v) => h - 2 - (v - floor) / span * (h - 4)), class: "ops-spark-line ops-spark-" + field.split("_")[0], fill: "none" }));
				spark.append(svg, node("small", history.window + " · " + low.toFixed(1) + "–" + high.toFixed(1) + "%"));
			}
		}
	}

	function mirroredChart(title, upPoints, downPoints, labels, classes, section) {
		const figure = node("figure", undefined, "ops-chart ops-mirror");
		figure.append(node("figcaption", title));
		const values = [...upPoints, ...downPoints].map((p) => p[1]).filter(Number.isFinite);
		if (!values.length) { figure.append(node("p", "No retained samples for " + title + " in this window.")); return figure; }
		const W = widthOf(page.querySelector("#ops-net-charts")) / (window.matchMedia("(max-width: 900px)").matches ? 1 : 2) - 8;
		const H = 150, x0 = 84, x1 = W - 6, mid = 66, half = 52, max = Math.max(...values) || 1;
		const xOf = (t) => x0 + (t - section.start) / (section.end - section.start) * (x1 - x0);
		const svg = svgNode("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${title}: ${labels[0]} peak ${bytes(Math.max(0, ...upPoints.map((p) => p[1])), true)}, ${labels[1]} peak ${bytes(Math.max(0, ...downPoints.map((p) => p[1])), true)} over ${section.window}` });
		for (const y of [mid - half, mid, mid + half]) svg.append(svgNode("line", { x1: x0, x2: x1, y1: y, y2: y, class: "ops-chart-grid" }));
		svg.append(svgNode("text", { x: x0 - 6, y: mid - half + 4, "text-anchor": "end", class: "ops-chart-label" }, bytes(max, true)), svgNode("text", { x: x0 - 6, y: mid + 4, "text-anchor": "end", class: "ops-chart-label" }, "0"), svgNode("text", { x: x0 - 6, y: mid + half + 4, "text-anchor": "end", class: "ops-chart-label" }, bytes(max, true)));
		svg.append(svgNode("path", { d: linePath(upPoints, section.start, section.end, section.step_seconds, xOf, (v) => mid - v / max * half), class: "ops-history-line " + classes[0], fill: "none" }));
		svg.append(svgNode("path", { d: linePath(downPoints, section.start, section.end, section.step_seconds, xOf, (v) => mid + v / max * half), class: "ops-history-line ops-line-dashed " + classes[1], fill: "none" }));
		svg.append(svgNode("text", { x: x0 + 4, y: 12, class: "ops-chart-label" }, "↑ " + labels[0]), svgNode("text", { x: x0 + 4, y: mid + half - 2, class: "ops-chart-label" }, "↓ " + labels[1]));
		timeLabels(svg, section.start, section.end, x0, x1, H - 4);
		figure.append(svg);
		const byTime = new Map(); upPoints.forEach(([t, v]) => byTime.set(t, [bytes(v, true), "—"])); downPoints.forEach(([t, v]) => byTime.set(t, [byTime.get(t)?.[0] || "—", bytes(v, true)]));
		figure.append(dataTable(title, ["Time", labels[0], labels[1]], [...byTime.entries()].sort((a, b) => a[0] - b[0]).map(([t, pair]) => [date(t, section.end - section.start > 21600), ...pair])));
		return figure;
	}

	function renderRates() {
		const net = $("#ops-net-charts"), disks = $("#ops-disk-charts"), section = charts?.rates;
		net.replaceChildren(); disks.replaceChildren();
		const host = hostData();
		if (chartsLoading && !charts) {
			net.append(node("p", "Loading retained samples…", "ops-empty"));
			disks.append(node("p", "Loading retained samples…", "ops-empty")); return;
		}
		const hostRates = section?.status === "ok" ? section.hosts?.[selected] : null;
		const hasHistory = Boolean(hostRates) && (Object.values(hostRates.network || {}).some((pair) => pair.receive.length || pair.transmit.length) || Object.keys(hostRates.disks || {}).length > 0);
		if (section?.status !== "ok") {
			const current = host?.status === "up" ? " Current: Ethernet / Wi-Fi ↓ " + bytes(host.physical_receive_bytes_per_second, true) + " ↑ " + bytes(host.physical_transmit_bytes_per_second, true) + " · Tailscale ↓ " + bytes(host.tailscale_receive_bytes_per_second, true) + " ↑ " + bytes(host.tailscale_transmit_bytes_per_second, true) + "." : "";
			net.append(node("p", "Rate history unavailable." + current, "ops-empty ops-error"));
			disks.append(node("p", "Disk I/O history unavailable. Current rates remain in the disk table below.", "ops-empty ops-error")); return;
		}
		if (!hasHistory && host?.status !== "up") {
			net.append(node("p", "No interface metrics exported by " + selected + " yet.", "ops-empty")); disks.append(node("p", "No disk metrics exported by " + selected + " yet.", "ops-empty")); return;
		}
		const rates = section.hosts?.[selected];
		net.append(mirroredChart("Ethernet / Wi-Fi", rates.network.physical.receive, rates.network.physical.transmit, ["Receive", "Send"], ["ops-line-rx", "ops-line-tx"], section), mirroredChart("Tailscale", rates.network.tailscale.receive, rates.network.tailscale.transmit, ["Receive", "Send"], ["ops-line-rx", "ops-line-tx"], section));
		for (const [device, pair] of Object.entries(rates.disks || {})) disks.append(mirroredChart(device + " — read / write", pair.read, pair.write, ["Read", "Write"], ["ops-line-read", "ops-line-write"], section));
		const notes = [];
		if (rates.idle_disks?.length) notes.push("Idle in this window: " + rates.idle_disks.join(", ") + ".");
		if (rates.more_disks?.length) notes.push("Not drawn (busiest " + Object.keys(rates.disks).length + " shown): " + rates.more_disks.join(", ") + ".");
		if (!Object.keys(rates.disks || {}).length && !notes.length) notes.push("No physical disk I/O exported in this window.");
		if (notes.length) disks.append(node("p", notes.join(" "), "metrics-footnote"));
	}

	function renderStorageChart() {
		const chart = $("#ops-volumes-chart"), host = hostData();
		chart.replaceChildren();
		const volumes = host?.status === "up" && Array.isArray(host.volumes) ? host.volumes : [];
		for (const volume of volumes) {
			const used = volume.used_percent, row = node("div", undefined, "ops-volume-row");
			const name = node("div", volume.name + (volume.name === host.system_volume ? " (system)" : ""), "ops-volume-name");
			name.append(node("small", (volume.device || "") + (volume.readonly === true ? " · read-only" : "")));
			const bar = node("div", undefined, "ops-volume-bar"), fill = node("i");
			bar.setAttribute("role", "img"); bar.setAttribute("aria-label", `${volume.name} ${percent(used)} used, ${bytes(volume.available_bytes)} available of ${bytes(volume.total_bytes)}`);
			fill.dataset.level = used >= 90 ? "critical" : used >= 80 ? "high" : "normal";
			fill.style.transform = "scaleX(" + (Number.isFinite(used) ? Math.min(100, Math.max(0, used)) / 100 : 0) + ")";
			bar.append(fill, node("b"), node("b"));
			const numbers = node("div", undefined, "ops-volume-numbers"); numbers.append(node("strong", percent(used)), document.createTextNode(" used · " + bytes(volume.available_bytes) + " free of " + bytes(volume.total_bytes)));
			row.append(name, bar, numbers); chart.append(row);
		}
		if (volumes.length) chart.append(node("p", "Dashed ticks mark 80 % and 90 %; the bar turns yellow at ≥ 80 % and red at ≥ 90 %, with the same value in text.", "metrics-footnote"));
	}

	function rankedList(title, items, total) {
		const wrap = node("div", undefined, "ops-rank-block");
		wrap.append(node("h5", title + " · ranked by " + (rankBy === "cpu" ? "CPU cores" : "memory") + (total > items.length ? " · top " + items.length + " of " + total : ""), "ops-subheading"));
		const list = node("ol", undefined, "ops-rank"), key = rankBy === "cpu" ? "cpu_cores" : "memory_bytes";
		const max = Math.max(...items.map((item) => item[key]).filter(Number.isFinite), 0) || 1;
		for (const item of items) {
			const value = item[key], li = node("li", undefined, "ops-rank-item"), bar = node("span", undefined, "ops-rank-bar"), fill = node("i");
			fill.dataset.measure = rankBy; fill.style.transform = "scaleX(" + (Number.isFinite(value) ? value / max : 0) + ")";
			bar.setAttribute("aria-hidden", "true"); bar.append(fill);
			const label = node("span", item.name, "ops-rank-name"); label.title = item.name;
			li.append(label, bar, node("span", rankBy === "cpu" ? numeric(value, 3) + " cores" : bytes(value), "ops-rank-value"));
			list.append(li);
		}
		wrap.append(list); return wrap;
	}
	function renderWorkloadChart() {
		const chart = $("#ops-workload-chart"), activity = activityData(), search = $("#ops-workload-search").value.trim().toLowerCase();
		chart.replaceChildren();
		for (const button of page.querySelectorAll("[data-rank]")) button.setAttribute("aria-pressed", String(button.dataset.rank === rankBy));
		const key = rankBy === "cpu" ? "cpu_cores" : "memory_bytes";
		for (const [section, label, haystack] of [["containers", "Containers", (item) => item.name + " " + item.image], ["processes", "Processes", (item) => item.name + " " + item.pid]]) {
			const source = activity?.[section];
			if (source?.status !== "ok") { chart.append(node("p", label + ": " + sourceMessage(source, label === "Containers" ? "Container performance" : "Per-process performance"), "ops-empty")); continue; }
			const matching = (source.rows || []).filter((item) => haystack(item).toLowerCase().includes(search) && Number.isFinite(item[key]));
			if (!matching.length) { chart.append(node("p", label + ": nothing matches this filter.", "ops-empty")); continue; }
			chart.append(rankedList(label, [...matching].sort((a, b) => b[key] - a[key] || a.name.localeCompare(b.name)).slice(0, 10), matching.length));
		}
	}

	function renderProbeChart() {
		const chart = $("#ops-probes-chart"), section = charts?.probes, current = activityData()?.probes?.rows || [];
		chart.replaceChildren();
		if (chartsLoading && !charts) { chart.append(node("p", "Loading retained samples…", "ops-empty")); return; }
		const durations = new Map(current.map((row) => [row.service + "|" + row.target, row.duration_seconds]));
		const historyRows = section?.status === "ok" ? section.hosts?.[selected] || [] : [];
		const list = node("div", undefined, "ops-timeline");
		if (historyRows.length) {
			for (const row of historyRows) {
				const up = row.values.filter((v) => v === 1).length, down = row.values.filter((v) => v === 0).length, cells = row.values.length;
				const svg = svgNode("svg", { viewBox: `0 0 ${cells * 4} 12`, preserveAspectRatio: "none", role: "img", "aria-label": `${row.service} ${row.kind || ""}: ${up} up, ${down} down, ${cells - up - down} without samples over ${section.window}` });
				row.values.forEach((value, index) => svg.append(svgNode("rect", { x: index * 4 + 0.4, y: 1, width: 3.2, height: 10, class: value === 1 ? "ops-cell-up" : value === 0 ? "ops-cell-down" : "ops-cell-gap" })));
				const duration = durations.get(row.service + "|" + row.target);
				list.append(node("span", row.service + (row.kind ? " · " + row.kind : ""), "ops-timeline-name"), svg, node("span", Number.isFinite(duration) ? numeric(duration * 1000, 1) + " ms" : "—", "ops-timeline-value"));
			}
		} else if (current.length && section?.status !== "ok" && !chartsLoading) {
			chart.append(node("p", "Probe history unavailable · current results only.", "metrics-footnote"));
			for (const row of current) list.append(node("span", row.service + (row.kind ? " · " + row.kind : ""), "ops-timeline-name"), badge(row.status === "up" ? "Up now" : row.status === "down" ? "Down now" : "Unknown", row.status), node("span", Number.isFinite(row.duration_seconds) ? numeric(row.duration_seconds * 1000, 1) + " ms" : "—", "ops-timeline-value"));
		}
		if (list.childElementCount) chart.append(list);
		if (historyRows.length) {
			const stepTime = (index) => date(section.start + index * section.step_seconds, section.end - section.start > 21600);
			const runs = (values, wanted) => {
				const found = [];
				for (let index = 0, from = null; index <= values.length; index++) {
					const match = index < values.length && values[index] === wanted;
					if (match && from === null) from = index;
					else if (!match && from !== null) { found.push(from === index - 1 ? stepTime(from) : stepTime(from) + " – " + stepTime(index - 1)); from = null; }
				}
				return found.join("; ") || "none";
			};
			chart.append(dataTable("Probe history", ["Probe", "Up", "Down", "No sample", "Down at", "No sample at"], historyRows.map((row) => [
				row.service + (row.kind ? " · " + row.kind : ""), row.values.filter((v) => v === 1).length, row.values.filter((v) => v === 0).length, row.values.filter((v) => v === null).length, runs(row.values, 0), runs(row.values, null),
			])));
		}
	}

	function renderLogChart() {
		const figure = $("#ops-logs-chart"), section = charts?.logs;
		figure.replaceChildren();
		if (chartsLoading && !charts) { figure.append(node("p", "Loading retained samples…")); return; }
		if (section?.status !== "ok") { figure.append(node("p", "Log history unavailable (Loki unreachable). Other charts are unaffected.", "ops-error")); return; }
		const levels = section.hosts?.[selected]?.levels || {};
		const order = [["Error", "error"], ["Warning", "warning"], ["Information", "info"]];
		const known = new Set(order.map(([name]) => name));
		const stacks = [...order.filter(([name]) => levels[name]), ...Object.keys(levels).filter((name) => !known.has(name) && name !== "unknown").map((name) => [name, "other"]), ...(levels.unknown ? [["unknown", "unknown"]] : [])];
		const n = Math.max(0, ...Object.values(levels).map((values) => values.length));
		const totals = Array.from({ length: n }, (_, i) => stacks.reduce((sum, [name]) => sum + (levels[name][i] || 0), 0));
		if (!n || !totals.some(Boolean)) { figure.append(node("p", "No log lines from " + selected + " in this window.")); return; }
		const W = widthOf(figure), H = 150, x0 = 52, x1 = W - 6, base = H - 20, top = 10, max = Math.max(...totals), bw = (x1 - x0) / n;
		const sums = stacks.map(([name]) => name + " " + levels[name].reduce((a, b) => a + b, 0));
		const svg = svgNode("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${selected} log lines over ${section.window}: ${sums.join(", ")}` });
		const defs = svgNode("defs", {}), hatch = svgNode("pattern", { id: "ops-log-hatch", width: 4, height: 4, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" });
		hatch.append(svgNode("rect", { width: 4, height: 4, class: "ops-hatch-bg" }), svgNode("line", { x1: 0, y1: 0, x2: 0, y2: 4, class: "ops-hatch-line" }));
		defs.append(hatch); svg.append(defs);
		svg.append(svgNode("line", { x1: x0, x2: x1, y1: base, y2: base, class: "ops-chart-grid" }), svgNode("text", { x: x0 - 6, y: top + 4, "text-anchor": "end", class: "ops-chart-label" }, numeric(max)), svgNode("text", { x: x0 - 6, y: base + 4, "text-anchor": "end", class: "ops-chart-label" }, "0"));
		for (let i = 0; i < n; i++) {
			let y = base;
			for (const [name, kind] of stacks) {
				const value = levels[name][i] || 0; if (!value) continue;
				const h = value / max * (base - top); y -= h;
				svg.append(svgNode("rect", { x: x0 + i * bw + 0.5, y, width: Math.max(0.5, bw - 1), height: h, class: "ops-log-" + kind }));
			}
		}
		timeLabels(svg, section.start, section.end, x0, x1, H - 4);
		figure.append(svg);
		if (stacks.length === 1 && stacks[0][0] === "unknown") figure.append(node("p", "These log sources omit a severity label, so every line is counted as “severity not exported”.", "metrics-footnote"));
		figure.append(dataTable("Log lines by severity", ["Time", ...stacks.map(([name]) => name)], Array.from({ length: n }, (_, i) => [date(section.start + i * section.step_seconds, section.end - section.start > 21600), ...stacks.map(([name]) => numeric(levels[name][i] || 0))]).filter((row) => row.slice(1).some((v) => v !== "0"))));
	}
	function renderCharts() { renderRates(); renderProbeChart(); renderLogChart(); }

	function renderSnapshot() { renderOverview(); renderHostCharts(); renderResources(); renderStorageChart(); renderWorkloads(); renderWorkloadChart(); renderActivity(); renderProbeChart(); renderRates(); }

	async function fetchSnapshot(manual = false) {
		if (fetching) return;
		fetching = true; refresh.disabled = true; refresh.textContent = "Refreshing…";
		page.setAttribute("aria-busy", "true");
		if (manual) text("#metrics-feedback", "Collecting current source readings…");
		const controller = new AbortController(), deadline = setTimeout(() => controller.abort(), 12000);
		try {
			const response = await fetch("/api/metrics", { signal: controller.signal, cache: "no-store" });
			if (!response.ok) throw new Error("Snapshot unavailable");
			const data = await response.json(), collected = new Date(data.timestamp);
			if (!data.infrastructure?.hosts || !Array.isArray(data.projects) || !Number.isFinite(collected.getTime())) throw new Error("Invalid snapshot");
			snapshot = data; snapshotFailed = false; renderSnapshot();
			$("#metrics-collected").dateTime = data.timestamp;
			$("#metrics-collected").textContent = collected.toLocaleTimeString();
			$("#metrics-collected").title = collected.toLocaleString();
			const count = Object.values(data.infrastructure.hosts).filter((host) => host.status === "up").length;
			text("#metrics-feedback", count + " / 2 host exporters reporting · inspect source coverage below.");
			$("#metrics-feedback").dataset.state = count ? "up" : "unknown";
		} catch (error) {
			snapshot = null; snapshotFailed = true; renderSnapshot();
			text("#metrics-feedback", error.name === "AbortError" ? "Collection timed out. Current readings cleared; try Refresh now." : "Snapshot unavailable. Current readings cleared; history has its own source status.");
			$("#metrics-feedback").dataset.state = "down";
		} finally {
			clearTimeout(deadline); fetching = false; refresh.disabled = false; refresh.textContent = "Refresh now"; page.setAttribute("aria-busy", "false");
		}
	}
	async function fetchHistory() {
		const generation = ++historyGeneration;
		if (historyRequest) historyRequest.abort();
		const controller = new AbortController(); historyRequest = controller;
		historyLoading = !history || history.window !== windowSelect.value;
		renderHistory(); text("#metrics-history-feedback", "Querying Prometheus…");
		const deadline = setTimeout(() => controller.abort(), 12000);
		try {
			const response = await fetch("/api/metrics/history?window=" + encodeURIComponent(windowSelect.value), { signal: controller.signal, cache: "no-store" });
			if (!response.ok) throw new Error("History unavailable");
			const data = await response.json();
			if (generation !== historyGeneration) return;
			if (!data.hosts || data.window !== windowSelect.value) throw new Error("Invalid history");
			history = data; historyFailed = data.status !== "ok";
			text("#metrics-history-feedback", data.status === "ok" ? "Retained samples · " + data.window + " · refresh 60 s" : "History unavailable");
		} catch (error) {
			if (generation !== historyGeneration) return;
			history = null; historyFailed = true; text("#metrics-history-feedback", "History unavailable · current readings unaffected");
		} finally {
			clearTimeout(deadline);
			if (generation === historyGeneration) { historyLoading = false; historyRequest = null; renderHistory(); renderHostCharts(); }
		}
	}
	async function fetchCharts() {
		const generation = ++chartsGeneration;
		if (chartsRequest) chartsRequest.abort();
		const controller = new AbortController(); chartsRequest = controller;
		chartsLoading = !charts || charts.window !== windowSelect.value;
		if (chartsLoading) { charts = null; renderCharts(); }
		text("#ops-charts-feedback", "Querying Prometheus and Loki…");
		const deadline = setTimeout(() => controller.abort(), 15000);
		try {
			const response = await fetch("/api/metrics/rates?window=" + encodeURIComponent(windowSelect.value), { signal: controller.signal, cache: "no-store" });
			if (!response.ok) throw new Error("Charts unavailable");
			const data = await response.json();
			if (generation !== chartsGeneration) return;
			if (!data.rates || !data.probes || !data.logs || data.window !== windowSelect.value) throw new Error("Invalid chart data");
			charts = data;
			text("#ops-charts-feedback", data.rates.status === "ok" ? "Retained samples · " + data.window + " · refresh 60 s" : "Rate history unavailable");
		} catch (error) {
			if (generation !== chartsGeneration) return;
			charts = { window: windowSelect.value, rates: { status: "unavailable" }, probes: { status: "unavailable" }, logs: { status: "unavailable" } };
			text("#ops-charts-feedback", "Chart history unavailable · current readings unaffected");
		} finally {
			clearTimeout(deadline);
			if (generation === chartsGeneration) { chartsLoading = false; chartsRequest = null; renderCharts(); }
		}
	}
	function fetchWindowed() { fetchHistory(); fetchCharts(); }
	function selectHost(name) {
		if (!["parrot", "flatbush"].includes(name)) return;
		selected = name; hostSelect.value = name; containerLimit = serviceLimit = processLimit = 20;
		$("#ops-workload-search").value = ""; $("#ops-service-filter").value = "all";
		renderSnapshot(); renderHistory(); renderCharts();
	}
	function syncPolling() {
		const live = page.classList.contains("active") && !document.hidden && $("#metrics-live").checked;
		text("#metrics-auto", live ? "Auto-refresh · 15 s" : "Live refresh paused");
		if (live && !snapshotTimer) { fetchSnapshot(); snapshotTimer = setInterval(fetchSnapshot, 15000); fetchWindowed(); historyTimer = setInterval(fetchWindowed, 60000); }
		else if (!live && snapshotTimer) { clearInterval(snapshotTimer); clearInterval(historyTimer); snapshotTimer = historyTimer = null; }
	}
	refresh.addEventListener("click", () => { fetchSnapshot(true); fetchWindowed(); });
	hostSelect.addEventListener("change", () => selectHost(hostSelect.value));
	windowSelect.addEventListener("change", fetchWindowed);
	for (const button of page.querySelectorAll("[data-rank]")) button.addEventListener("click", () => { rankBy = button.dataset.rank; renderWorkloadChart(); });
	$("#metrics-live").addEventListener("change", syncPolling);
	for (const button of page.querySelectorAll("[data-select-host]")) button.addEventListener("click", () => selectHost(button.dataset.selectHost));
	$("#ops-workload-search").addEventListener("input", () => { containerLimit = serviceLimit = processLimit = 20; renderWorkloads(); renderWorkloadChart(); });
	$("#ops-service-filter").addEventListener("change", () => { serviceLimit = 20; renderWorkloads(); });
	$("#ops-containers-more").addEventListener("click", () => { containerLimit += 20; renderWorkloads(); });
	$("#ops-services-more").addEventListener("click", () => { serviceLimit += 20; renderWorkloads(); });
	$("#ops-processes-more").addEventListener("click", () => { processLimit += 20; renderWorkloads(); });
	new MutationObserver(syncPolling).observe(page, { attributes: true, attributeFilter: ["class"] });
	document.addEventListener("visibilitychange", syncPolling);
	const masthead = document.querySelector(".masthead");
	if (masthead) new ResizeObserver(() => {
		page.style.setProperty("--ops-sticky-top", Math.ceil(masthead.getBoundingClientRect().height) + "px");
	}).observe(masthead);
	let chartWidth = 0;
	new ResizeObserver((entries) => {
		const width = Math.round(entries[0].contentRect.width);
		if (width !== chartWidth) { chartWidth = width; renderHistory(); renderCharts(); }
	}).observe($("#metrics-history-chart"));
	// Re-rendering replaces chart nodes; keep a focused Data table summary focused so keyboard users are not dropped to the page top.
	function keepFocus(render) {
		return () => {
			const key = document.activeElement?.matches?.(".ops-chart-data > summary") ? document.activeElement.parentElement.dataset.table : null;
			render();
			if (key) page.querySelector(`.ops-chart-data[data-table="${CSS.escape(key)}"] > summary`)?.focus({ preventScroll: true });
		};
	}
	renderHistory = keepFocus(renderHistory); renderRates = keepFocus(renderRates); renderProbeChart = keepFocus(renderProbeChart); renderLogChart = keepFocus(renderLogChart);
	renderSnapshot(); renderCharts(); syncPolling();
})();
