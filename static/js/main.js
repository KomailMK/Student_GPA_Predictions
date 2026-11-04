document.addEventListener('DOMContentLoaded', function () {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ---------- Scroll animations (AOS) ---------- */
    // Sideways slides start ~100px off-screen, which causes horizontal overflow on phones.
    if (window.matchMedia('(max-width: 960px)').matches) {
        document.querySelectorAll('[data-aos^="fade-left"], [data-aos^="fade-right"]').forEach((el) => {
            el.setAttribute('data-aos', 'fade-up');
        });
    }
    if (window.AOS) {
        AOS.init({
            duration: 800,
            easing: 'ease-out-cubic',
            once: true,
            offset: 60,
            disable: reduceMotion
        });
    }

    /* ---------- Navbar: shrink on scroll ---------- */
    const navbar = document.getElementById('navbar');
    const onScroll = () => navbar && navbar.classList.toggle('scrolled', window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });

    /* ---------- Mobile drawer ---------- */
    const menuToggle = document.getElementById('menu-toggle');
    const drawer = document.getElementById('mobile-drawer');
    const setDrawer = (open) => {
        document.body.classList.toggle('drawer-open', open);
        menuToggle.setAttribute('aria-expanded', String(open));
        menuToggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
        drawer.setAttribute('aria-hidden', String(!open));
    };
    if (menuToggle && drawer) {
        menuToggle.addEventListener('click', () => setDrawer(!document.body.classList.contains('drawer-open')));
        drawer.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => setDrawer(false)));
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setDrawer(false); });
        window.addEventListener('resize', () => { if (window.innerWidth > 960) setDrawer(false); });
    }

    /* ---------- Toasts (success / info) ---------- */
    document.querySelectorAll('.toast').forEach((toast, i) => {
        const dismiss = () => {
            toast.classList.add('is-leaving');
            toast.addEventListener('animationend', () => toast.remove(), { once: true });
        };
        toast.style.animationDelay = `${i * 120}ms`;
        toast.querySelector('.toast-close').addEventListener('click', dismiss);
        setTimeout(dismiss, 4500 + i * 120);
    });

    /* ---------- Cursor spotlight on cards ---------- */
    document.querySelectorAll('.spotlight').forEach((el) => {
        el.addEventListener('pointermove', (e) => {
            const r = el.getBoundingClientRect();
            el.style.setProperty('--mx', `${e.clientX - r.left}px`);
            el.style.setProperty('--my', `${e.clientY - r.top}px`);
        });
    });

    /* ---------- Password visibility ---------- */
    document.querySelectorAll('.password-toggle').forEach((btn) => {
        btn.addEventListener('click', function () {
            const input = this.parentElement.querySelector('input');
            const icon = this.querySelector('i');
            const show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            icon.classList.toggle('fa-eye', !show);
            icon.classList.toggle('fa-eye-slash', show);
            this.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
        });
    });

    /* ---------- Password strength (informational only) ---------- */
    document.querySelectorAll('input[data-strength]').forEach((input) => {
        const meter = input.closest('.field').querySelector('.strength');
        const label = meter.querySelector('.strength-label');
        const hints = ['Use 8+ characters with a mix of letters, numbers & symbols', 'Weak', 'Okay', 'Good', 'Strong'];
        input.addEventListener('input', () => {
            const v = input.value;
            let score = 0;
            if (v.length >= 8) score++;
            if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
            if (/\d/.test(v)) score++;
            if (/[^A-Za-z0-9]/.test(v)) score++;
            if (v && score === 0) score = 1;
            meter.dataset.score = v ? score : 0;
            label.textContent = hints[v ? score : 0];
        });
    });

    /* ---------- OTP boxes -> hidden "code" field ---------- */
    document.querySelectorAll('.otp-group').forEach((group) => {
        const boxes = [...group.querySelectorAll('.otp-box')];
        const hidden = document.getElementById(group.dataset.otpTarget);
        const sync = () => {
            hidden.value = boxes.map((b) => b.value).join('');
            boxes.forEach((b) => b.classList.toggle('filled', !!b.value));
        };
        const fillFrom = (start, digits) => {
            digits.split('').forEach((d, k) => { if (boxes[start + k]) boxes[start + k].value = d; });
            sync();
            boxes[Math.min(start + digits.length, boxes.length - 1)].focus();
        };

        boxes.forEach((box, i) => {
            box.addEventListener('input', () => {
                const digits = box.value.replace(/\D/g, '');
                box.value = '';
                if (digits) fillFrom(i, digits.slice(0, boxes.length - i));
                else sync();
            });
            box.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !box.value && i > 0) {
                    boxes[i - 1].value = '';
                    boxes[i - 1].focus();
                    sync();
                    e.preventDefault();
                } else if (e.key === 'ArrowLeft' && i > 0) boxes[i - 1].focus();
                else if (e.key === 'ArrowRight' && i < boxes.length - 1) boxes[i + 1].focus();
            });
            box.addEventListener('paste', (e) => {
                e.preventDefault();
                const digits = (e.clipboardData.getData('text') || '').replace(/\D/g, '');
                if (digits) fillFrom(i, digits.slice(0, boxes.length - i));
            });
            box.addEventListener('focus', () => box.select());
        });
    });

    /* ---------- Inline client-side validation ---------- */
    const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const validateField = (input) => {
        const field = input.closest('.field');
        const errorEl = field.querySelector('.field-error');
        const label = (field.querySelector('label')?.textContent || 'this field').trim().toLowerCase();
        const v = input.value.trim();
        let msg = '';

        if (input.hasAttribute('data-otp')) {
            if (!/^\d{6}$/.test(v)) msg = 'Please enter all 6 digits of your code.';
        } else if (input.required && !v) {
            msg = `Please enter your ${label}.`;
        } else if (input.type === 'email' && !emailRe.test(v)) {
            msg = 'That email doesn\u2019t look quite right — try name@example.com.';
        }

        field.classList.toggle('has-error', !!msg);
        errorEl.textContent = msg;
        return !msg;
    };

    document.querySelectorAll('form.js-validate').forEach((form) => {
        const inputs = [...form.querySelectorAll('input[required]')];

        inputs.forEach((input) => {
            const field = input.closest('.field');
            const watch = input.type === 'hidden' ? field.querySelectorAll('.otp-box') : [input];
            watch.forEach((el) => {
                el.addEventListener('input', () => { if (field.classList.contains('has-error')) validateField(input); });
                if (input.type !== 'hidden') el.addEventListener('blur', () => { if (input.value) validateField(input); });
            });
        });

        form.addEventListener('submit', (e) => {
            const results = inputs.map(validateField);
            if (results.includes(false)) {
                e.preventDefault();
                const firstBad = form.querySelector('.field.has-error');
                firstBad.classList.remove('shake');
                void firstBad.offsetWidth;
                firstBad.classList.add('shake');
                (firstBad.querySelector('.otp-box:not(.filled)') || firstBad.querySelector('input:not([type=hidden])'))?.focus();
                return;
            }
            const btn = form.querySelector('button[type="submit"]');
            btn.classList.add('is-loading');
            btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> <span>Please wait…</span>';
        });
    });

    /* ---------- GPA rings: fill + count-up, then reveal text ---------- */
    const animateRing = (valueEl) => {
        const target = parseFloat(valueEl.dataset.ringValue);
        const wrap = valueEl.closest('.ring-wrap');
        const progress = wrap.querySelector('.ring-progress');
        const card = wrap.parentElement;
        const duration = reduceMotion ? 0 : 1600;
        const start = performance.now();
        const ease = (t) => 1 - Math.pow(1 - t, 3);

        requestAnimationFrame(() => {
            progress.style.transitionDuration = `${duration}ms, 300ms`;
            progress.style.opacity = '1';
            progress.style.strokeDashoffset = 100 - (target / 4) * 100;
        });

        const tick = (now) => {
            const t = duration ? Math.min((now - start) / duration, 1) : 1;
            valueEl.textContent = (target * ease(t)).toFixed(2);
            if (t < 1) return requestAnimationFrame(tick);
            wrap.classList.add('is-done');
            card.querySelectorAll('.standing').forEach((s) => s.classList.add('is-visible'));
            card.querySelectorAll('.reveal-text').forEach(revealWords);
        };
        requestAnimationFrame(tick);
    };

    const revealWords = (el) => {
        if (!el.dataset.split) {
            const text = el.textContent.trim();
            el.setAttribute('aria-label', text);
            el.textContent = '';
            text.split(/\s+/).forEach((w, i) => {
                const span = document.createElement('span');
                span.className = 'reveal-word';
                span.setAttribute('aria-hidden', 'true');
                span.style.setProperty('--i', i);
                span.textContent = w;
                el.append(span, ' ');
            });
            el.dataset.split = '1';
        }
        requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('is-revealed')));
    };

    const rings = document.querySelectorAll('[data-ring-value]');
    if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                io.unobserve(entry.target);
                setTimeout(() => animateRing(entry.target), reduceMotion ? 0 : 450);
            });
        }, { threshold: 0.4 });
        rings.forEach((r) => io.observe(r));
    } else {
        rings.forEach(animateRing);
    }
});