/* ARMS Clipper popup. Runs only while the popup is open; there is no background
   worker, no content script, no host permission. The page is read once, when
   "Capture selection" is pressed, through activeTab + scripting. */
"use strict";

(() => {
	const $ = (id) => document.getElementById(id);
	let tab = null;
	let clip = null;

	function say(text, kind) {
		const el = $("msg");
		el.textContent = text;
		el.className = kind || "";
	}

	async function init() {
		try {
			[tab] = await chrome.tabs.query({ active: true, currentWindow: true });
		} catch (_e) {
			tab = null;
		}
		const url = tab && ArmsClip.cleanUrl(tab.url);
		$("page-title").textContent = (tab && tab.title) || "(no active tab)";
		$("page-url").textContent = url || (tab && tab.url ? "Not an http(s) page — cannot be clipped." : "");
		$("capture").disabled = !tab || !url;
		if (!url) say("Open a normal web page, select some text, then reopen this popup.", "error");
	}

	/** Runs inside the page: returns plain strings only. */
	function readSelection() {
		return { text: String(window.getSelection() || ""), title: document.title, url: location.href };
	}

	async function capture() {
		clip = null;
		$("download").disabled = true;
		$("preview").value = "";
		say("");
		let result;
		try {
			const [injection] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: readSelection });
			result = injection && injection.result;
		} catch (_e) {
			say("This page cannot be read (browser-protected page or permission withheld).", "error");
			return;
		}
		const built = ArmsClip.buildClip(result || {}, new Date());
		if (!built.ok) {
			say(built.error, "error");
			return;
		}
		clip = built;
		$("preview").value = built.markdown;
		$("download").disabled = false;
		say(`Ready: ${built.markdown.length.toLocaleString()} characters. Review, then download.`, "ok");
	}

	async function download() {
		if (!clip) return;
		try {
			const url = "data:text/markdown;charset=utf-8," + encodeURIComponent(clip.markdown);
			await chrome.downloads.download({ url, filename: clip.filename, saveAs: true, conflictAction: "uniquify" });
			say("Download started. Choose where to save it.", "ok");
		} catch (e) {
			say(`Download failed: ${e && e.message ? e.message : "unknown error"}`, "error");
		}
	}

	$("capture").addEventListener("click", capture);
	$("download").addEventListener("click", download);
	init();
})();
