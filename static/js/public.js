/* ═══════════════════════════════════════════════════════════
   QuizMaster — Public CSS-3D interactions
   Pointer tilt, scroll reveal, and hero parallax.
   Loaded only on public pages. Bails out on reduced-motion.
   ═══════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    var reduceMotion = window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    document.addEventListener('DOMContentLoaded', function () {
        setupReveal();
        if (reduceMotion) return;
        setupTilt();
        setupHeroParallax();
    });

    /* ── Scroll reveal ─────────────────────────────────────── */
    function setupReveal() {
        var selector = '.feature-card, .dept-card, .testimonial-card, ' +
            '.step-card, .quiz-card, .package-card, .pkg-card, ' +
            '.section-header, .cta-banner';
        var items = Array.prototype.slice.call(document.querySelectorAll(selector));
        if (!items.length) return;

        if (reduceMotion || !('IntersectionObserver' in window)) {
            // No animation: just make sure everything is visible.
            return;
        }

        items.forEach(function (el) { el.classList.add('reveal'); });

        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('in-view');
                    io.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

        items.forEach(function (el) { io.observe(el); });
    }

    /* ── Pointer tilt (CSS 3D) ─────────────────────────────── */
    function setupTilt() {
        if (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) {
            return; // skip tilt on touch devices
        }
        var selector = '.feature-card, .dept-card, .testimonial-card, .step-card';
        var cards = Array.prototype.slice.call(document.querySelectorAll(selector));
        var MAX = 7; // max degrees

        cards.forEach(function (card) {
            card.classList.add('tilt-3d');
            // Ensure the parent grid gives perspective.
            var parent = card.parentElement;
            if (parent && !parent.classList.contains('tilt-scene')) {
                parent.classList.add('tilt-scene');
            }

            var raf = null;
            function onMove(e) {
                var rect = card.getBoundingClientRect();
                var px = (e.clientX - rect.left) / rect.width;   // 0..1
                var py = (e.clientY - rect.top) / rect.height;   // 0..1
                var ry = (px - 0.5) * (MAX * 2);
                var rx = (0.5 - py) * (MAX * 2);
                if (raf) cancelAnimationFrame(raf);
                raf = requestAnimationFrame(function () {
                    card.style.transform =
                        'rotateX(' + rx.toFixed(2) + 'deg) rotateY(' + ry.toFixed(2) + 'deg)';
                    card.style.setProperty('--mx', (px * 100).toFixed(1) + '%');
                    card.style.setProperty('--my', (py * 100).toFixed(1) + '%');
                });
            }
            function reset() {
                if (raf) cancelAnimationFrame(raf);
                card.style.transform = '';
            }
            card.addEventListener('mousemove', onMove);
            card.addEventListener('mouseleave', reset);
        });
    }

    /* ── Hero parallax (mouse + scroll) ─────────────────────────
       We transform the whole .hero-3d stage (a single element with no
       CSS animation) so individual float-cards keep their CSS bob +
       base rotation. Mouse and scroll offsets are composited together. */
    function setupHeroParallax() {
        var stage = document.querySelector('.hero-3d');
        if (!stage) return;
        var hero = stage.closest('.hero-section') || stage;

        var mx = 0, my = 0, sy = 0;
        var raf = null;

        function apply() {
            raf = null;
            stage.style.transform =
                'translate3d(' + mx.toFixed(1) + 'px, ' + (my + sy).toFixed(1) + 'px, 0)';
        }
        function schedule() { if (!raf) raf = requestAnimationFrame(apply); }

        hero.addEventListener('mousemove', function (e) {
            var rect = hero.getBoundingClientRect();
            mx = ((e.clientX - rect.left) / rect.width - 0.5) * 22;   // px
            my = ((e.clientY - rect.top) / rect.height - 0.5) * 22;
            schedule();
        });
        hero.addEventListener('mouseleave', function () {
            mx = 0; my = 0; schedule();
        });

        window.addEventListener('scroll', function () {
            sy = (window.scrollY || window.pageYOffset) * 0.12;
            schedule();
        }, { passive: true });
    }
})();
