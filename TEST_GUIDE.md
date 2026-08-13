# 🧪 GUIDE DE TEST — 6 POCs AACF 100% Conforme

**Objectif** : Valider que chaque POC démarre correctement et respecte les règles AACF (HR0–HR21).

---

## 📋 CHECKLIST RAPIDE

Avant de lancer les tests :
- [ ] Git repo à jour (`git status` = clean)
- [ ] Node.js + npm/pnpm disponibles
- [ ] Python 3.9+ + venv
- [ ] Ports 8001–8006 libres (`netstat | findstr LISTENING`)
- [ ] Fichier `.env` présent dans chaque `apps/<poc>/backend/`

---

## 🚀 LANCER UN POC

### **Windows** (Recommandé)
```batch
cd apps\<poc>\
start.bat
```

Une fenêtre cmd s'ouvre et affiche :
```
[13:37:02] ocr-vision (port 8005) is starting...
[13:37:05] Backend: http://127.0.0.1:8005/api/v1/health
[13:37:10] Frontend: Vite dev server running
[13:37:15] ✅ http://127.0.0.1:8005
```

### **Unix/Mac**
```bash
cd apps/<poc>/
bash start.sh
```

**Ne pas fermer la fenêtre !** (Les services continuent de tourner)

---

## 🔍 TESTS PAR POC

### ✅ **Test 1: corpus-agent** (http://127.0.0.1:8001)

```
Port        : 8001
Backend API : http://127.0.0.1:8001/api/v1/health
Frontend    : http://127.0.0.1:8001
DB          : apps/corpus-agent/backend/data/corpus-agent.db
Tier        : Tier 1 (local, 127.0.0.1 only)
LLM Mode    : LLM-first (needs Mistral API key)
```

