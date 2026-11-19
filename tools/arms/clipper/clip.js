/* Pure helpers for the ARMS clipper. No browser APIs, so they can be exercised
   under Node/Bun as well as inside the popup. */
(function (root) {
	"use strict";

	const MAX_SELECTION = 100000;
	const MAX_TITLE = 300;

	/** Collapse whitespace/control characters so a value is safe on one line. */
	function oneLine(value, max) {
		return String(value == null ? "" : value)
			.replace(/[\u0000-\u001f\u007f\u2028\u2029]+/g, " ")
			.replace(/\s+/g, " ")
			.trim()
			.slice(0, max);
	}

	/** Only http(s) pages are clippable. Credentials are dropped, the fragment is dropped. */
	function cleanUrl(raw) {
		let u;
		try {
			u = new URL(String(raw));
		} catch (_e) {
			return null;
		}
		if (u.protocol !== "http:" && u.protocol !== "https:") return null;
		u.username = "";
		u.password = "";
		u.hash = "";
		return u.href;
	}

	function pad(n) {
		return String(n).padStart(2, "0");
	}

	function stamp(date) {
		return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
	}

	/** Safe download name: fixed folder, ASCII slug only, never a path from the page. */
	function safeFilename(title, date) {
		const slug = String(title == null ? "" : title)
			.normalize("NFKD")
			.replace(/[\u0300-\u036f]/g, "")
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, "-")
			.replace(/^-+|-+$/g, "")
			.slice(0, 40)
			.replace(/-+$/g, "");
		return `arms-clips/${stamp(date)}-${slug || "clip"}.md`;
	}

	/** Returns {ok:true, markdown, filename} or {ok:false, error}. */
	function buildClip(input, now) {
		const date = now || new Date();
		const url = cleanUrl(input && input.url);
		if (!url) return { ok: false, error: "Only http(s) pages can be clipped." };
		let text = String((input && input.text) || "")
			.replace(/\r\n?/g, "\n")
			.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "")
			.trim();
		if (!text) return { ok: false, error: "No text is selected on the page. Select some text, then capture." };
		let truncated = false;
		if (text.length > MAX_SELECTION) {
			text = text.slice(0, MAX_SELECTION);
			truncated = true;
		}
		const title = oneLine(input.title, MAX_TITLE) || url;
		const quote = text
			.split("\n")
			.map((line) => (line.length ? `> ${line}` : ">"))
			.join("\n");
		const markdown =
			[
				"---",
				`title: ${JSON.stringify(title)}`,
				`source: ${JSON.stringify(url)}`,
				`captured: ${JSON.stringify(date.toISOString())}`,
				"type: web-clip",
				truncated ? "truncated: true" : null,
				"---",
				"",
				`# ${title.replace(/^#+\s*/, "")}`,
				"",
				`Source: <${url}>`,
				"",
				quote,
				truncated ? `\n_Selection truncated at ${MAX_SELECTION} characters._` : null,
			]
				.filter((line) => line !== null)
				.join("\n") + "\n";
		return { ok: true, markdown, filename: safeFilename(title, date), title, url };
	}

	const api = { buildClip, safeFilename, cleanUrl, oneLine, MAX_SELECTION };
	if (typeof module !== "undefined" && module.exports) module.exports = api;
	else root.ArmsClip = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
