(() => {
    const LINK_ACTIVE_CLASS = "nav-link-active";

    function highlightNavigation() {
        const currentPath = window.location.pathname;
        document.querySelectorAll("nav a.nav-link").forEach((link) => {
            const href = link.getAttribute("href");
            if (!href) {
                return;
            }
            if (href === currentPath || (href !== "/" && currentPath.startsWith(href))) {
                link.classList.add(LINK_ACTIVE_CLASS);
            } else {
                link.classList.remove(LINK_ACTIVE_CLASS);
            }
        });
    }

    function dispatchSpaEvent(detail) {
        const event = new CustomEvent("spa:navigate", { detail });
        window.dispatchEvent(event);
    }

    document.addEventListener("DOMContentLoaded", () => {
        highlightNavigation();
    });

    window.addEventListener("popstate", () => {
        highlightNavigation();
        dispatchSpaEvent({ path: window.location.pathname });
    });
})();

