# Regles par bundle client

Le bundle THALES est decoupe en deux normes, une par sous-dossier de
`app/checks/thales_rules/` :

| Norme | Dossier | Catalogue | Etat par defaut |
| --- | --- | --- | --- |
| ATA100 | `ata100/` | `THALES-CUSTOM` `v1` | actif |
| S1000D | `s1000d/` | `THALES-S1000D` `v1` | actif (execute seulement sur un PDF S1000D) |

Chaque norme declare ses regles dans son `rules.py` : source unique des
`CompiledRule` et des metadonnees de presentation, construites par la fabrique
commune `thales_rules/rule_factory.py` (`partial(build_rule, code_catalogue,
version)`). `RULE_METADATA` est genere depuis les definitions ; ne pas ajouter de
metadonnees manuelles paralleles. Le mapping (`mapping.json`) reste commun a
toutes les normes du client.

`active_client.json` selectionne le bundle actif. Le registre charge ses normes
(`norms` du manifest client), puis leurs modules de regles, operations et
classification depuis les chemins du manifest de chaque norme ; le catalogue est
synchronise au demarrage et les versions manifestes sont les defauts des nouveaux
uploads et des analyses historiques sans version enregistree. Dans l'ecran Rules,
chaque norme forme un groupe repliable (code = nom du dossier, libelle = `label`
du manifest de la norme) avec son bouton « Tout activer / Tout desactiver ».

## Ajouter une norme a un client

1. Creer `app/checks/<bundle>/<norme>/` avec `__init__.py`, `manifest.json`,
   `rules.py` et, si besoin, `operations.py` / `page_classifier.py` :

   ```json
   {
     "label": "S1000D",
     "bundle_version": "1.0.0",
     "catalogs": [{ "code": "THALES-S1000D", "version": "v1" }],
     "modules": { "rules": "rules.py", "operations": "operations.py" },
     "default_enabled": false
   }
   ```

2. Exporter `RULE_DEFINITIONS` et `STANDARD_SPEC` dans `rules.py` (voir
   `s1000d/rules.py`), et `OPERATIONS` dans `operations.py`. Les noms d'operations
   et les codes de catalogue doivent etre uniques dans tout le bundle : prefixer
   les operations par la norme (`s1000d_...`).
3. Ajouter le nom du dossier a `norms` dans le `manifest.json` du client et
   augmenter son `bundle_version`.
4. Ajouter les textes du front : `client-rules.fr.json` / `client-rules.en.json`
   (nom et description) et `rules.messages` / `rules.catalog` de `fr.json` /
   `en.json`.
5. `default_enabled: false` cree le catalogue avec toutes ses regles
   desactivees ; l'etat est ensuite conserve par version de catalogue.

## Ajouter une regle a une norme

1. Ajouter une definition avec la fabrique `rule(...)` dans le `rules.py` de la
   norme (`app/checks/thales_rules/ata100/rules.py` ou `s1000d/rules.py`). Pour
   une norme dont ce fichier est deja volumineux, placer les definitions dans un
   module de domaine et les exporter/importer dans le `RULE_DEFINITIONS` central.
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

`RULE_METADATA` dans le bundle est genere depuis `RULE_DEFINITIONS`.

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
dans `app/checks/thales_rules/ata100/revision_engine.py`.

Les controles S1000D sont regroupes en trois operations a parametre `control`
(`s1000d_dm_status`, `s1000d_front_matter`, `s1000d_content`). Un controle ne
renvoie jamais FAIL sans preuve : lorsque la structure attendue (LOEDM, titre,
annotations de lien) est absente du PDF, il renvoie INCONCLUSIVE avec la raison.

Les normes sont exclusives par document : un module optionnel `norm_detector.py`
(declare dans le manifest de la norme, il exporte `matches_document(parsed)`)
reconnait le PDF de la norme, et l'analyse n'execute que les regles de la norme
detectee (S1000D si le PDF imprime une LOEDM listant des DMC, sinon la norme sans
detecteur, ATA100). Une regle propre a un type de mise a jour ou a un constructeur
se limite avec `only_if=Condition(field=..., equals=...)` ; les champs
`meta_update_type` (Migration / MCO) et `meta_manufacturer` viennent du mapping.

## Classifier une page

La classification des pages appartient au module `page_classifier.py` declare
par le manifest de la norme (aujourd'hui ATA100 uniquement). Le pipeline appelle
son entree `classify_pages(parsed, document)` depuis le `ClientBundle` actif ; les
classifieurs de plusieurs normes sont enchaines. Les regles ne doivent pas etre
declarees dans le classifieur.

## Manifest et versions

- `active_client.json` selectionne un dossier bundle ; `CLIENT_BUNDLE` peut
  surcharger ce nom.
- Le manifest declare le client, ses normes (`norms`) ou ses catalogues, le mapping
  et les modules Python du bundle ; chaque norme declare ses propres catalogues,
  sa version et ses modules.
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
python -m pytest tests/test_client_bundle_contract.py tests/test_client_registry.py tests/test_thales_catalog_baseline.py tests/test_thales_bundle_rules.py tests/test_compiled_standard_catalogs.py tests/test_revision_state.py tests/test_s1000d_rules.py -q
Pop-Location
```

Le test `test_thales_catalog_baseline.py` fige la serialisation du catalogue THALES
et rend explicite chaque changement de contrat.