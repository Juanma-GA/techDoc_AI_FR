# Fixtures FTM (synthétiques)

Classeurs de test **100 % inventés** (aucune donnée réelle), consolidés par
famille de règle du moteur v4 (`app/checks/`). Tu peux les ouvrir dans Excel ou
les téléverser dans l'app pour voir l'agent travailler.

| Fichier | Rôle |
|---|---|
| `fiche_conforme.xlsx` | Fiche qui **passe** tous les checks déterministes → aucune anomalie attendue (baseline). |
| `fiche_non_conforme.xlsx` | Fiche qui déclenche **au moins une anomalie par famille** déterministe (script, texte, ordre_taches, tache_induite, securite, preliminaire, complementaire, serrage, valeur_numerique, illustration, rechange, outillage, entete). |
| `referentiel_demo.xlsx` | Suivi ATM (24 lignes) + BASL. L'en-tête de l'onglet ATM est en **ligne 3** (pas la plus large) → sert à tester la sélection manuelle de la ligne d'en-tête dans le mapping. |

> Format `.xlsx` (pas `.xlsm`) : openpyxl ne génère pas de `.xlsm` ouvrable par
> Excel (pas de `vbaProject.bin`). Les parsers FTM lisent `.xlsx` et `.xlsm` à
> l'identique — le format ne change rien aux checks.

## Régénérer

```bash
python tests/fixtures/build_fixtures.py
```

Le contenu (et l'oracle `EXPECTED_TYPES`) vit dans
[`build_fixtures.py`](build_fixtures.py). Les fiches sont verrouillées par
[`tests/test_fixtures_pipeline.py`](../test_fixtures_pipeline.py) : si une règle
évolue, ajuster les fiches puis régénérer.
