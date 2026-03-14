document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.querySelector('.nav-toggle');
    const nav = document.getElementById('site-nav');
    const navBreakpoint = 960;

    if (!toggle || !nav) {
        return;
    }

    const setExpanded = (expanded) => {
        toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        document.body.classList.toggle('nav-open', expanded);
    };

    toggle.addEventListener('click', () => {
        const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
        setExpanded(!isExpanded);
    });

    nav.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', () => setExpanded(false));
    });

    window.addEventListener('resize', () => {
        if (window.innerWidth > navBreakpoint) {
            setExpanded(false);
        }
    });
});
