(function () {
  "use strict";

  const LANGUAGE_KEY = "atexis-portal-lang";
  const THEME_KEY = "theme";
  const labels = {
    fr: {
      portal: "Portail",
      roadmap: "Roadmap IA",
      ecosystem: "Écosystème IA",
      navigation: "Navigation stratégique",
      language: "Langue",
      theme: "Basculer le thème clair / sombre"
    },
    en: {
      portal: "Portal",
      roadmap: "AI Roadmap",
      ecosystem: "AI Ecosystem",
      navigation: "Strategic navigation",
      language: "Language",
      theme: "Toggle light / dark theme"
    }
  };

  function readPreference(key) {
    try {
      return localStorage.getItem(key);
    } catch (_error) {
      return null;
    }
  }

  function writePreference(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (_error) {
      // Preferences remain usable for the current page when storage is unavailable.
    }
  }

  function initialLanguage() {
    const stored = readPreference(LANGUAGE_KEY);
    if (stored === "fr" || stored === "en") return stored;
    return (navigator.language || "fr").slice(0, 2).toLowerCase() === "en" ? "en" : "fr";
  }

  function mountHeader(options) {
    const root = document.getElementById("portal-header");
    if (!root) throw new Error("Missing #portal-header mount point");

    root.innerHTML = `
      <header class="portal-topbar">
        <div class="portal-heading">
          <h1 class="portal-title" id="page-title"></h1>
          <p class="portal-subtitle" id="page-subtitle"></p>
        </div>
        <div class="portal-actions">
          <nav class="portal-nav" id="portal-nav">
            <button class="portal-nav-button" type="button" data-page="portal" data-target="index.html" id="portal-btn"></button>
            <button class="portal-nav-button" type="button" data-page="roadmap" data-target="roadmap.html" id="roadmap-btn"></button>
            <button class="portal-nav-button" type="button" data-page="ecosystem" data-target="ia-ecosystem.html" id="ecosystem-btn"></button>
          </nav>
          <div class="portal-tools">
            <button type="button" class="portal-theme-toggle" id="theme-toggle">
              <svg class="sun" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="4"></circle>
                <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"></path>
              </svg>
              <svg class="moon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
              </svg>
            </button>
            <div class="portal-lang-switch" id="language-switch" role="group">
              <button class="portal-lang-button" type="button" data-lang="fr">FR</button>
              <button class="portal-lang-button" type="button" data-lang="en">EN</button>
            </div>
          </div>
        </div>
      </header>`;

    document.getElementById("page-title").textContent = options.title;
    document.getElementById("page-subtitle").textContent = options.subtitle;
    document.querySelectorAll(".portal-nav-button").forEach(function (button) {
      button.classList.toggle("active", button.dataset.page === options.activePage);
      if (button.dataset.page === options.activePage) button.setAttribute("aria-current", "page");
      button.addEventListener("click", function () {
        location.href = button.dataset.target;
      });
    });
  }

  function applyChromeLanguage(lang) {
    const current = labels[lang] || labels.fr;
    document.documentElement.lang = lang;
    document.getElementById("portal-btn").textContent = current.portal;
    document.getElementById("roadmap-btn").textContent = current.roadmap;
    document.getElementById("ecosystem-btn").textContent = current.ecosystem;
    document.getElementById("portal-nav").setAttribute("aria-label", current.navigation);
    document.getElementById("language-switch").setAttribute("aria-label", current.language);
    document.getElementById("theme-toggle").setAttribute("aria-label", current.theme);
    document.querySelectorAll(".portal-lang-button").forEach(function (button) {
      button.classList.toggle("active", button.dataset.lang === lang);
    });
    writePreference(LANGUAGE_KEY, lang);
  }

  function initialize(onLanguageChange) {
    const applyLanguage = function (lang) {
      applyChromeLanguage(lang);
      onLanguageChange(lang);
    };

    document.querySelectorAll(".portal-lang-button").forEach(function (button) {
      button.addEventListener("click", function () {
        applyLanguage(button.dataset.lang);
      });
    });

    document.getElementById("theme-toggle").addEventListener("click", function () {
      const isLight = document.documentElement.classList.toggle("light");
      writePreference(THEME_KEY, isLight ? "light" : "dark");
    });

    applyLanguage(initialLanguage());
  }

  window.PortalUI = {
    initialize: initialize,
    mountHeader: mountHeader
  };
})();