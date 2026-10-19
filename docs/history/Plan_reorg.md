
# Archived Reorganization Plan

> Execution status: phases 0 through 7 completed. The live AACF source was unavailable, so AACF compliance remains `AACF NON VERIFIABLE`. `scripts/check_standard.sh` was not executed because Bash was unavailable in the Windows environment. Known launcher port discrepancies were documented but not changed by this documentation reorganization.

Plan : refactor documentation et skills

Contexte global

- Objectif : Réorganiser la documentation et les skills en une structure portable, sans dépendre d’un harness spécifique (Copilot, Claude Code, etc.).
- Langue : Les nouvelles skills et documents techniques seront en anglais. Les README métier existants pourront rester en français temporairement.
- Source de vérité : Les skills deviennent la source de vérité. Les agents ne sont que des wrappers de compatibilité.
- Priorité : AACF est prioritaire sur STANDARD_POC. Ce dernier reste le cadre local du repo sans usurper le rôle d’AACF.
- Clarification de responsabilité : La skill aacf-compliance doit rester fortement centrée sur l’AACF externe, sans jamais être confondue avec le standard repo.
- Clarification de responsabilité : La skill audit-standard doit rester le cœur de la conformité locale et s’appuyer explicitement sur PROMPT_AUDIT_STANDARD.md comme format de rapport.
- Clarification de responsabilité : Les guides de test comme AACF_TESTING_GUIDE.md restent des outils de validation opérationnelle, pas des sources normatives.


Phase 0 — Baseline et classification

1. Inventorier les apps :
- catia-toolbox
- corpus-agent
- doc-reviewer
- doc-writer
- ocr-vision
- s1000d-extractor
- _template
2. Comparer les ports mentionnés dans les README et les launchers/config existants.
3. Identifier les documents redondants, contradictoires et obsolètes.
4. Vérifier les liens existants dans :
- README.md
- CLAUDE.md
- STANDARD_POC.md
- PROMPT_AUDIT_STANDARD.md
- Agents.md
- AACF_TESTING_GUIDE.md
- SESSION_SUMMARY.md
- ANALISIS_TECNICO_EJECUTIVO.md
5. Classer les références FTM selon :
- legacy supprimable
- référence générique mal nommée
- concept métier
- fixture
- historique
- référence obsolète
6. Clarifier les rôles de :
- CLAUDE.md
- STANDARD_POC.md
- Agents.md
- aacf-compliance.agent.md
- PROMPT_AUDIT_STANDARD.md
- AACF_TESTING_GUIDE.md
- SESSION_SUMMARY.md
- ANALISIS_TECNICO_EJECUTIVO.md
- les archives historiques / ADR


Phase 1 — Hiérarchie documentaire

1. Définir la source de vérité unique pour chaque sujet :
- README.md : point d’entrée général, inventaire exact des apps, liens principaux
- CLAUDE.md : instructions locales, sécurité, méthode et validations
- STANDARD_POC.md : standard technique normatif du repo
- CONTRIBUTING.md : workflow Git / PR / branches / commits
- docs/index.md : index documentaire
- docs/standards/ : modèles, procédures, contrats standards
- docs/apps/ : onboarding et matrice de conformité
- docs/adr/ : décisions historiques
- apps/<poc>/README.md : docs fonctionnelles et opérationnelles de chaque app
2. Règle cible : Un sujet = une seule source de vérité. Les autres documents doivent pointer vers elle sans recopier le contenu.
3. Revoir la séparation entre :
- règles projet
- docs humaines
- skills
- procédures
- historique


Phase 2 — Contrat commun des skills

