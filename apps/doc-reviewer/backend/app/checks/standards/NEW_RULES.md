# Règles compilées par client

Les règles propres à une entreprise vivent dans son module `*_custom.py`.
Le pipeline générique charge les modules qui exposent `STANDARD_SPEC` et
synchronise leur catalogue en base au démarrage du backend.

## Ajouter une règle à un client existant

1. Ouvrir le module du client, par exemple
   `app/checks/standards/thales_custom.py`.
2. Ajouter la règle dans `_RULES_V1`.
3. Ajouter son entrée dans `RULE_METADATA` si le texte présenté dans l’API
    doit être plus précis que le `topic` par défaut.
4. Redémarrer le backend pour synchroniser le catalogue.
5. Ajouter un test dans `backend/tests/`, puis lancer le test ciblé.

### Règle simple : motif interdit

Utiliser `_rule` avec `pattern` lorsqu’un motif trouvé constitue une erreur. Le
moteur signale chaque occurrence et peut proposer un remplacement avec `\1`,
`\2`, etc. Pour une règle composée, passer directement `checks=[...]` à ce
même helper.

```python
_rule(
    "CUSTOM_DECIMAL_COMMA",
    "Les décimales doivent utiliser un point",
    pattern=r"(?<!\d)(\d+),(\d+)(?!\d)",
    severity="error",
    replacement=r"\1.\2",
)
```

### Règle obligatoire : élément absent ou incorrect

Utiliser `operator="regex_exists"` lorsqu’un élément doit être présent. Pour
obtenir une suggestion compréhensible :

- `expected` contient le regex utilisé par le moteur ;
- `expected_display` contient le texte attendu affiché à l’utilisateur ;
- `failure_message` contient la formulation négative affichée dans la suggestion ;
- `replacement` permet de corriger un élément présent mais incorrect ;
- `require_all=True` impose la présence du motif sur chaque cible (utile pour
    un footer répété sur plusieurs pages) ;
- `missing_anchor` indique un texte voisin auquel accrocher un élément absent ;
- `missing_anchor_position` vaut `"above"`, `"below"` ou `"same"` selon la
    mise en page. `"same"` pose la bbox directement sur l'ancre existante.

Les placeholders comme `{{meta_revision_number}}` sont résolus depuis le
mapping du document dans `expected_display` et `replacement`.

Pour une règle obligatoire corrigible, `expected_display` sert aussi de forme
canonique pour le diagnostic après un `FAIL`. Le moteur cherche alors une ligne
ou une fenêtre de mots proche et produit les différences minimales : caractère
ou mot corrigé, valeur manquante insérée, ou valeur incorrecte remplacée. Il
ne faut donc pas ajouter un second `operator="regex"` pour détecter chaque
valeur incorrecte. Si aucun candidat suffisamment proche n'est trouvé, le
moteur conserve le commentaire d'élément attendu absent et utilise
`missing_anchor` pour le positionner.

```python
_rule(
    "CUSTOM_TP1_REVISION_NUMBER",
    "Numéro de révision TP1",
    failure_message="numéro de révision non conforme.",
    severity="error",
    target=RuleTarget(page="all", region="footer", page_type="TP1"),
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=r"Revision\s+No\.?\s*{{meta_revision_number}}",
            expected_display="Revision No.{{meta_revision_number}}",
            missing_anchor=r"(?i)\bFirst\s+Issue\b",
        ),
    ],
)
```

Pour une règle composée de plusieurs éléments obligatoires, créer un `Check`
par élément. Cela permet d’indiquer précisément ce qui manque, au lieu de
signaler tout le bloc comme incorrect.

### Choisir la cible

- `region="full_page"` : tout le texte de la page ;
- `region="footer"` : le bandeau bas calculé à partir des coordonnées PDF ;
- `region="header"` ou `region="body"` : les zones correspondantes ;
- `page_type="TP1"` : uniquement les pages classifiées TP1 ;
- `page="all"` : toutes les pages, sauf si un numéro précis est requis.

Si la règle dépend d’un contexte document, utiliser le placeholder prévu dans
`compiled_rules.py` (`meta_cmm_number`, `meta_revision_date`,
`meta_revision_number`, etc.) plutôt qu’une valeur écrite en dur.

## Ajouter un nouveau client

1. Copier le module existant :

   ```text
   app/checks/standards/thales_custom.py
   -> app/checks/standards/<client>_custom.py
   ```

2. Adapter `STANDARD_CODE`, `STANDARD_LABEL`, `STANDARD_DESCRIPTION`, les
    règles et `STANDARD_SPEC`.
3. Vérifier que le fichier expose `STANDARD_SPEC` avec :
   - `code` ;
   - `label` ;
   - `description` ;
   - `versions` ;
   - `metadata`.
4. Le module sera découvert automatiquement et ajouté à `BUILTIN_STANDARDS`.
5. Si le client a besoin de classifier des pages, exposer aussi une fonction
   `classify_pages(parsed, document)` dans le module.
6. Ajouter des tests propres au client.

Aucune modification de `analyze.py`, `rules_engine.py` ou de l’exécuteur n’est
nécessaire pour ajouter un module client conforme à ce contrat.

## Vérification rapide

Depuis la racine du dépôt :

```powershell
Push-Location backend
python -m pytest tests/test_compiled_standard_catalogs.py -q
Pop-Location
```

Pour une règle qui modifie le texte, tester au minimum les cas suivants :

- élément présent et conforme : `PASS` ;
- élément présent mais incorrect : `FAIL` avec remplacement ;
- élément complètement absent : `FAIL` avec élément attendu lisible et ancre
  de suggestion correcte ;
- page hors cible : aucune suggestion.