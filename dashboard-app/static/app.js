document.addEventListener('DOMContentLoaded', function() {
  var tabs = Array.from(document.querySelectorAll('.section-nav [role="tab"]'));
  var panels = document.querySelectorAll('[role="tabpanel"]');

  function activateTab(tab, updateHash) {
    // Deactivate all tabs
    tabs.forEach(function(t) {
      t.classList.remove('active');
      t.setAttribute('aria-selected', 'false');
      t.setAttribute('tabindex', '-1');
    });

    // Activate selected tab
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    tab.setAttribute('tabindex', '0');

    // Show correct panel
    panels.forEach(function(p) { p.classList.remove('active'); });
    var target = document.getElementById('page-' + tab.dataset.page);
    if (target) {
      target.classList.add('active');
      animateBars(target);
    }

    // Update URL hash
    if (updateHash !== false) {
      history.replaceState(null, '', '#' + tab.dataset.page);
    }
  }

  // Click handler
  tabs.forEach(function(tab) {
    tab.addEventListener('click', function() {
      activateTab(tab);
      tab.focus();
    });
  });

  // Keyboard arrow navigation (WAI-ARIA Tabs pattern)
  tabs.forEach(function(tab) {
    tab.addEventListener('keydown', function(e) {
      var idx = tabs.indexOf(tab);
      var next;

      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        next = tabs[(idx + 1) % tabs.length];
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        next = tabs[(idx - 1 + tabs.length) % tabs.length];
      } else if (e.key === 'Home') {
        e.preventDefault();
        next = tabs[0];
      } else if (e.key === 'End') {
        e.preventDefault();
        next = tabs[tabs.length - 1];
      }

      if (next) {
        activateTab(next);
        next.focus();
      }
    });
  });

  // Restore tab from URL hash on load
  var hash = window.location.hash.replace('#', '');
  if (hash) {
    var matchingTab = tabs.find(function(t) { return t.dataset.page === hash; });
    if (matchingTab) {
      activateTab(matchingTab, false);
    }
  }

  // Handle browser back/forward
  window.addEventListener('hashchange', function() {
    var h = window.location.hash.replace('#', '');
    var t = tabs.find(function(tab) { return tab.dataset.page === h; });
    if (t) activateTab(t, false);
  });

  // Animate progress bars on load
  animateBars(document.querySelector('.page.active') || document);
});

function animateBars(scope) {
  requestAnimationFrame(function() {
    requestAnimationFrame(function() {
      scope.querySelectorAll('.progress-fill[data-width]').forEach(function(el) {
        el.style.width = el.dataset.width;
      });
    });
  });
}

// ── Realm filter pills ────────────────────────────────────────
(function() {
  var pills = document.querySelectorAll('.realm-pill');
  var sections = document.querySelectorAll('.realm-section');

  pills.forEach(function(pill) {
    pill.addEventListener('click', function() {
      pills.forEach(function(p) { p.classList.remove('active'); });
      pill.classList.add('active');

      var realm = pill.dataset.realm;
      sections.forEach(function(sec) {
        if (realm === 'all' || sec.dataset.realmSection === realm) {
          sec.style.display = '';
        } else {
          sec.style.display = 'none';
        }
      });
    });
  });
})();

// ── Interactive task checkboxes ───────────────────────────────
(function() {
  document.querySelectorAll('.task-check[data-realm]').forEach(function(box) {
    function handleToggle() {
      var isDone = box.dataset.done === 'true';
      var newDone = !isDone;

      // Optimistic UI update
      box.dataset.done = String(newDone);
      box.setAttribute('aria-checked', String(newDone));
      box.innerHTML = newDone ? '&#x2713;' : '';
      box.classList.toggle('done', newDone);

      var textEl = box.nextElementSibling;
      if (textEl) textEl.classList.toggle('done', newDone);

      var row = box.closest('.task-item');
      if (row) row.classList.toggle('task-done-row', newDone);

      // API call to persist
      fetch('/api/tasks/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({
          realm: box.dataset.realm,
          line: parseInt(box.dataset.line, 10),
          done: newDone
        })
      }).then(function(res) {
        if (!res.ok) revert();
      }).catch(revert);

      function revert() {
        box.dataset.done = String(isDone);
        box.setAttribute('aria-checked', String(isDone));
        box.textContent = isDone ? '\u2713' : '';
        box.classList.toggle('done', isDone);
        if (textEl) textEl.classList.toggle('done', isDone);
        if (row) row.classList.toggle('task-done-row', isDone);
      }
    }

    box.addEventListener('click', handleToggle);
    box.addEventListener('keydown', function(e) {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        handleToggle();
      }
    });
  });
})();
