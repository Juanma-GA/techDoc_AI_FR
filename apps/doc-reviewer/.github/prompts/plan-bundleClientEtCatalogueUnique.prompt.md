## Plan: Bundle client et catalogue unique

Le bundle client devient le point de configuration de l’application. Le choix du bundle actif est externe aux dossiers clients : l’application lit `backend/app/checks/active_client.json`, puis charge le `manifest.json` situé dans le dossier sélectionné. Pour cette installation, `active_client.json` sélectionne `thales_rules`. Le frontend ne choisit plus les normes : il affiche les règles du manifest actif et permet uniquement d’activer/désactiver chaque règle.

La refonte corrige aussi la dispersion THALES actuelle : `rules.py` sera l’unique endroit où les règles sont déclarées et construites, avec leur nom, description, messages et configuration d’exécution. `operations.py` sera le module métier client cohérent qui porte les calculs, l’état de révision, les opérateurs spécialisés et les résultats nécessaires aux suggestions. `page_classifier.py` est la seule séparation prévue lorsque la classification des pages le justifie.

**Principe de migration sans casse**

La migration ne sera pas une réécriture en une seule fois. Chaque palier doit garder les façades et les contrats historiques nécessaires, passer les tests existants, puis déplacer une responsabilité précise. Les colonnes THALES, les endpoints standards et l’alias `RULE_METADATA` peuvent rester temporairement pour compatibilité, mais aucune nouvelle fonctionnalité ne doit continuer à ajouter du couplage dans le cœur. Les règles officielles du client et les règles utilisateur importées/suggérées restent deux catégories séparées ; le catalogue officiel du bundle ne doit jamais être reconstruit à partir de règles utilisateur.

**Structure cible du bundle**
- `backend/app/checks/active_client.json` (hors dossier client) : sélection du bundle actif pour l’installation, par exemple `{ "bundle": "thales_rules" }`.
- `manifest.json` : `client_code`, libellé, `bundle_version`, version de contrat, catalogues actifs (code/version), modules optionnels et options UI héritées.
- `mapping.json` : champs de contexte document, types (`string`, `enum`, `string_list`, etc.), longueurs, valeurs possibles, obligations, défauts et entités/regex client.
- `rules.py` : unique fabrique `rule(...)` et unique liste de définitions. Chaque définition produit le `CompiledRule` et ses métadonnées de présentation. Les règles de révision utilisent exactement cette même fabrique ; il n’existe plus de chemin spécial `REVISION` ni de seconde définition manuelle dans `RULE_METADATA`. Pour la compatibilité, `RULE_METADATA` peut rester un alias généré depuis les définitions, mais il ne doit plus être édité directement.
- `operations.py` : calculs THALES regroupés et enregistrés via un contrat unique : extraction/état de révision, cohérence Highlights/LEP/footer, conversions pression/température, ponctuation, shop verification, holder/document type et propositions de correction. Une opération reçoit un contexte d’exécution et renvoie un résultat structuré ; le cœur reste responsable des cibles, bboxes et de la persistance.
- `page_classifier.py` : optionnel, uniquement pour remplir `page_type` et éventuellement préparer l’état de page avant l’exécution.
- `tests/` : tests du contrat, des règles, des opérations et du classifieur.

