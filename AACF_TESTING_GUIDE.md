# AACF Compliance Testing Guide

**Status**: ✅ **All 6 POCs ready for local testing**

## Pre-Launch Checklist

All POCs have passed pre-launch validation:

| POC | Port | Backend | Frontend | MistralClient | Status |
|-----|------|---------|----------|---------------|--------|
| corpus-agent | 8001 | ✅ | ✅ built | ✅ | Ready |
| doc-writer | 8002 | ✅ | ✅ built | ✅ | Ready |
| doc-reviewer | 8003 | ✅ | ✅ built | ✅ | Ready |
| catia-toolbox | 8004 | ✅ | ✅ built | ✅ | Ready |
| ocr-vision | 8005 | ✅ | ✅ built | ✅ | Ready |
| s1000d-extractor | 8006 | ✅ | ✅ built | ✅ | Ready |

## How to Test

### Step 1: Launch POCs

Open **6 separate command windows** (one per POC):

```batch
# Terminal 1: corpus-agent
cd apps\corpus-agent
start.bat

# Terminal 2: doc-writer
cd apps\doc-writer
start.bat

# Terminal 3: doc-reviewer
cd apps\doc-reviewer
start.bat

# Terminal 4: catia-toolbox
cd apps\catia-toolbox
start.bat

# Terminal 5: ocr-vision
cd apps\ocr-vision
start.bat

# Terminal 6: s1000d-extractor
cd apps\s1000d-extractor
start.bat
```

**Wait 30-60 seconds for all backends to initialize** (first run rebuilds frontend Vite bundle).

Each terminal will show:
```
[info] Uvicorn running on http://127.0.0.1:<PORT>
```

**Critical**: Do NOT close any terminal until you finish testing — closing one kills the backend.

### Step 2: Verify Portal

Open file explorer and navigate to:
```
deploy/portal/index.html
```

Double-click to open in browser.

You should see:
- ✅ Header "Atexis POCs" with theme toggle + language switcher (FR/EN)
- ✅ 6 POCs listed as clickable cards:
  - Corpus Agent
  - Doc Writer
  - Doc Reviewer
  - Catia Toolbox
  - OCR Vision
  - S1000D Extractor
- ✅ Footer with "Hosted on the Atexis AI platform workspace"

### Step 3: Test Each POC

For each POC card on the portal:

1. **Click the card** → browser navigates to `http://127.0.0.1:<PORT>/`
2. **Verify UI loads** (should see sidebar + main content)
3. **Check theme toggle** (sun/moon button in header)
   - Click → page should switch dark ↔ light (check favicon, sidebar color, text color)
4. **Check language toggle** (FR/EN buttons)
   - Click EN → page text should switch to English
   - Click FR → page text should switch to French
5. **Check navigation** (if applicable)
   - Click menu items in sidebar
   - Page should change without full page reload
6. **Check Settings page** (usually last tab)
   - Should display LLM status badge (OK / Untested / Not Configured / Disabled)
   - If LLM key is configured, badge should show green "OK"
   - Should have option to test LLM connection
7. **Go back to portal** (browser back button or click header logo)

### Step 4: Verify AACF Compliance

While testing, verify these Hard Rules (AACF HR0–HR21):

#### HR0 + HR8 (Configuration)
- [ ] **Settings page accessible** (each POC)
- [ ] **LLM key can be configured at runtime** (not hardcoded in code)
- [ ] **LLM can be toggled ON/OFF** via Settings
- [ ] **Portal configuration externalized** (`deploy/portal/config.json`)

#### HR1 (Auth)
- [ ] **All backends bind to 127.0.0.1 only** (local-only, no internet exposure)
- [ ] **No auth prompts** (verify in `_run.bat` / browser)

#### HR4 + HR7 (Quality + Graceful Degradation)
- [ ] **LLM failures handled gracefully** (if LLM is OFF, app still works without breaking)
- [ ] **No HTTP 5xx on LLM failure** (should degrade or return meaningful error)

#### HR15 (i18n)
- [ ] **FR/EN toggles present in all POCs**
- [ ] **All user-facing text translatable** (no hardcoded English/French)
- [ ] **Portal supports FR/EN** (config.json strings, UI labels)

#### HR20 (Optimistic Mutations)
- [ ] **Settings changes reflect immediately** (theme, language, LLM toggle)
- [ ] **No spinners on simple form submits** (if backend is fast)

#### HR21 (Humanization)
- [ ] **No snake_case / enum keys in UI** (e.g., no `llm_disabled` — use "LLM Disabled")
- [ ] **Theme names are human-readable** ("Light", "Dark" — not "light_mode" / "dark_mode")

