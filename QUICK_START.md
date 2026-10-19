# 🚀 LANCER LES APPS — GUIDE RAPIDE

Chaque POC est **100% AACF conforme** et prêt à être testé en local.

---

## 📌 Résumé des ports

| POC | Port | Lancer |
|---|---|---|
| **Corpus Agent** | 8001 | `apps/corpus-agent/start.bat` |
| **Doc Writer** | 8002 | `apps/doc-writer/start.bat` |
| **Doc Reviewer** | 8003 | `apps/doc-reviewer/start.bat` |
| **Catia Toolbox** | 8004 | `apps/catia-toolbox/start.bat` |
| **OCR Vision** | 8005 | `apps/ocr-vision/start.bat` |
| **S1000D Extractor** | 8006 | `apps/s1000d-extractor/start.bat` |

---

## 🎬 LANCER UNE APP (Windows)

### Étape 1 : Ouvrir PowerShell/CMD

```powershell
cd ATEXIS_POCS
```

### Étape 2 : Lancer l'app

```powershell
apps\corpus-agent\start.bat
```

**Résultat attendu :**
- Une fenêtre cmd s'ouvre et affiche :
```
[setup] Installation des deps Python - 1 a 3 min...
[setup] Migrations Alembic...
[run] Backend sur http://127.0.0.1:8001/
      Ctrl+C ici pour arreter.
```
- Le navigateur ouvre automatiquement http://127.0.0.1:8001

### Étape 3 : Tester dans le navigateur

Une fois la page ouverte :
- ✅ Theme toggle (sun/moon) dans le sidebar
- ✅ Langue FR/EN dans le sidebar
- ✅ Navigation propre à l'application ; l'onglet Données peut être absent
- ✅ Pas de console error (F12)

### Étape 4 : Arrêter l'app

Dans la fenêtre cmd : `Ctrl+C`

---

## 🧪 CHECKLIST DE TEST RAPIDE

Après avoir lancé **au moins une app**, valide ces points :

### Backend OK ?
```bash
curl http://127.0.0.1:8001/api/v1/health
# Résultat attendu:
# {"status":"ok","llm":"not_configured|untested|ok|disabled",...}
```

### Frontend OK ?
- Ouvre http://127.0.0.1:8001
- Page charge sans erreur
- Onglets visibles
- Pas de console error (F12)

### Thème & i18n OK ?
- Clic sun/moon → thème bascule dark/light
- Clic FR/EN → UI en FR ou EN
- Rechargement F5 → langue/thème persisté (localStorage)

---

## ⚠️ ERREURS COURANTES & SOLUTIONS

### ❌ Port déjà utilisé
```
error: port 8001 is already in use
```
**Solution :**
```powershell
netstat -ano | findstr :8001
taskkill /PID <PID> /F
```
Ou relancer l'app (elle bascule auto au port suivant si 8001 occupé).

### ❌ Python pas trouvé
```
ModuleNotFoundError: No module named 'fastapi'
```
**Solution :**
```powershell
cd apps\<poc>\backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### ❌ Alembic migrations fail
```
sqlalchemy.exc.OperationalError
```
**Solution :**
```powershell
cd apps\<poc>\backend
python -m alembic upgrade head
```

### ❌ Frontend dist manquant
```
GET /index.html → 503 frontend not built
```
**Solution :**
```powershell
cd apps\<poc>\frontend
pnpm install
pnpm build
```

---

## 📞 PROCHAINES ÉTAPES

1. **Lancer les 6 POCs** un par un via leurs `start.bat`
2. **Valider** que chaque POC démarre et s'affiche
3. **Tester** theme toggle + i18n FR/EN sur chaque
4. **Documenter** les résultats dans [TEST_GUIDE.md](./TEST_GUIDE.md)
5. **Signaler** les bugs sur [#issues](issues/)

---

**Status:** ✅ All POCs 100% AACF compliant, ready for testing  
**Ready to launch? Let's go! 🚀**