**Contrat de lancement et du manifest**
1. Ajouter `backend/app/checks/active_client.json` comme sélection par défaut, avec un format limité à un nom de bundle, par exemple `{ "bundle": "thales_rules" }`. Une variable d’environnement `CLIENT_BUNDLE` peut surcharger ce nom au lancement ; elle ne doit pas créer une seconde configuration concurrente appelée `client_manifest`.
2. Résoudre le nom vers `backend/app/checks/<bundle>/manifest.json`, puis charger une seule fois via un `client_registry` : identité, mapping, catalogue, opérations et classifieur. Aucun module du cœur ne fait d’import direct de `thales_custom`.
3. Le `manifest.json` interne décrit le client et déclare les catalogues actifs par code/version, par exemple le catalogue THALES v1 et, si nécessaire, des normes génériques approuvées. Il ne doit jamais stocker d’UUID de base de données ; les catalogues sont résolus en `StandardVersion` au démarrage.
4. Les nouveaux uploads reçoivent les versions du manifest dans `Document.standard_version_ids`. Les documents existants gardent leurs versions enregistrées pour préserver la reproductibilité ; si un document historique n’en possède aucune, l’analyse utilise le manifest comme fallback.
5. Les états d’activation des règles restent dans `StandardVersion.disabled_rule_codes`. Le manifest définit la version/cible par défaut, pas l’état courant des cases, afin que les choix de désactivation restent persistants.
6. La validation du bundle est bloquante au démarrage : sélection absente, manifest ou fichier déclaré absent, version invalide, collision de codes, metadata manquante, mapping incohérent ou opération inconnue doivent empêcher l’application de démarrer avec une erreur explicite. Une erreur de synchronisation du catalogue client ne doit pas être silencieusement absorbée.
7. Toute modification comportementale du bundle doit augmenter `bundle_version`. Le registre calcule aussi un `bundle_hash`/`manifest_hash` pour permettre de vérifier quelle implémentation a produit une analyse.

**Étapes d’implémentation**

### Phase 1 — Recomposer THALES proprement
1. Introduire les contrats `ClientBundle`, `ClientRuleDefinition`, `ClientOperation`, `OperationResult` et `ClientMapping` dans un module générique du backend. `OperationResult` doit au minimum porter `status`, `observed`, `expected`, `message`, `original`, `proposed` et `span` ; le cœur transforme ensuite ce résultat en `RuleResult`/`RawSuggestion`.
2. Créer `backend/app/checks/thales_rules/manifest.json`, `mapping.json`, `rules.py`, `operations.py` et les tests du bundle. Ajouter `active_client.json` et le loader sans changer encore la sélection effective des documents, afin de valider la configuration séparément.
3. Déplacer toutes les constructions de `_RULES_V1` dans `rules.py` derrière une seule fabrique. La fabrique doit accepter au même endroit le code, nom, description, sévérité, cible, checks, message, exemples, traductions et paramètres de l’opération. Elle construit à la fois le `CompiledRule`, ses métadonnées sérialisables et le catalogue API.
4. Générer automatiquement l’alias de compatibilité `RULE_METADATA` depuis les définitions de `rules.py`. Aucun bloc de metadata parallèle ne doit être édité à la main ; les anciens imports peuvent continuer à fonctionner jusqu’à la fin de la migration.
5. Reprendre les règles `REVISION` comme des règles ordinaires de `rules.py`. Le contrôle (`lep_star`, `footer_date`, etc.) devient un paramètre explicite du check/opération, par exemple `operation="revision_consistency"` et `operation_params={"control": "footer_date"}` ; le type `RevisionControl` fermé et le chemin de traitement spécial sont retirés du contrat générique.
6. Déplacer la logique de `_thales_revision.py`, les constantes THALES et les fonctions spécialisées actuellement dans `compiled_rule_operators.py` et `compiled_rule_suggestions.py` vers `operations.py`. L’état de révision y est construit une fois par document et mis en cache dans le contexte d’exécution du bundle, pas via un détail caché de `thales_custom.py`.
7. Enregistrer les opérations dans une table unique, par exemple `OPERATIONS: dict[str, ClientOperation]`. Le cœur appelle toujours la même interface ; il ne doit pas ajouter de branche `if rule_code == ...` ou `if check.operator == ...` pour THALES.
8. Garder `page_classifier.py` limité à la classification et à l’initialisation des informations de page. Il peut appeler une opération de préparation de révision, mais ne doit pas devenir un second lieu de déclaration de règles.
9. Transformer `standards/thales_custom.py` et `standards/_thales_revision.py` en façades de compatibilité réexportant le bundle pendant la migration. Aucun nouveau code métier ne doit y être ajouté.
10. Comparer avant/après les codes de règles, la sérialisation du catalogue, les metadata, les statuts, les classifications, l’état `is_modified`, les suggestions et les bboxes sur les fixtures THALES existantes avant de retirer l’ancien chemin.