**Checklist:**
- [ ] Page charge (http://127.0.0.1:8001)
- [ ] Sidebar visible avec onglets (Home, Architecture, Données, Paramètres)
- [ ] Thème dark/light toggle (sun/moon icon)
- [ ] Switch langue FR/EN fonctionne
- [ ] Badge LLM affiche un état (`ok`, `untested`, `not_configured`, `disabled`)
- [ ] Onglet Paramètres accessible, `llm_enabled` toggle visible
- [ ] Onglet Données affiche stats + bouton reset
- [ ] Pas d'erreur console (F12 → Console)

**Fix si erreur :**
```bash
cd apps/corpus-agent/backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head
```

---

### ✅ **Test 2: doc-writer** (http://127.0.0.1:8002)

```
Port        : 8002
Backend API : http://127.0.0.1:8002/api/v1/health
Frontend    : http://127.0.0.1:8002
DB          : apps/doc-writer/backend/data/doc-writer.db
Tier        : Tier 1/2 (configurable via TIER_MODE)
LLM Mode    : LLM-assisted (fallback: dummy template)
```

**Checklist:**
- [ ] Page charge
- [ ] Theme + i18n toggles fonctionnent
- [ ] Onglet Paramètres : voir option `TIER_MODE` (tier1|tier2)
- [ ] LLM badge affiche un état
- [ ] Editor UI responsive (form, buttons, etc.)
- [ ] Pas d'erreur console

---

### ✅ **Test 3: doc-reviewer** (http://127.0.0.1:8003)

```
Port        : 8003
Backend API : http://127.0.0.1:8003/api/v1/health
Frontend    : http://127.0.0.1:8003
DB          : apps/doc-reviewer/backend/data/doc-reviewer.db
Tier        : Tier 1 (local)
LLM Mode    : LLM-first with regex fallback (HR4/HR7 compliant)
```

**Checklist:**
- [ ] Page charge
- [ ] Theme + i18n toggles
- [ ] LLM badge status
- [ ] Upload zone visible (ou drag-drop)
- [ ] Onglet Données affiche stats
- [ ] Pas d'erreur console

---

### ✅ **Test 4: catia-toolbox** (http://127.0.0.1:8004)

```
Port        : 8004
Backend API : http://127.0.0.1:8004/api/v1/health
Frontend    : http://127.0.0.1:8004
DB          : apps/catia-toolbox/backend/data/catia-toolbox.db
Tier        : Tier 1 (local)
LLM Mode    : LLM-assisted (task planning)
```

**Checklist:**
- [ ] Page charge
- [ ] Tailwind + @internal/ui components visibles
- [ ] Theme + i18n toggles
- [ ] LLM badge
- [ ] Form / input areas responsive
- [ ] Pas d'erreur console

---

### ✅ **Test 5: ocr-vision** (http://127.0.0.1:8005)

```
Port        : 8005
Backend API : http://127.0.0.1:8005/api/v1/health
Frontend    : http://127.0.0.1:8005
DB          : apps/ocr-vision/backend/data/ocr-vision.db
Tier        : Tier 1 (local)
LLM Mode    : Computer vision (API-heavy)
```

**Checklist:**
- [ ] Page charge
- [ ] Theme + i18n toggles
- [ ] LLM badge status
- [ ] Upload / camera input visible
- [ ] Image preview responsive
- [ ] Pas d'erreur console

---

### ✅ **Test 6: s1000d-extractor** (http://127.0.0.1:8006)

```
Port        : 8006
Backend API : http://127.0.0.1:8006/api/v1/health
Frontend    : http://127.0.0.1:8006
DB          : apps/s1000d-extractor/backend/data/s1000d-extractor.db
Tier        : Tier 1 (local)
LLM Mode    : LLM-first (XML schema generation)
```

**Checklist:**
- [ ] Page charge
- [ ] Theme + i18n toggles
- [ ] LLM badge status
- [ ] Input source (XML, PDF, etc.) visible
- [ ] Output preview / download area
- [ ] Pas d'erreur console

---

## 🔧 POINTS DE VÉRIFICATION COMMUNS (Tous les POCs)

### 1. **AACF HR0/HR8 — Config externalisée**
```bash
curl http://127.0.0.1:80XX/api/v1/health
```
Résultat attendu :
```json
{
  "status": "ok",
  "llm": "not_configured|untested|ok|disabled",
  "timestamp": "2026-08-13T15:37:00Z"
}
```

### 2. **AACF HR21 — Design system appliqué**
```
F12 → Elements → <html>
```
Vérifier :
- [ ] Classe `.dark` présente (si thème dark activé)
- [ ] Pas de `background: #xxx` inline
- [ ] Fonts : `Inter`, `JetBrains Mono`, `Orbitron` présentes
- [ ] Coleurs via CSS variables (ex. `var(--color-primary)`)

### 3. **AACF HR1 — localStorage usage OK**
```
F12 → Application → localStorage
```
Vérifier :
- [ ] `theme` (string: "dark"|"light") ✅ OK
- [ ] `language` (string: "fr"|"en") ✅ OK
- [ ] **Aucun** `auth_token`, `user_id`, `password` ❌ FAIL si présent

### 4. **AACF HR15 — i18n complète**
```
1. Cliquer FR → tout doit passer en français
2. Cliquer EN → tout doit passer en anglais
3. Rechargement F5 → langue persistée (via localStorage)
```

### 5. **AACF HR20 — Optimistic mutations**
```
Onglet Données → Cliquer "Reset All"
1er clic : bouton devient rouge "Confirmer?"
2e clic (< 3s) : action exécutée
3e clic (> 3s) : retour à l'état initial
```

---

## ⚠️ ERREURS COURANTES & SOLUTIONS

### ❌ Port déjà utilisé
```
error: port 8001 is already in use
```
**Fix:**
```bash
netstat -ano | findstr :8001
taskkill /PID <PID> /F
```

### ❌ `venv` ou dépendances manquantes
```
ModuleNotFoundError: No module named 'fastapi'
```
**Fix:**
```bash
cd apps/<poc>/backend
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Unix
pip install -r requirements.txt
```

### ❌ Alembic migrations cassées
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError)
```
**Fix:**
```bash
cd apps/<poc>/backend
python -m alembic upgrade head
```

### ❌ Node.js ou pnpm manquants
```
pnpm: command not found
```
**Fix:**
```bash
# Installer Node.js LTS puis :
npm install -g pnpm
# Ou utiliser npm si pnpm indisponible
cd apps/<poc>/frontend
npm install
npm run build
```

### ❌ Frontend dist/ manquant
```
GET /index.html → 503 frontend not built
```
**Fix:**
```bash
cd apps/<poc>/frontend
pnpm install
pnpm build
```

---

## 📊 TRACKING DES TESTS

Après chaque test, mets à jour le fichier **`poc_test_results`** SQL :

```sql
UPDATE poc_test_results
SET status = 'passed',
    backend_ok = 1,
    frontend_ok = 1,
    theme_toggle = 1,
    i18n_toggle = 1,
    settings_page = 1,
    health_check = 1,
    admin_panel = 1,
    notes = 'All checks passed'
WHERE poc_name = 'corpus-agent';
```

---

## 🎯 CRITÈRE DE SUCCÈS

✅ **PASS** si :
- [ ] Tous les 6 POCs démarrent sans erreur
- [ ] Frontend + Backend communiquent (`/api/v1/health` → 200 OK)
- [ ] Theme toggle (dark/light) fonctionne
- [ ] i18n toggle (FR/EN) fonctionne
- [ ] Onglets (Home, Architecture, Données, Paramètres) visibles
- [ ] LLM badge affiche un état
- [ ] Pas de console error (F12)
- [ ] localStorage contient uniquement `theme` + `language`
- [ ] Design system appliqué (Tailwind, couleurs, fonts)

---

## 📞 NEXT STEPS

1. **Lancer chaque POC** via `start.bat`
2. **Accéder** http://127.0.0.1:80XX
3. **Valider** tous les points de vérification ci-dessus
4. **Documenter** les résultats (session SQL ou notes)
5. **Escalade** si une app échoue (report le détail de l'erreur)

---

**Ready to test? Let's go! 🚀**

