/*
 * Portal MFA login gate (SSO option A) — vanilla, matching the portal's own
 * plain HTML/CSS/JS style (like KleamPy's auth.js), NOT React.
 *
 * Loaded BEFORE the launcher renders. Checks the portal backend's shared
 * session; if not authenticated, shows a full-screen login overlay that runs
 * the corporate MFA flow against /atexispocs/api/auth/* and, on success,
 * reloads so the launcher (and the shared `atexispocs_session` cookie the
 * apps trust) is in place. All API paths are RELATIVE to this page, so the
 * subpath prefix (/app/is-team-dev-1-jjm/atexispocs/) is handled by the
 * browser resolving against document.baseURI — no hardcoded host/IP.
 */
(function () {
  "use strict";

  var COPY = {
    fr: {
      title: "Bienvenue",
      sub: "Connecte-toi pour acceder aux applications AI4TECHDOC",
      info:
        "AI4TECHDOC necessite un compte Microsoft 365 professionnel. " +
        "Connecte-toi avec ton email et ton mot de passe professionnels, " +
        "puis confirme avec la methode de verification de ton compte — " +
        "l'application Authenticator, un SMS ou un appel telephonique. " +
        "Si tu ne peux pas te connecter, contacte le support informatique.",
      email: "Email professionnel",
      password: "Mot de passe",
      signIn: "Se connecter",
      signingIn: "Connexion…",
      startFailed: "Impossible de demarrer la connexion. Verifie ton email et reessaie.",
      domainError: "L'adresse doit etre une adresse professionnelle @atexis.com.",
      waiting: "Contact de ton organisation…",
      verifying: "Verification…",
      mfaNumber: "Ouvre Microsoft Authenticator et appuie sur ce nombre :",
      code: "Saisis le code de verification.",
      verify: "Verifier",
      call: "Microsoft appelle ton telephone. Reponds et appuie sur #.",
      choose: "Choisis une methode de verification :",
      codeRejected: "Code refuse.",
      cancel: "Annuler",
      cancelled: "Connexion annulee.",
      timedOut: "La demande a expire.",
      denied: "Acces refuse.",
      notReachable: "Service d'identite injoignable. La connexion se termine cote serveur…",
      generic: "Une erreur est survenue. Reessaie.",
      logout: "Se deconnecter",
    },
    en: {
      title: "Welcome",
      sub: "Sign in to access the AI4TECHDOC applications",
      info:
        "AI4TECHDOC requires a corporate Microsoft 365 account. Sign in " +
        "with your work email and password, then confirm with whichever " +
        "verification method your account uses — the Authenticator app, a " +
        "text message or a phone call. If you can't sign in, contact IT " +
        "Support.",
      email: "Corporate email",
      password: "Password",
      signIn: "Sign in",
      signingIn: "Signing in…",
      startFailed: "Could not start sign-in. Check your email and try again.",
      domainError: "The address must be a corporate @atexis.com address.",
      waiting: "Contacting your organization…",
      verifying: "Verifying…",
      mfaNumber: "Open Microsoft Authenticator and tap this number:",
      code: "Enter the verification code.",
      verify: "Verify",
      call: "Microsoft is calling your phone. Answer and press #.",
      choose: "Choose a verification method:",
      codeRejected: "Code rejected.",
      cancel: "Cancel",
      cancelled: "Sign-in cancelled.",
      timedOut: "The request timed out.",
      denied: "Access denied.",
      notReachable: "Identity service unreachable. Sign-in finishes server-side…",
      generic: "Something went wrong. Please try again.",
      logout: "Log out",
    },
  };

  function lang() {
    try {
      var v = localStorage.getItem("atexis-portal-lang");
      if (v === "fr" || v === "en") return v;
    } catch (e) {}
    return (navigator.language || "fr").slice(0, 2).toLowerCase() === "en" ? "en" : "fr";
  }
  function t(k) {
    return (COPY[lang()] || COPY.fr)[k];
  }

  var POLL_MAX = 200;
  var POLL_MS = 3000;
  var ws = null;
  var authId = null;
  var pollTimer = null;
  var pollAttempts = 0;
  var gotComplete = false;

  function $(id) {
    return document.getElementById(id);
  }
  function show(el) {
    if (el) el.classList.remove("hidden");
  }
  function hide(el) {
    if (el) el.classList.add("hidden");
  }
  function setText(id, s) {
    var el = $(id);
    if (el) el.textContent = s || "";
  }

  function showOverlay() {
    show($("login-overlay"));
  }
  function hideOverlay() {
    hide($("login-overlay"));
  }

  function apiUrl(path) {
    return new URL(path, document.baseURI).href;
  }
  function wsUrl(id, email, password) {
    var u = new URL("api/auth/ws/" + encodeURIComponent(id), document.baseURI);
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
    u.search =
      "?email=" + encodeURIComponent(email) + "&password=" + encodeURIComponent(password);
    return u.href;
  }

  function resetMfaSub() {
    hide($("login-mfa-number"));
    hide($("login-mfa-code-group"));
    hide($("login-mfa-choose"));
    hide($("login-mfa-error"));
  }
  function setMfaError(s) {
    var el = $("login-mfa-error");
    if (!el) return;
    if (s) {
      el.textContent = s;
      show(el);
    } else {
      hide(el);
    }
  }

  // --- session bootstrap ---------------------------------------------------

  function checkSession() {
    fetch(apiUrl("api/auth/session"), { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data && data.authenticated) {
          applyAuthedChrome(data);
          hideOverlay();
        } else {
          showLoginForm();
        }
      })
      .catch(function () {
        // Fail-open sur erreur reseau : ne pas verrouiller le lanceur si le
        // backend a un hoquet transitoire (chaque app gate de toute facon).
        hideOverlay();
      });
  }

  function applyAuthedChrome(data) {
    var badge = $("portal-user-badge");
    if (badge) {
      var name = data.display_name || data.email || "";
      badge.querySelector("#portal-user-name").textContent = name;
      show(badge);
    }
  }

  function showLoginForm() {
    setText("login-title", t("title"));
    setText("login-sub", t("sub"));
    setText("login-info", t("info"));
    show($("login-info"));
    setText("login-email-label", t("email"));
    setText("login-password-label", t("password"));
    $("login-submit").textContent = t("signIn");
    hide($("login-mfa"));
    show($("login-form"));
    showOverlay();
  }

  // --- sign-in flow --------------------------------------------------------

  // Meme regle que le backend (_EMAIL_RE dans backend/app/api/auth.py) et
  // qu'elecgraph (ATEXIS_EMAIL_RE) : domaine @atexis.com uniquement. Verifie
  // cote client d'abord pour un retour immediat, mais le backend reste la
  // seule source de verite (fail-closed) — cf. la meme regex la-bas.
  var ATEXIS_EMAIL_RE = /^[^@\s]+@atexis\.com$/i;

  function startSignIn(email, password) {
    hide($("login-email-error"));
    setMfaError("");
    pollAttempts = 0;
    gotComplete = false;

    if (!ATEXIS_EMAIL_RE.test(email)) {
      var errEl = $("login-email-error");
      errEl.textContent = t("domainError");
      show(errEl);
      return;
    }

    $("login-submit").disabled = true;
    $("login-submit").textContent = t("signingIn");

    fetch(apiUrl("api/auth/start"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ email: email }),
    })
      .then(function (r) {
        return r.json().then(function (b) {
          return { ok: r.ok, body: b };
        });
      })
      .then(function (res) {
        $("login-submit").disabled = false;
        $("login-submit").textContent = t("signIn");
        if (!res.ok || !res.body.auth_id) {
          var el = $("login-email-error");
          el.textContent = res.body.detail || t("startFailed");
          show(el);
          return;
        }
        authId = res.body.auth_id;
        hide($("login-form"));
        show($("login-mfa"));
        resetMfaSub();
        setText("login-mfa-status", t("waiting"));
        openWs(email, password);
      })
      .catch(function () {
        $("login-submit").disabled = false;
        $("login-submit").textContent = t("signIn");
        var el = $("login-email-error");
        el.textContent = t("startFailed");
        show(el);
      });
  }

  function openWs(email, password) {
    try {
      ws = new WebSocket(wsUrl(authId, email, password));
    } catch (e) {
      beginPoll();
      return;
    }
    ws.onmessage = function (ev) {
      var msg;
      try {
        msg = JSON.parse(ev.data);
      } catch (e) {
        return;
      }
      handleMessage(msg);
    };
    ws.onclose = function () {
      ws = null;
      if (!gotComplete) beginPoll();
    };
  }

  function sendWs(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }

  function handleMessage(msg) {
    switch (msg.type) {
      case "status":
        setText("login-mfa-status", msg.message || t("waiting"));
        break;
      case "mfa_required":
        resetMfaSub();
        setText("login-mfa-status", t("mfaNumber"));
        setText("login-mfa-number", msg.mfa_number || "");
        show($("login-mfa-number"));
        show($("login-cancel"));
        break;
      case "awaiting_code":
        resetMfaSub();
        setText("login-mfa-status", msg.message || t("code"));
        show($("login-mfa-code-group"));
        $("login-mfa-code").value = "";
        $("login-mfa-code").focus();
        break;
      case "awaiting_call":
        resetMfaSub();
        setText("login-mfa-status", msg.description || t("call"));
        break;
      case "choose_method":
        resetMfaSub();
        setText("login-mfa-status", t("choose"));
        renderChoose(msg.options || []);
        show($("login-mfa-choose"));
        break;
      case "code_rejected":
        setMfaError(msg.message || t("codeRejected"));
        $("login-mfa-code").value = "";
        break;
      case "auth_complete":
        gotComplete = true;
        setText("login-mfa-status", t("verifying"));
        resetMfaSub();
        finalize();
        break;
      case "auth_error":
        setMfaError(msg.message || t("generic"));
        break;
      default:
        break;
    }
  }

  function renderChoose(options) {
    var box = $("login-mfa-choose");
    box.innerHTML = "";
    options.forEach(function (opt, index) {
      var label = typeof opt === "string" ? opt : opt.label || String(opt);
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "login-choose-option";
      btn.textContent = label;
      btn.addEventListener("click", function () {
        sendWs({ type: "method_choice", index: index, label: label });
      });
      box.appendChild(btn);
    });
  }

  function finalize() {
    if (!authId) return;
    fetch(apiUrl("api/auth/poll/" + encodeURIComponent(authId)), { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(handlePoll)
      .catch(function () {
        setMfaError(t("generic"));
      });
  }

  function beginPoll() {
    if (pollTimer) return;
    setText("login-mfa-status", t("notReachable"));
    pollTimer = setInterval(function () {
      pollAttempts += 1;
      if (pollAttempts > POLL_MAX) {
        clearInterval(pollTimer);
        pollTimer = null;
        setMfaError(t("timedOut"));
        return;
      }
      if (!authId) return;
      fetch(apiUrl("api/auth/poll/" + encodeURIComponent(authId)), { credentials: "same-origin" })
        .then(function (r) {
          return r.json();
        })
        .then(function (res) {
          if (res.status !== "pending") {
            clearInterval(pollTimer);
            pollTimer = null;
            handlePoll(res);
          }
        })
        .catch(function () {});
    }, POLL_MS);
  }

  function handlePoll(res) {
    switch (res.status) {
      case "pending":
        beginPoll();
        break;
      case "complete":
        hideOverlay();
        window.location.reload();
        break;
      case "denied":
        setMfaError(res.message || t("denied"));
        show($("login-cancel"));
        break;
      case "expired":
      case "failed":
        setMfaError(res.message || t("generic"));
        break;
      default:
        setMfaError(t("generic"));
    }
  }

  function cancelSignIn() {
    sendWs({ type: "cancel" });
    if (ws) {
      try {
        ws.close();
      } catch (e) {}
      ws = null;
    }
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    authId = null;
    setMfaError("");
    setText("login-mfa-status", t("cancelled"));
    setTimeout(showLoginForm, 600);
  }

  function logout() {
    fetch(apiUrl("api/auth/logout"), { method: "POST", credentials: "same-origin" })
      .then(function () {
        window.location.reload();
      })
      .catch(function () {
        window.location.reload();
      });
  }

  // --- wiring --------------------------------------------------------------

  window.PortalAuth = { logout: logout };

  document.addEventListener("DOMContentLoaded", function () {
    checkSession();

    var form = $("login-form");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var email = $("login-email").value.trim();
        var password = $("login-password").value;
        if (!email || !password) return;
        startSignIn(email, password);
      });
    }
    var codeBtn = $("login-mfa-submit");
    if (codeBtn) {
      codeBtn.textContent = t("verify");
      codeBtn.addEventListener("click", function () {
        var code = $("login-mfa-code").value.trim();
        if (code) sendWs({ type: "mfa_code", code: code });
      });
    }
    var codeInput = $("login-mfa-code");
    if (codeInput) {
      codeInput.addEventListener("keypress", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          $("login-mfa-submit").click();
        }
      });
    }
    var cancelBtn = $("login-cancel");
    if (cancelBtn) {
      cancelBtn.textContent = t("cancel");
      cancelBtn.addEventListener("click", cancelSignIn);
    }
    var logoutBtn = $("portal-logout");
    if (logoutBtn) {
      logoutBtn.textContent = t("logout");
      logoutBtn.addEventListener("click", logout);
    }
  });
})();
