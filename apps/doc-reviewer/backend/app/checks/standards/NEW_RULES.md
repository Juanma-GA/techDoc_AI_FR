# Regles par bundle client

Les regles officielles THALES sont declarees dans `app/checks/thales_rules/rules.py`.
Ce module est la source unique des `CompiledRule` et des metadonnees de presentation.
`app/checks/standards/thales_custom.py` reste une facade de compatibilite pour les
anciens imports ; ne pas y ajouter de regle ni modifier `RULE_METADATA` a la main.

`active_client.json` selectionne le bundle actif. Le registre charge ses modules
de regles, operations et classification depuis les chemins du manifest ; le
catalogue est synchronise au demarrage et les versions manifestes sont les defauts
des nouveaux uploads et des analyses historiques sans version enregistree.

## Ajouter une regle THALES

1. Ajouter une definition avec la fabrique `rule(...)` dans
   `app/checks/thales_rules/rules.py`.
2. Fournir dans cette definition son code, nom, description, message, type de
   presentation, severite, cible, checks et eventuelles traductions.
3. Ajouter la definition a `RULE_DEFINITIONS` a l'endroit correspondant a l'ordre
   d'execution souhaite. Les definitions de revision restent au debut : elles
  determinent les pages modifiees dont dependent les autres regles.
4. Ajouter un test du contrat de la regle et un test de comportement dans
   `backend/tests/`.

Exemple de definition declarative :

```python
CUSTOM_DECIMAL_COMMA = rule(
    code="CUSTOM_DECIMAL_COMMA",
    name="Valeurs decimales separees par un point",
    description="Les valeurs decimales utilisent un point, pas une virgule.",
    message="Une valeur decimale utilise une virgule.",
    kind="regex_flag",
    severity="warning",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex",
            expected=r"(?<!\d)(\d+),(\d+)(?!\d)",
            replacement=r"\1.\2",
        ),
    ],
    translations={
        "en": {
            "description": "Decimal values must use a point.",
            "message": "A decimal value uses a comma.",
        }
    },
)
```

`RULE_METADATA` dans la facade est genere depuis `RULE_DEFINITIONS`. Sa presence
sert uniquement aux appels historiques de catalogue.

## Operateur client

Utiliser un check generique si l'operateur est deja pris en charge. Pour une
operation propre au client, utiliser `operator="client_operation"`, nommer
`operation` et passer ses parametres dans `operation_params` :

```python
Check(
    field="text",
    operator="client_operation",
    operation="revision_consistency",
    operation_params={"control": "footer_date"},
)
```

Implementer cette operation dans le module `operations.py` declare par le
manifest. Elle recoit un `ClientOperationContext` et renvoie un `OperationResult`;
le coeur adapte ce resultat en verdict et en suggestions. Ne pas ajouter de
branche sur le code de regle dans le moteur. Toute operation utilisee doit etre
exportee par `OPERATIONS`; le chargeur bloque si une regle reference un nom absent.

Les controles de revision utilisent maintenant ce meme contrat. Leur moteur est
dans `app/checks/thales_rules/revision_engine.py` et l'ancien module
`standards/_thales_revision.py` ne sert plus que de facade de compatibilite.

## Classifier une page

La classification des pages appartient au module `page_classifier.py` declare
par le manifest. Le pipeline appelle son entree `classify_pages(parsed, document)`
depuis le `ClientBundle` actif. Les regles ne doivent pas etre declarees dans le
classifieur.

## Manifest et versions

- `active_client.json` selectionne un dossier bundle ; `CLIENT_BUNDLE` peut
  surcharger ce nom.
- Le manifest declare le client, les catalogues, leur version, le mapping et les
  modules Python du bundle.
- Les modules declares (`rules`, `operations`, `page_classifier` et le moteur
  interne de revision) sont charges dans un namespace isole ; leur contenu
  participe au `bundle_hash`.
- Toute evolution comportementale du bundle doit augmenter `bundle_version`.
- Le bundle ne stocke pas d'UUID de base de donnees ; les catalogues sont resolus
  en versions de standard par le registre.
- `GET /api/v1/client-config` expose l'identite, les hashes, les catalogues
  resolus et le mapping. `GET /api/v1/client-rules` expose les regles officielles ;
  `PATCH /api/v1/client-rules/{code}` modifie leur statut persiste dans
  `StandardVersion.disabled_rule_codes`.
- Les valeurs saisies par document sont stockees dans `Document.client_metadata`
  selon `mapping.json`. Les anciennes colonnes THALES et les champs PATCH plats
  restent compatibles pendant la transition.
- L'ecran Rules affiche le catalogue du bundle actif. L'ancien ecran checklist et
  regles utilisateur reste disponible pour depannage avec
  `VITE_LEGACY_RULES_UI=true`.
- `app/checks/sample_client/` est un bundle d'exemple non actif. Il sert de
  reference minimale pour les champs string/enum/string_list, les entites, les
  operations et le classifieur ; `test_client_registry.py` le charge sans
  modifier `active_client.json`.

## Tests

Depuis la racine du depot :

```powershell
Push-Location backend
python -m pytest tests/test_client_bundle_contract.py tests/test_client_registry.py tests/test_thales_catalog_baseline.py tests/test_thales_bundle_rules.py tests/test_compiled_standard_catalogs.py tests/test_revision_state.py -q
Pop-Location
```

Le test `test_thales_catalog_baseline.py` fige la serialisation du catalogue THALES
et rend explicite chaque changement de contrat.