### Phase 2 — Rendre le cœur réellement générique
11. Modifier `compiled_rules.py` pour accepter des noms d’entités, champs de contexte et opérations déclarés par le bundle, avec validation au chargement du bundle. Les primitives génériques restent disponibles ; elles ne sont plus mélangées avec les champs THALES dans des `Literal` fermés.
12. Adapter `compiled_rule_runtime.py` pour charger les entités et tokens de contexte depuis le mapping actif. Les patterns génériques restent dans le cœur ; `cmm_number`, logo, dates et autres patterns THALES viennent du bundle.
13. Transformer `compiled_rule_operators.py` en registre : `evaluate_check()` résout l’opérateur générique ou l’opération du bundle via le contrat `ClientOperation`. Le cœur ne contient plus d’URL, texte, enum constructeur, constante Fahrenheit ou import THALES.
14. Transformer `compiled_rule_suggestions.py` en adaptateur générique. Il garde la génération regex, les ancres et la géométrie ; il délègue les `OperationResult` spécialisés de `operations.py` et matérialise leurs spans/propositions en `RawSuggestion`.
15. Adapter `compiled_rule_executor.py` et `rules_engine.py` pour transmettre le `ClientBundle`/contexte d’exécution, appeler le classifieur déclaré, conserver l’ordre actuel, le filtrage des règles désactivées et les pipelines unités/layout/vision.
16. Adapter `checklist_compiler.py` afin que les champs, tokens et opérations autorisés soient ceux du mapping/contrat actif. Les checklists existantes restent une fonctionnalité utilisateur séparée ; elles ne créent pas un second format pour les règles officielles du client.

### Phase 3 — Manifest, catalogues et analyse
17. Ajouter le loader/registre client et la validation de manifest : `active_client.json` valide, bundle existant, manifest et fichiers déclarés présents, version valide, catalogues déclarés, unicité des codes, metadata complète et opérations référencées. Cette validation est exécutée avant de monter l’application et ses erreurs ne doivent pas être ignorées par `main.py`.
18. Adapter `standards/__init__.py` et `db/seed.py` pour synchroniser le catalogue issu de `rules.py`, tout en conservant les normes génériques éventuellement listées par le manifest. Une resynchronisation ne doit jamais réinitialiser `disabled_rule_codes`.
19. Ajouter la résolution centralisée `active_standard_versions(db)` utilisée par l’upload et l’analyse. Les nouveaux documents prennent les versions du manifest ; les anciens conservent leurs versions enregistrées et n’utilisent le fallback que si leur liste est vide. Retirer de l’interface l’obligation de fournir `standard_version_ids`, mais conserver le champ de base et le paramètre API pour compatibilité technique.
20. Adapter `api/analyze.py` pour utiliser les versions résolues et enrichir chaque snapshot avec `client_code`, `bundle_version`, `contract_version`, `manifest_hash`, `mapping_hash`, `bundle_hash`, catalogues actifs, règles compilées et paramètres d’opération réellement utilisés. Une modification de code métier doit augmenter `bundle_version` ; une réanalyse historique doit utiliser une version de bundle disponible ou signaler explicitement qu’elle utilise le bundle courant.
21. Ajouter des tests de démarrage/contrat : sélection absente, manifest invalide, fichier déclaré absent, catalogue absent, collision de codes, opération inconnue, client THALES actif, fallback d’un document historique, conservation des toggles après resynchronisation et stabilité des hashes dans un snapshot.