1. Créer un document de référence pour le format portable des skills, sans dépendre d’un harness particulier.
- Emplacement : .github/skills/<skill-name>/SKILL.md
2. Chaque skill doit contenir :
- frontmatter YAML minimal
- name
- description avec déclencheurs explicites
- cas où la skill ne doit pas être utilisée
- entrées attendues
- documents normatifs à consulter
- procédure
- validations
- sortie attendue
- limites
- règles de sécurité
3. Portabilité obligatoire :
- Interdictions :
- Pas de dépendance à aacf_fetch
- Pas de dépendance à gh
- Pas de dépendance à un terminal
- Pas de dépendance à VS Code
- Pas de dépendance à l’écriture
- Les capacités optionnelles doivent avoir un comportement de repli explicite.
4. Les champs spécifiques à Copilot (ex: tools, agents) doivent rester dans les adaptateurs (ex: .agent.md), jamais dans la skill portable.
5. Tests de compatibilité :
- Vérifier que les skills fonctionnent dans Copilot, Claude Code, et autres harness compatibles.
- Prévoir un fallback manuel si la découverte automatique échoue.


Phase 3 — Skills read-only, priorisées
Créer d’abord les skills qui ne modifient rien.

1. repository-onboarding
- Découvre le monorepo, les apps, les règles applicables, les fichiers référents et l’ordre de lecture recommandé.
- Sortie : inventaire, parcours de prise en main, risques, validations proposées.
2. audit-standard
- Audit une app contre STANDARD_POC.md.
- Vérifie les règles de STANDARD_POC.md.
- S’appuie explicitement sur PROMPT_AUDIT_STANDARD.md comme format de rapport.
- Sortie : faits confirmés, écarts, gravité, fichiers concernés, actions proposées, éléments non vérifiés.
- Interdit d’appliquer des corrections dans cette skill.
- Cette skill est le cœur de la conformité locale ; elle ne remplace pas l’AACF externe ni les sources normatives du framework.
3. poc-validation
- Organise les validations disponibles :
- check_standard
- pytest
- build frontend
- typecheck
- lint
- Vitest
- Playwright
- packaging
- Distingue contrôles exécutés vs recommandés.
4. aacf-compliance
- Source normative : AACF (priorité externe).
- Vérifie la version AACF si le MCP est disponible.
- Renvoie AACF NON VERIFIABLE si le MCP est inaccessible.
- Ne présente jamais STANDARD_POC.md comme preuve de conformité AACF.
- Reste strictement read-only.
- Ne divulgue ni secret ni donnée utilisateur.
- La skill aacf-compliance doit rester fortement centrée sur l’AACF externe, sans jamais être confondue avec le standard repo.
- L’adaptateur aacf-compliance.agent.md reste un wrapper compatible, sans devenir la source de vérité.


Phase 4 — Skills mutantes contrôlées
Créer ensuite les skills mutantes, avec confirmation explicite avant tout changement.

1. new-poc
- Utilise _template et new_poc.sh.
- Demande confirmation avant création/modification.
- Vérifie : slug, port, README, scripts, tests.
2. frontend-design-system
- Encadre les modifications liées à :
- UI
- design tokens
- Tailwind
- thèmes
- i18n
- composants partagés
- Toute modification transversale doit être signalée et validée.
3. release-package
- Vérifie :
- launcher
- build frontend conditionnel
- port
- bind local
- contenu du ZIP
- emplacement final : apps/<poc>/dist/
- Assure que le packaging reste conforme au standard.
4. git-pr-workflow
- Documente :
- feature/<name>
- fixing/<name>
- une branche par tâche
- une PR par tâche
- branches empilées
- branche courante associée à la PR parente comme base d'une branche dépendante
- merge de origin/main dans la branche dépendante après le merge de la PR parente
- validations avant chaque push.


Phase 5 — Normalisation de la documentation des apps

1. Créer un template commun pour les README d’app : docs/standards/app-readme-template.md.
2. Chaque README d’app doit contenir :
- objectif
- statut de maturité
- fonctionnalités
- port
- prérequis
- démarrage Windows
- démarrage Unix
- démarrage frontend dev
- mode d’interface servi
- persistance
- configuration LLM
- tests
- limites
- écarts au standard
- références techniques
3. Ordre recommandé pour la normalisation :
- _template
- ocr-vision
- doc-writer
- doc-reviewer
- s1000d-extractor
- catia-toolbox
- corpus-agent
4. Les README backend restent centrés sur l’architecture propre à chaque app. Les règles communes restent dans STANDARD_POC.md ou docs/standards/.


Phase 6 — Nettoyage documentaire du legacy FTM

