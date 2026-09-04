// Local sign-in / sign-up screen. SSO is a future extension (disabled here).
import { useState } from "react";
import { useSession } from "../sessionStore";
import { BRANDING } from "../../branding";

export function Login() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const login = useSession((s) => s.login);
  const register = useSession((s) => s.register);
  const error = useSession((s) => s.error);
  const noUsers = useSession((s) => s.users.length === 0);

  const effectiveMode = noUsers ? "register" : mode;

  async function submit() {
    setBusy(true);
    if (effectiveMode === "register") await register(name, email, password);
    else await login(email, password);
    setBusy(false);
  }

  return (
    <div className="login-bg">
      <div className="login-card">
        <div className="logo-row"><h1>{BRANDING.name}</h1></div>
        <p className="sub">{BRANDING.tagline} — {effectiveMode === "register" ? "create your account" : "sign in"}</p>

        {effectiveMode === "register" && (
          <div className="field"><label>Full name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Maria Ruiz" /></div>
        )}
        <div className="field"><label>Email</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@atexis.com" /></div>
        <div className="field"><label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()} /></div>

        {error && <div className="login-error">{error}</div>}

        <button className="btn-login" disabled={busy} onClick={submit}>
          {busy ? "…" : effectiveMode === "register" ? "Create account" : "Sign in"}
        </button>

        {!noUsers && (
          <div className="login-switch">
            {effectiveMode === "login" ? (
              <>No account? <a onClick={() => setMode("register")}>Create one</a></>
            ) : (
              <>Have an account? <a onClick={() => setMode("login")}>Sign in</a></>
            )}
          </div>
        )}
        <div className="sso">or <a title="Not available yet">Sign in with company SSO</a> <small>(future)</small></div>
        <div className="foot">Local account · {BRANDING.name}</div>
      </div>
    </div>
  );
}
