# ATEXIS AI Framework — Vibe Coding Instructions

Drop this file into your project (e.g. save it as `AGENTS.md`, or paste it into your
assistant's rules/system prompt). It tells your AI coding agent what the ATEXIS AI Framework
(AACF) is, how to pull approved content on demand via the `aacf_fetch` MCP tool, and the
non‑negotiable rules every ATEXIS project must follow.

> **You are coding at ATEXIS.** Build on the AACF's approved templates, rules, styles and
> governance instead of starting from scratch. When in doubt, fetch the relevant AACF document
> and follow it.

---

## 1. Fetch AACF content with the `aacf_fetch` MCP tool

The ATEXIS AI platform serves the AACF read‑only through an MCP tool called **`aacf_fetch`**,
hosted on the platform's MCP server. Use it to read any framework document at the moment you
need it — do not guess the content, fetch it.

- **Endpoint:** `http://10.117.139.1:8200/mcp`  (transport: **streamable‑http**)
- **Auth:** `Authorization: Bearer <YOUR_KEY>`  *(or the header `X-Api-Key: <YOUR_KEY>`)*
- **Key:** get one from **Admin Console → API Keys** (shown once). Corporate network / VPN only.

**Tool:** `aacf_fetch`

| Parameter | Type | Description |
|---|---|---|
| `path` | string (required) | Path within the AACF, e.g. `rules/python.mdc`, `templates/web-app.md`. Use `""` with `list_dir:true` to list the root |
| `list_dir` | boolean (default false) | List a directory's entries instead of reading a file |
| `include_version` | boolean (default false) | Prefix the response with the AACF version |

**Examples**

```jsonc
// Discover what's available
aacf_fetch({ "path": "", "list_dir": true, "include_version": true })

// Read the hard rules before writing any code
aacf_fetch({ "path": "rules/atexis-hard-rules.md" })

// Pull the approved starter for the kind of project you're building
aacf_fetch({ "path": "templates/web-app.md" })

// Language + safety rules
aacf_fetch({ "path": "rules/python.mdc" })
aacf_fetch({ "path": "rules/ai-output-safety.mdc" })

// The unified design system (so every ATEXIS UI looks consistent)
aacf_fetch({ "path": "styles/design-system.md" })
```

### Connecting your agent to the MCP server

**VS Code (`.vscode/mcp.json`):**

```json
{
  "servers": {
    "atexis-aacf": {
      "type": "http",
      "url": "http://10.117.139.1:8200/mcp",
      "headers": { "Authorization": "Bearer ${input:atexisKey}" }
    }
  },
  "inputs": [
    { "id": "atexisKey", "type": "promptString", "description": "ATEXIS API key", "password": true }
  ]
}
```

**Claude Code (CLI):**

```bash
claude mcp add atexis-aacf --transport http http://10.117.139.1:8200/mcp \
  -H "Authorization: Bearer sk-...YOUR_KEY..."
```

**Continue (`~/.continue/config.json`):**

```jsonc
{
  "experimental": {
    "modelContextProtocolServers": [
      { "transport": { "type": "streamable-http",
        "url": "http://10.117.139.1:8200/mcp",
        "requestOptions": { "headers": { "Authorization": "Bearer sk-...YOUR_KEY..." } } } }
    ]
  }
}
```

**Smoke test (curl):**

```bash
API=sk-...YOUR_KEY...
curl -s http://10.117.139.1:8200/mcp \
  -H "Authorization: Bearer $API" \
  -H "Accept: application/json, text/event-stream" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"aacf_fetch","arguments":{"path":"rules/atexis-hard-rules.md"}}}'
```

All traffic stays on the internal ATEXIS network — no external calls, no telemetry.

> The same MCP endpoint also exposes the platform RAG tools (`rag_search`, `rag_query`, …) for
> retrieval over approved corpora. Other MCP servers (research, transcription, …) live behind the
> gateway at `https://172.21.28.81/mcp/<name>/mcp` — see the platform Connection Guide.

### Version freshness — verify before you rely (once per session)

Content you fetch live via `aacf_fetch` is always the deployed framework version. But if you are
working from a **local copy** of any AACF file (files committed into a repo, an older snapshot):

1. `aacf_fetch({"path": "VERSION"})` and compare with the local `aacf/VERSION`.
2. **Different?** Your copy is outdated — re-fetch ALL framework files via `aacf_fetch` (walk from
   `{"path": "", "list_dir": true}`). Never mix files from different framework versions.
3. **Can't reach the MCP?** Tell the user: *you cannot reach the AACF MCP and may be working with
   an outdated version of the framework* — then continue with the local copy.

---

## 2. The map — what to fetch, and when

| You are… | Fetch |
|---|---|
| Starting a new project | `templates/` → pick the closest starter (`web-app`, `api-service`, `data-pipeline`, `internal-tool`, `automation-script`) |
| Writing code | `rules/atexis-hard-rules.md`, then the language rule (`rules/python.mdc`, `rules/javascript.mdc`, `rules/dotnet.mdc`) |
| Generating code with AI | `rules/ai-output-safety.mdc` (OWASP LLM Top 10, supply‑chain / slopsquatting, prompt‑injection) |
| Building any UI | `styles/design-system.md`, `styles/branding.md` |
| Getting it review‑ or audit‑ready | `governance/security-governance-compliance.md`, `governance/guardrails.md`, `governance/tier-checklists.md` |
| Writing prompts / agents | `prompts/prompt-library.md` |

Browse the full framework in the app at **`/propose/framework`** (My proposals → Framework).

---

## 3. The Hard Rules (HR0–HR21) — always in force

Fetch `rules/atexis-hard-rules.md` for the authoritative text. Summary:

- **HR0** Every config value is surfaced in an admin UI. **HR8** Nothing hardcoded — everything configurable.
- **HR1** No `localStorage` / `sessionStorage` for auth or state. Auth is HTTP‑only cookies; Postgres is the source of truth.
- **HR2** Fix every issue you detect and test the fix. **HR3** Verify against the real codebase, cite references.
- **HR4** If a task can't be done properly, report the blocker — don't silently simplify.
- **HR6** Never truncate quality‑bearing or user‑facing content — summarize with an LLM instead of slicing.
- **HR7** No fallbacks that quietly degrade UX, quality or data integrity — escalate instead.
- **HR9** Never delete persistent/user data without explicit confirmation.
- **HR10** Deep‑merge nested config; never shallow‑merge. **HR13** No legacy code — remove or refactor.
- **HR11** Don't use regex for critical/semantic operations — use an LLM call.
- **HR15** All UI text is localizable. **HR21** Never render raw machine tokens (snake_case, enum keys) — humanize before display.
- **HR18/19** No hard timeouts or iteration caps on agentic work — use a watchdog + escalation.
- **HR20** All mutation UI is optimistic — reflect the change immediately, persist in the background, roll back only on server rejection.

---

## 4. The golden path

1. **Fetch** the closest `templates/` starter and build on it.
2. **Fetch** the hard rules + your language rule; follow them as you write.
3. If you're AI‑generating code, **fetch** `rules/ai-output-safety.mdc` and honour it (verify every dependency exists, never invent packages, never echo untrusted input into shell/SQL/HTML).
4. For UI, **fetch** the design system and use the approved tokens and components.
5. Before you call it done, **fetch** the governance guardrails + tier checklist for your project's tier and self‑check against them.

Build on approved components. Fetch, don't guess. Follow the hard rules.