### Phase 4 — Mapping extensible des documents
22. Ajouter une colonne JSON/TEXT `client_metadata_json` à `Document` via Alembic. Elle porte les variables propres au client et autorise notamment `string_list` pour plusieurs PNR.
23. Généraliser `document_context.py` avec validation du mapping : obligatoire, enum, longueur, type, défaut et valeurs répétées. Les anciennes colonnes THALES restent lisibles pendant la transition et servent de fallback uniquement lorsque la clé JSON correspondante est absente.
24. Adapter `schemas.py` et `api/documents.py` pour accepter un contexte générique, tout en acceptant les huit champs THALES historiques et en les synchronisant vers le JSON. Les champs historiques ne doivent pas être recopiés dans le bundle comme une seconde déclaration.
25. Adapter `api/analyze.py`, `compiled_rule_runtime.py`, `rules_engine._doc_meta_block()` et les chemins sémantiques/LLM pour lire le contexte déclaré par le bundle, sécuriser les valeurs utilisateur et sérialiser les listes sans ambiguïté.
26. Tester l’ajout d’une variable uniquement dans `mapping.json`, sa sauvegarde, sa validation, son utilisation dans un `FieldRef`, son apparition dans l’API et sa conservation dans le snapshot.
27. Couvrir les PNR multiples : une liste dans le mapping, règle TP1 sur toutes les valeurs, règles d’en-tête sur les racines/séries attendues, et suggestions localisées.

### Phase 5 — API et interface de règles
28. Ajouter `GET /api/v1/client-config` renvoyant le manifest actif, le client, la version, les hashes, les catalogues/version résolus, les champs de mapping et les règles de présentation. Ajouter `GET /api/v1/client-rules` et `PATCH /api/v1/client-rules/{code}` pour que le frontend ne dépende pas des détails internes de `StandardVersion`; ces endpoints délèguent en interne au mécanisme `disabled_rule_codes` existant.
29. Enrichir `CompiledRuleSummary` et la réponse `client-rules` avec `name/title`, `description`, `message` si nécessaire et un statut explicite. Le statut affiché doit distinguer : activée/désactivée, mode d’exécution (`deterministic`, `semantic`, `manual`, `unsupported`) et sévérité.
30. Adapter `frontend/src/hooks/useRules.ts` pour charger les règles du manifest actif via `client-rules`, plutôt que `activeStandardVersionIds` du store. Le hook de toggle appelle le nouvel endpoint ; la résolution `standard_id`/`version_id` reste interne au backend.
31. Adapter `frontend/src/types/domain.ts` et créer `useClientConfig.ts` pour typer le manifest, le mapping et les règles enrichies. Le frontend ne doit plus coder `Airbus | Boeing`, les champs THALES, le préfixe `CUSTOM_` ou une liste de normes.
32. Refaire `frontend/src/routes/Rules.tsx` comme écran des règles officielles du client actif : en-tête client/catalogue/version, sections actives/inactives, interrupteur, nom, description, statut d’exécution et sévérité. Une règle désactivée reste visible et clairement marquée.
33. Cacher dans le frontend, sans supprimer les fichiers ni les APIs, le bloc `Normes cibles actives` et le bloc `Administration des normes` dans `Settings.tsx`, ainsi que `ChecklistImportCard` dans `Rules.tsx`. Le code caché doit rester réactivable par un flag documenté, mais aucune sélection persistée ne doit continuer à influencer les nouveaux uploads.
34. Retirer du parcours visible les anciens choix de normes dans `DocumentsList.tsx`, `StandardPicker.tsx`, `filtersStore.ts`, `useStandards.ts` et `useDocuments.ts`. Conserver leurs types, composants, hooks et endpoints en legacy compilable, sans les utiliser pour la sélection du bundle actif.
35. Séparer explicitement les règles officielles du bundle des règles utilisateur (`Rule`, `RulesSuggestPanel`, anciennes règles checklist). L’écran `client-rules` n’affiche que le catalogue officiel ; les APIs et composants utilisateur peuvent rester présents mais masqués dans cette première version, afin qu’une règle utilisateur ne modifie jamais `rules.py` ni le catalogue du client.
36. Adapter `suggestionText.ts` pour préférer le nom/message/description fournis par l’API du bundle et conserver le fallback des messages historiques et des normes génériques. Les traductions de règles ne doivent plus être obligatoirement présentes dans `en.json`/`fr.json`.