#### HR2/HR3 (Quality)
- [ ] **No console.log / print / debug output** in browser console / backend logs (check terminal output)
- [ ] **Error messages are clear** (if an error occurs, message should explain what and next steps)

## Troubleshooting

### "Cannot reach http://127.0.0.1:PORT"
**Cause**: Backend not started or port occupied.

**Fix**:
```bash
# Check if port is in use:
netstat -ano | findstr :<PORT>

# If yes, kill process:
taskkill /PID <PID> /F

# Restart backend:
cd apps/<poc> && start.bat
```

### "CORS error" or "fetch failed"
**Cause**: API route not registered correctly or backend crashed.

**Fix**:
```bash
# Check backend terminal for errors
# Look for:
#   - ImportError (missing module)
#   - SyntaxError (code bug)
#   - Traceback (unhandled exception)

# Restart with fresh import:
cd apps/<poc>/backend
python -c "from app.core.mistral_client import MistralClient; print('OK')"

# If fails, check app/core/mistral_client.py for "class MistralClient:" definition
```

### "Frontend not rendering" or "blank page"
**Cause**: Vite build missing or broken, CSS classes not defined.

**Fix**:
```bash
# Check if frontend/dist/ exists:
ls apps/<poc>/frontend/dist/index.html

# If not, manually rebuild:
cd apps/<poc>/frontend
pnpm build

# Restart backend:
cd ../backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8XXX
```

### "Theme toggle not working" or "Language switch frozen"
**Cause**: i18next config incomplete or theme.css not imported.

**Fix**:
- Verify `frontend/src/index.css` imports `@internal/design-tokens/theme.css` (line 1)
- Verify `frontend/src/i18n/index.ts` defines FR/EN locales
- Clear browser cache: `Ctrl+Shift+Delete` → clear all

### "LLM badge shows 'Disabled' but I want to test LLM"
**Cause**: Mistral key not configured or LLM toggle is OFF.

**Fix**:
1. Go to Settings page (last tab)
2. Look for "LLM Configuration" section
3. Paste your Mistral API key (get from Admin Console)
4. Click "Test LLM Connection"
5. Badge should change to "OK" (green)
6. If stays "Untested" (orange), check backend logs for Mistral API errors

## What You're Verifying

This testing workflow confirms:

1. ✅ **No hardcoded config** (HR0/HR8)
2. ✅ **Auth-free local mode** (HR1)
3. ✅ **Graceful LLM degradation** (HR4/HR7)
4. ✅ **Full i18n coverage** (HR15)
5. ✅ **Optimistic UI updates** (HR20)
6. ✅ **Humanized text** (HR21)
7. ✅ **Code quality** (HR2/HR3 — no console spam, clear errors)
8. ✅ **All 6 POCs can coexist on 127.0.0.1** (ports 8001–8006)

## Files Changed (Latest Commit)

```
commit 8e60bc7
Author: Copilot <223556219+Copilot@users.noreply.github.com>

    fix: restore MistralClient class wrapper + add missing CSS classes
    
    - corpus-agent: add missing 'class MistralClient:' definition
      Fixes: ImportError when importing MistralClient
      Affected: 6 imports (analysis.py, anomalies.py, chat.py, ...)
    
    - catia-toolbox: define missing layout CSS classes in index.css
      Classes: .ct, .layout, .sidebar, .brand, .nav-item, .lang-switch, etc.
      Reason: preview-skin.css removed; Tailwind @layer components now provide styling
```

## Next Steps (After Testing)

If all tests pass:

1. ✅ Update SQL: `UPDATE poc_test_results SET status = 'passed', backend_ok = 1, frontend_ok = 1, ...`
2. ✅ Document any deviations from AACF in each POC's README
3. ✅ Commit test results: `git add . && git commit -m "test: all 6 POCs AACF compliant (manual verification)"`
4. ✅ Archive this guide in `docs/` for future maintainers

If any test fails:

1. ❌ Note which HR rule failed and which POC
2. ❌ Check the "Troubleshooting" section above
3. ❌ If still stuck, create a GitHub issue with:
   - POC name + port
   - Backend log excerpt (from terminal)
   - Browser console error (if visible)
   - Which HR rule is violated

---

**Created**: 2025-01-28  
**Framework**: AACF Hard Rules (HR0–HR21)  
**Status**: All 6 POCs ready for local testing  
**Last Updated**: Latest commit (8e60bc7)
