# Donnees simulees — Catia Toolbox

Jeu de donnees **100 % synthetique** pour essayer la Toolbox sans CATIA ni
donnees reelles. Tout est reproductible :

```bash
# depuis apps/catia-toolbox/
python sample-data/generate_sample.py
# (ou backend/.venv/Scripts/python.exe sample-data/generate_sample.py)
```

Cela cree (ignores par git, cf. `.gitignore`) :

| Artefact | Sert a |
|---|---|
| `assembly_v1/` | Onglet **Import** -> Scanner un dossier (donnez le chemin absolu affiche par le script) |
| `assembly_v2/` | Onglet **Comparaison** (2e import = variante modifiee) |
| `listing_v1.csv` | Onglet **Import** -> Importer un listing (CSV) |
| `listing_v2.json` | Onglet **Import** -> Importer un listing (JSON) |
| `replacement_mapping.csv` | Onglet **Remplacement** (colonnes `old;new`) |

## Mode d'emploi rapide

1. **Import** : scanner `assembly_v1` (puis `assembly_v2` pour avoir 2 imports).
2. **Comparaison** : base = v1, candidat = v2.
3. **Verifications** : sur v1 (profondeur max 6 par defaut).
4. **Conversion** : sur v1.
5. **Remplacement** : sur v1, importer `replacement_mapping.csv`.

## Resultats attendus (reference)

L'arborescence v1 (14 fichiers, 12 dossiers) contient volontairement :
profondeur 8, doublon de nom (`Bras_Principal.CATPart` x2), nommage
incoherent (espaces / MAJUSCULES / snake / kebab), extensions interdites
(`.bak`, `.tmp`), fichiers convertibles disperses.

| Module | Resultat attendu |
|---|---|
| **Comparaison** v1->v2 | 1 ajout (`Nouvelle_Piece.CATPart`), 1 suppression (`apercu.cgr`), 2 modifies (`Ensemble Principal.CATProduct`, `plan-detail.CATDrawing`) |
| **Verifications** | ~14 violations : 2 `danger` (.bak/.tmp), 3 `warning` (profondeur + doublon), ~9 `info` (nommage) |
| **Conversion** | 11 fichiers convertibles -> `composer/.../*.smg` |
| **Remplacement** | 4 occurrences (2 pour `Bielle.CATPart`, 2 pour `Bras_Principal.CATPart`) |