### Phase 6 — Documentation, template et nettoyage
37. Mettre à jour `backend/app/checks/standards/NEW_RULES.md` avec le workflow réel : copier un dossier client, modifier `active_client.json` seulement pour le sélectionner, puis modifier manifest/mapping/operations/rules dans le dossier client et tester ; supprimer la documentation qui invite à modifier le cœur ou `thales_custom.py`.
38. Ajouter un bundle minimal de test avec un champ, une enum, une liste et une opération différente. Son chargement doit fonctionner sans branche spéciale dans `rules_engine`, `compiled_rule_operators`, `compiled_rule_suggestions`, les modèles frontend ou les locales.
39. Après validation, supprimer les branches THALES du cœur et garder seulement les façades de compatibilité nécessaires aux anciens imports. Ne pas supprimer les colonnes THALES avant une migration de données explicite et un plan de lecture des historiques.

**Fichiers importants**
- `backend/app/checks/active_client.json` — sélection du bundle actif pour l’installation ; `CLIENT_BUNDLE` peut le surcharger au lancement.
- `backend/app/checks/thales_rules/manifest.json`, `mapping.json`, `rules.py`, `operations.py`, `page_classifier.py` — nouveau bundle et unique déclaration métier.
- `backend/app/checks/client_registry.py`, `backend/app/config.py`, `backend/app/main.py` — résolution et validation bloquante du bundle au lancement.
- `backend/app/checks/standards/__init__.py`, `thales_custom.py`, `_thales_revision.py`, `backend/app/db/seed.py` — découverte et façades de transition.
- `backend/app/core/compiled_rules.py`, `compiled_rule_runtime.py`, `compiled_rule_operators.py`, `compiled_rule_executor.py`, `compiled_rule_suggestions.py`, `rules_engine.py`, `checklist_compiler.py` — contrats génériques et délégation.
- `backend/app/core/document_context.py`, `backend/app/db/models.py`, `backend/app/schemas.py`, `backend/app/api/documents.py`, `backend/app/api/analyze.py` — contexte JSON, defaults et snapshots.
- `backend/app/api/rules.py`, `backend/app/api/standards.py`, nouvelle API client — contrat des règles, descriptions, toggles et configuration client.
- `backend/alembic/versions/` — migration de `client_metadata_json`.
- `frontend/src/routes/Settings.tsx`, `Rules.tsx`, `DocumentsList.tsx`, `Standards.tsx`, `ChecklistImportCard.tsx` — masquage non destructif, retrait des anciens choix et écran règles.
- `frontend/src/components/upload/StandardPicker.tsx`, `frontend/src/stores/filtersStore.ts`, `frontend/src/hooks/useClientConfig.ts`, `useRules.ts`, `useStandards.ts`, `useDocuments.ts`, `frontend/src/types/domain.ts`, `frontend/src/lib/suggestionText.ts` — contrat frontend, compatibilité legacy et toggles.
- `frontend/src/locales/en.json`, `fr.json` — interface générique uniquement ; suppression progressive des textes de règles client.
- `backend/tests/test_compiled_standard_catalogs.py`, `test_revision_state.py`, `test_standards_api.py`, `test_documents.py`, `test_analyze_sse.py`, nouveaux tests de manifest/bundle/config/client-rules ; tests frontend du panneau Rules/Settings.

Organisation des fichiers : 

backend/app/checks/
├── active_client.json          # choix du bundle utilisé par l’application
├── client_registry.py           # loader/validation générique du bundle
├── thales_rules/
│   ├── manifest.json           # identité et configuration de THALES
│   ├── mapping.json
│   ├── rules.py
│   ├── operations.py
│   ├── page_classifier.py
│   ├── README.md
│   └── tests/
│       ├── test_rules.py
│       ├── test_operations.py
│       ├── test_page_classifier.py
│       └── test_contract.py
└── autre_client/
    ├── manifest.json
    └── ...

