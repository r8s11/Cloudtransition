/* Personal-agents course — shared read-only sandbox engine.
 *
 * Three widgets, one file. Each lesson includes this script and the markup
 * for its own widget. Nothing here touches a real mailbox, device, or the
 * network. Stages describe the bound path; no model output is faked.
 */

(function () {
  'use strict';

  /* ---------- helpers ---------- */

  function esc(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function $(id) { return document.getElementById(id); }

  function show(el) { if (el) el.hidden = false; }
  function hide(el) { if (el) el.hidden = true; }

  /* ---------- Lesson 3 — Gmail archive search (read-only) ---------- */

  // Seeded snapshot copied from the local Gmail archive (kb.sqlite, source=gmail).
  // No secrets, no tokens, no live mail. Read-only fixture.
  const GMAIL_SEED = [
    {
      title: 'Roosevelt, your application was sent to Raas Infotek',
      from: 'LinkedIn <jobs-noreply@linkedin.com>',
      snippet: 'Your application was sent to Raas Infotek. Supporting systems to building them — security enthusiast, code tinkerer.',
      source: 'LinkedIn application confirmation'
    },
    {
      title: 'Roosevelt, your application was sent to PROCAL TECHNOLOGIES',
      from: 'LinkedIn <jobs-noreply@linkedin.com>',
      snippet: 'Your application was sent to PROCAL TECHNOLOGIES. Supporting systems to building them — security enthusiast, code tinkerer.',
      source: 'LinkedIn application confirmation'
    },
    {
      title: 'Roosevelt, your application was sent to Zodiac Solutions, Inc',
      from: 'LinkedIn <jobs-noreply@linkedin.com>',
      snippet: 'Your application was sent to Zodiac Solutions, Inc. Supporting systems to building them — security enthusiast, code tinkerer.',
      source: 'LinkedIn application confirmation'
    },
    {
      title: 'Good Enough for a Tuesday Night',
      from: 'New Yorker Substack <newyorker@substack.com>',
      snippet: "Each week, our editors select a New Yorker story for you to read: something timely, something important, or something unexpected.",
      source: 'New Yorker Substack newsletter'
    },
    {
      title: 'VA reaches more new Veterans',
      from: 'U.S. Department of Veterans Affairs <veteransaffairs@messages.va.gov>',
      snippet: 'VA.gov gets easier to use, career training, and more. Vet Resources — US Department of Veterans Affairs.',
      source: 'VA.gov bulletin'
    }
  ];

  function renderGmailResults(container, shellEl, query) {
    const q = (query || '').toLowerCase().trim();
    const matches = q ? GMAIL_SEED.filter(function (item) {
      return (item.title + ' ' + item.snippet + ' ' + item.from).toLowerCase().indexOf(q) !== -1;
    }) : GMAIL_SEED.slice();

    if (!q) {
      container.innerHTML = '<p class="sandbox-empty">Type a search to see matching archive snippets.</p>';
      shellEl.textContent = '';
      return;
    }

    if (matches.length === 0) {
      container.innerHTML = '<p class="sandbox-empty">No matching snippets in the seeded archive.</p>';
      shellEl.textContent = '';
      return;
    }

    var html = '<ul class="sandbox-list">';
    for (var i = 0; i < matches.length; i++) {
      var item = matches[i];
      html += '<li class="sandbox-item">';
      html += '<div class="sandbox-item-head">';
      html += '<span class="sandbox-item-title">' + esc(item.title) + '</span>';
      html += '<span class="sandbox-item-source">' + esc(item.source) + '</span>';
      html += '</div>';
      html += '<div class="sandbox-item-from">' + esc(item.from) + '</div>';
      html += '<div class="sandbox-item-snippet">' + esc(item.snippet) + '</div>';
      html += '<div class="sandbox-item-pointer">Source pointer: local archive, read-only — open the original message before treating a result as complete.</div>';
      html += '</li>';
    }
    html += '</ul>';
    container.innerHTML = html;

    // Read-only shell preview — the command that would run; never executed here.
    shellEl.textContent = 'python kb.py search "' + esc(query) + '" --source gmail --limit 3';
  }

  function initGmailSandbox() {
    var input = $('gmail-query');
    var btn = $('gmail-search');
    var container = $('gmail-results');
    var shell = $('gmail-shell');
    if (!input || !btn || !container || !shell) return;

    function run() {
      renderGmailResults(container, shell, input.value);
    }
    btn.addEventListener('click', run);
    input.addEventListener('input', run);
    run();
  }

  /* ---------- Lesson 4 — Smart home allow-list + approval dialog ---------- */

  const SH_ENTITY = 'light.study_light';
  var shState = 'off';
  var shPending = null;

  function initSmartHomeSandbox() {
    var onBtn = $('sh-on');
    var offBtn = $('sh-off');
    var stateEl = $('sh-state');
    var dialog = $('sh-dialog');
    var denyBtn = $('sh-deny');
    var acceptBtn = $('sh-accept');
    var log = $('sh-log');
    var dialogMsg = $('sh-dialog-msg');
    if (!onBtn || !offBtn || !stateEl || !dialog || !denyBtn || !acceptBtn || !log || !dialogMsg) return;

    function setState(next) {
      shState = next;
      stateEl.textContent = shState;
      stateEl.className = 'sandbox-state sandbox-state-' + shState;
      onBtn.disabled = shState === 'on';
      offBtn.disabled = shState === 'off';
    }

    function appendLog(kind, text) {
      var div = document.createElement('div');
      div.className = 'sandbox-log-entry sandbox-log-' + kind;
      div.textContent = text;
      log.insertBefore(div, log.firstChild);
    }

    function openDialog(action) {
      shPending = action;
      dialogMsg.textContent = 'Approve ' + action + ' for ' + SH_ENTITY + '?';
      dialog.hidden = false;
      onBtn.disabled = true;
      offBtn.disabled = true;
    }

    function closeDialog() {
      dialog.hidden = true;
      shPending = null;
      onBtn.disabled = shState === 'on';
      offBtn.disabled = shState === 'off';
    }

    function apply(action) {
      var accepted = action === 'on' ? 'on' : 'off';
      setState(accepted);
      appendLog('accepted', 'Home Assistant accepted ' + accepted + ' for ' + SH_ENTITY + ' (200). Accepted call ≠ proof the physical light changed.');
      closeDialog();
    }

    function deny() {
      appendLog('denied', 'Denied ' + shPending + ' for ' + SH_ENTITY + '. No request sent.');
      closeDialog();
    }

    onBtn.addEventListener('click', function () { openDialog('on'); });
    offBtn.addEventListener('click', function () { openDialog('off'); });
    acceptBtn.addEventListener('click', function () { if (shPending) apply(shPending); });
    denyBtn.addEventListener('click', deny);

    // Close dialog on Escape.
    dialog.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { deny(); }
    });

    setState('off');
  }

  /* ---------- Lesson 5 — NYC 311 typed read-only query ---------- */

  const NYC_BOROUGHS = ['BRONX', 'BROOKLYN', 'MANHATTAN', 'QUEENS', 'STATEN ISLAND'];

  function initNYCSandbox() {
    var chips = document.querySelectorAll('[data-borough]');
    var limitInput = $('nyc-limit');
    var limitVal = $('nyc-limit-val');
    var sqlEl = $('nyc-sql');
    var results = $('nyc-results');
    if (!chips.length || !limitInput || !limitVal || !sqlEl || !results) return;

    var selected = 'BRONX';
    var limit = 5;

    function refresh() {
      // Update chip states.
      for (var i = 0; i < chips.length; i++) {
        var chip = chips[i];
        var active = chip.dataset.borough === selected;
        chip.setAttribute('aria-checked', String(active));
        chip.className = active ? 'borough-chip borough-chip-active' : 'borough-chip';
      }
      limitVal.textContent = limit;

      // Read-only SQL preview — whitelisted fields, Literal borough, hard limit.
      // borough comes from a fixed Literal, so user text can never become
      // arbitrary query syntax.
      var sql = [
        'GET https://data.cityofnewyork.us/resource/erm2-nwe9.json',
        '  $select: created_date, complaint_type, status, agency, borough',
        "  $where: borough = '" + selected + "'",
        '  $order: created_date DESC',
        '  $limit: ' + limit
      ].join('\n');
      sqlEl.textContent = sql;

      // Mock results (read-only preview, no network call).
      var rows = [];
      for (var i = 1; i <= limit; i++) {
        rows.push({
          created_date: '2026-11-' + String(10 + i).padStart(2, '0') + 'T08:00:00',
          complaint_type: i % 2 === 0 ? 'Noise - Residential' : 'Illegal Parking',
          status: i % 3 === 0 ? 'Closed' : 'Open',
          agency: 'NYPD',
          borough: selected
        });
      }
      var html = '<table><thead><tr><th>Created</th><th>Complaint type</th><th>Status</th><th>Agency</th><th>Borough</th></tr></thead><tbody>';
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        html += '<tr>';
        html += '<td>' + esc(r.created_date) + '</td>';
        html += '<td>' + esc(r.complaint_type) + '</td>';
        html += '<td>' + esc(r.status) + '</td>';
        html += '<td>' + esc(r.agency) + '</td>';
        html += '<td>' + esc(r.borough) + '</td>';
        html += '</tr>';
      }
      html += '</tbody></table>';
      results.innerHTML = html;
    }

    for (var i = 0; i < chips.length; i++) {
      chips[i].addEventListener('click', function () {
        selected = this.dataset.borough;
        refresh();
      });
    }
    limitInput.addEventListener('input', function () {
      limit = Math.max(1, Math.min(10, parseInt(this.value, 10) || 1));
      this.value = limit;
      refresh();
    });

    refresh();
  }

  /* ---------- boot ---------- */

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    initGmailSandbox();
    initSmartHomeSandbox();
    initNYCSandbox();
  });

})();