1. Vérifier le statut Git de ftm-v1.
2. Vérifier l’existence d’un tag, commit ou branche de restauration.
3. Supprimer uniquement le legacy FTM documenté comme obsolète, après validation du périmètre.
4. Nettoyer les références fausses dans les docs et les scripts uniquement si elles ne protègent plus de fichier utile.
5. Archiver ou reformuler les docs historiques sans supprimer leur contexte utile (ex: SESSION_SUMMARY.md, ANALISIS_TECNICO_EJECUTIVO.md).
6. Garder corpus-agent hors de cette série. Tout renommage de code lié à FTM est reporté à une PR code séparée.


Phase 7 — Workflow Git et PR

1. Documenter dans CONTRIBUTING.md :
- ne pas travailler directement sur main sauf décision explicite
- feature/<name> pour une fonctionnalité
- fixing/<name> pour un correctif
- une seule tâche cohérente par branche
- une PR par fix ou feature
- créer une branche dépendante depuis la branche courante associée à la PR parente encore ouverte
- après le merge de la PR parente, fusionner origin/main dans la branche dépendante et vérifier/résoudre les conflits
- valider le merge, puis pousser la branche dépendante
- exécuter les validations avant chaque push ou ouverture de PR
2. Mettre à jour :
- README.md
- CLAUDE.md
- STANDARD_POC.md
- PROMPT_AUDIT_STANDARD.md
- Agents.md
- AACF_TESTING_GUIDE.md
- guides historiques et ADR
3. Garder les commits séparés par livrable.
4. Clarifier la distinction entre normes et outils de validation : les guides de test comme AACF_TESTING_GUIDE.md sont destinés à la validation opérationnelle, pas à la définition normative du standard.


Découpage des commits recommandé

- docs: define repository documentation hierarchy
- docs: add documentation index and application inventory
- docs: define portable skill format
- feat: add onboarding and audit skills
- feat: add validation and AACF compliance skills
- feat: add controlled workflow skills
- docs: normalize application onboarding documentation
- docs: document git and pull request workflow
- chore: remove obsolete ftm legacy files


Dépendances entre phases

- Phase 0 → bloque toutes les autres phases.
- Phases 1 et 2 → peuvent avancer en parallèle après la baseline.
- Phase 3 (skills read-only) → doit précéder la Phase 4 (skills mutantes).
- Phase 5 → dépend du template README (Phase 1).
- Phase 6 → dépend de l’inventaire des références (Phase 0) et de la vérification Git.
- Phase 7 → peut être livrée indépendamment.


Vérifications de fin de phase

1. Vérifier les frontmatters YAML de chaque skill.
2. Vérifier que le nom du dossier de chaque skill correspond au name déclaré.
3. Vérifier les liens et chemins vers les apps.
4. Vérifier l’absence de secrets et de chemins personnels.
5. Tester les skills read-only sur _template et ocr-vision.
6. Vérifier que les skills ne lisent jamais :
- backend/data
- storage
- bases
- uploads
7. Vérifier la cohérence entre l’adaptateur AACF (aacf-compliance.agent.md) et la skill AACF portable.
8. Exécuter bash scripts/check_standard.sh quand pertinent.
9. Vérifier l’état Git et les commits avant push.


Exclusions strictes
Cette phase ne modifie pas :

- le code métier
- les migrations
- les launchers
- les scripts de packaging
- les UI / design-tokens
- les ports
- la CI
- les bases
- les uploads
- les données utilisateur
- l’historique Git


Conclusion

- Les skills sont la vraie source de vérité.
- Les agents ne sont que des wrappers de compatibilité.
- AACF est prioritaire sur STANDARD_POC.
- STANDARD_POC reste le cadre local du repo, sans usurper le rôle d’AACF.
- La skill aacf-compliance reste centrée sur l’AACF externe, sans être confondue avec le standard repo.
- La skill audit-standard reste le cœur de la conformité locale et s’appuie explicitement sur PROMPT_AUDIT_STANDARD.md comme format de rapport.
- Les guides de test comme AACF_TESTING_GUIDE.md restent des outils de validation opérationnelle, pas des sources normatives.
- Structure simple, portable, cohérente et compatible avec plusieurs harness.
