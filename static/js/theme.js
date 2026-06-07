/* ═══════════════════════════════════════════════════════════
   QuizMaster — Light / Dark theme toggle
   The no-flash inline script in each <head> sets the initial theme
   before paint. This file wires up the toggle buttons + icon swap.
   Loaded on every page (public + dashboards).
   ═══════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    function current() {
        return document.documentElement.getAttribute('data-theme') || 'dark';
    }

    function updateIcons(theme) {
        // Show a sun while in dark mode (click → light), moon while light.
        var icons = document.querySelectorAll('[data-theme-toggle] i');
        Array.prototype.forEach.call(icons, function (ic) {
            ic.className = theme === 'light' ? 'bi bi-moon-stars-fill' : 'bi bi-sun-fill';
        });
        var labels = document.querySelectorAll('[data-theme-toggle] .theme-label');
        Array.prototype.forEach.call(labels, function (el) {
            el.textContent = theme === 'light' ? 'Dark mode' : 'Light mode';
        });
    }

    function apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.documentElement.setAttribute('data-bs-theme', theme);
        try { localStorage.setItem('theme', theme); } catch (e) {}
        updateIcons(theme);
    }

    document.addEventListener('DOMContentLoaded', function () {
        updateIcons(current());
        var toggles = document.querySelectorAll('[data-theme-toggle]');
        Array.prototype.forEach.call(toggles, function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                apply(current() === 'light' ? 'dark' : 'light');
            });
        });
    });
})();