**Vérification**
1. Avant extraction, figer la liste des règles, leurs metadata, opérateurs, statuts et résultats THALES avec les tests existants.
2. Après extraction, vérifier que toutes les règles, y compris `REVISION`, passent par la même fabrique de `rules.py` et que `operations.py` fournit les mêmes résultats.
3. Tester qu’un opérateur inconnu, une metadata manquante, une collision de code ou un mapping invalide est rejeté au chargement du bundle, jamais découvert seulement pendant une analyse.
4. Tester `active_client.json`, la surcharge `CLIENT_BUNDLE`, le manifest interne et l’échec bloquant d’un bundle incomplet.
5. Tester que le manifest sélectionne automatiquement les versions actives, qu’un nouvel upload les enregistre et qu’un document historique sans versions utilise le fallback.
6. Tester le toggle d’une règle via `client-rules` : la ligne reste visible, son statut passe à désactivé, elle n’est plus exécutée et l’état survit au redémarrage/sync.
7. Tester que `RULE_METADATA` est généré depuis `rules.py` et qu’aucun dictionnaire metadata manuel n’est nécessaire.
8. Tester l’API et l’écran règles : nom, description, sévérité, statut actif/inactif et mode d’exécution sont affichés sans traduction codée par rule code.
9. Vérifier que l’ancien sélecteur n’a plus d’effet : `Settings.tsx`, `DocumentsList.tsx`, `StandardPicker.tsx` et le store ne changent pas le catalogue utilisé par un nouvel upload.
10. Vérifier que les trois blocs legacy ne sont pas rendus, tandis que `Standards.tsx`, `ChecklistImportCard.tsx`, `RulesSuggestPanel` et leurs endpoints restent présents et compilables.
11. Vérifier que les règles utilisateur restent séparées du catalogue officiel et ne peuvent pas modifier `rules.py` ou le manifest.
12. Tester la compatibilité des champs THALES historiques et le nouveau JSON, y compris plusieurs PNR.
13. Vérifier la reproductibilité : snapshot avec versions, hashes, mapping, paramètres d’opération et catalogue compilé ; réanalyse avec bundle absent ou différent gérée explicitement.
14. Backend : tests ciblés puis `python -m pytest -q`, `ruff check app tests`, `mypy app` si disponibles.
15. Frontend : `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, puis Playwright sur l’écran Settings/Rules et une analyse SSE.

**Décisions**
- `active_client.json`, placé hors des dossiers clients, choisit le bundle actif ; le `manifest.json` interne décrit ce bundle. `CLIENT_BUNDLE` est l’unique surcharge d’environnement prévue.
- Le manifest peut lister le catalogue client et des normes génériques approuvées ; il remplace le choix persistant `activeStandardVersionIds` pour les nouveaux runs.
- `rules.py` est la source unique de déclaration et de metadata des règles. Il n’y a plus de dictionnaire de metadata séparé ni de constructeur particulier pour REVISION.
- `RULE_METADATA` peut rester temporairement comme alias calculé pour les anciens imports, mais aucune metadata ne doit être écrite dans ce dictionnaire.
- `operations.py` est la source unique de calculs/opérations/suggestions métier THALES. `page_classifier.py` reste une exception spécialisée de structure, pas un deuxième système de règles.
- Les opérations utilisent un contrat unique et renvoient des résultats structurés ; le cœur ne connaît pas les codes ou calculs THALES.
- Le toggle individuel reste piloté par `disabled_rule_codes` en base ; masquer l’administration des normes ne supprime pas cette capacité.
- Le mapping des documents devient JSON extensible, avec compatibilité temporaire des colonnes THALES et support des listes de PNR.
- Les règles officielles du bundle sont séparées des règles utilisateur ; l’écran principal ne montre et ne modifie que le catalogue officiel.
- L’import checklist, l’administration des normes et tous les anciens sélecteurs de normes sont masqués/commentés dans le frontend mais leurs composants, APIs et code restent disponibles en legacy compilable.
- Les snapshots enregistrent les versions et hashes du bundle/mapping/manifest ; toute modification comportementale impose une nouvelle version du bundle.

**Hors périmètre initial**
- Choisir un client différent pour chaque document.
- Supprimer immédiatement les anciennes colonnes et APIs THALES.
- Refaire toutes les normes génériques existantes.
- Transformer les calculs complexes en JSON pur ; les opérations Python restent permises derrière le contrat validé.
