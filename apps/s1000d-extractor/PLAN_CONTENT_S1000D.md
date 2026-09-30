# Plan de generation du contenu S1000D

## 1. Objectif

Remplir correctement le `<content>` de chaque Data Module S1000D a partir d'un PDF ou d'un DOCX, en tenant compte du type de DM :

- DM descriptif ;
- DM procedural.

La generation doit produire le maximum de structure exploitable sans bloquer lorsqu'une information est absente ou ambigue.

## 2. Decisions validees

- Les onglets `Descript` et `Proced` de `Balise_S1000D.xlsx` servent de guide metier.
- Le classeur n'est pas une liste bloquante ni une grammaire XML complete.
- Les schemas et la norme S1000D officielle sont prioritaires pour verifier les relations parent/enfant et les attributs.
- Les informations manquantes ne doivent pas bloquer la generation.
- Une information manquante doit produire un commentaire XML `TODO` et une alerte de validation lisible.
- Les valeurs absentes ne doivent jamais etre inventees silencieusement.
- Le support IPD est reporte a une phase ulterieure.
- Les `Warning` et `Caution` doivent etre differencies semantiquement, pas uniquement selon le mot d'introduction. (on verra plus tard)
- Les references internes et externes doivent etre detectees et resolues autant que possible.
- Une cible non resolue doit etre signalee sans empecher la production du XML.

## 3. Perimetre de la premiere version

### Inclus

- contenu descriptif ;
- contenu procedural ;
- paragraphes et titres ;
- sections et sous-sections ;
- listes ;
- emphase ;
- figures et tableaux ;
- references internes vers une figure ou un tableau du meme DM ;
- references externes vers un autre DM S1000D ;
- DMC provenant de la DMRL ou explicitement trouve dans le texte ;
- attributs manquants signales par commentaires ;
- validation non bloquante et revue humaine dans le wizard.

### Reporte

- IPD / Illustrated Parts Data ;
- catalogue de pieces complet ;
- warnings, cautions et notes ;
- construction exhaustive de toutes les structures S1000D specialisees non presentes dans le besoin initial ;
- resolution parfaite des URLs ou publications externes non-S1000D ;
- remplissage automatique de donnees qui n'existent pas dans le document source.

## 4. Architecture actuelle a conserver comme base

Le flux existant est :

```text
PDF/DOCX
  -> extraction RawBlock
  -> construction de l'IR
  -> classification descriptive/procedural
  -> decoupage en DM
  -> resolution des candidats S1000D
  -> serialisation XML
  -> validation XSD/BREX
```

Modules principaux :

- `backend/app/core/ir.py` : modele intermediaire ;
- `backend/app/core/structure_infer.py` : construction de l'arbre ;
- `backend/app/core/context_classifier.py` : type et contexte ;
- `backend/app/core/resolver.py` : choix de candidats de balises ;
- `backend/app/core/s1000d_serializer.py` : generation XML ;
- `backend/app/core/splitter.py` : decoupage en DM ;
- `backend/app/core/wizard.py` : revue et generation DM par DM ;
- `backend/app/core/dmrl.py` : chargement de la DMRL et des DMC ;
- `backend/app/core/validator.py` : validation et violations.

## 5. Limites actuelles a traiter

1. Le resolver connait surtout les balises generiques : `para`, `levelledPara`, listes, `proceduralStep`, admonitions, figures et tableaux.
2. Les balises procedurales specialisees du classeur ne sont pas encore generees depuis le contenu source.
3. Les templates de rubriques produisent un rendu derive, mais ne pilotent pas encore directement le `<content>` XML final du wizard.
4. Le type manuel du DM doit devenir une contrainte forte pour la resolution des noeuds.
5. Les references internes sont detectees de facon partielle et recoivent encore des identifiants temporaires.
6. Les references vers un autre DM ne sont pas encore transformees en `dmRef`.
7. Les metadonnees de liens presentes dans les parseurs ne sont pas toujours conservees jusqu'a l'IR.
8. Le serializer ajoute parfois les references comme freres du `<para>` au lieu de les placer dans le contenu XML approprie.
9. Les valeurs `internalRefTargetType` doivent etre verifiees avec les schemas officiels ; les valeurs textuelles `figure` ou `table` ne doivent pas etre conservees sans verification.

## 6. Source des regles de balisage

### 6.1 Regles de priorite

1. Schema et norme S1000D officielle ;
2. profil du DM : `descriptive` ou `procedural` ;
3. guide metier `Balise_S1000D.xlsx` ;
4. heuristiques et classification du document source ;
5. choix humain dans le wizard.

Les listes de codes fournies pour cette implementation sont conservees dans
`backend/app/s1000d_codes.json` et chargees par
`backend/app/core/s1000d_codes.py`. Elles servent de registre de choix et de
mapping, mais leur conformite normative reste a verifier avec les references
officielles de l'Issue cible.

### 6.2 Normalisation du classeur

Ne pas utiliser directement les cellules Excel dans le serializer. Construire une representation normalisee contenant au minimum :

```text
nom de la balise
profil de DM
role metier
parents autorises
enfants autorises
attributs obligatoires
attributs optionnels
exemple XML
description
niveau de confiance ou statut de verification
```

Les cellules composites doivent etre decomposees :

- `warning` + `warningAndCautionPara` ;
- `caution` + `warningAndCautionPara` ;
- `note` + `notePara` ;
- `figure` + `graphic` ;
- `dmRef` + `dmRefIdent` + `dmCode` ;
- `table` + `row` + `entry` ;
- `emphasis` avec `emphasisType`.

Le fichier Excel original reste un guide metier. Les descriptions ambiguës ou incompletes doivent produire une alerte de configuration, pas une correction silencieuse du fichier source.

### 6.3 Profil descriptif

Structure cible generale a verifier avec le schema officiel :

```text
content
  description
    levelledPara
      title
      para
      randomList / sequentialList
      warning / caution / note
      figure / graphic
      table
      internalRef
      dmRef
      symbol
```

Balises communes identifiees dans l'onglet `Descript` :

- `title` ;
- `para` ;
- `levelledPara` ;
- `randomList` ;
- `listItem` ;
- `warning` / `caution` / `note` ;
- `emphasis` `em01` / `em02` ;
- `figure` / `graphic` ;
- `internalRef` ;
- `dmRef` / `dmRefIdent` / `dmCode` ;
- `symbol` ;
- `table` / `col` / `row` / `entry`.

### 6.4 Profil procedural

Structure cible generale a verifier avec le schema officiel :

```text
content
  procedure
    preliminaryRqmts
      productionMaintData
      thresholdInterval
      taskDuration
      reqCondGroup
      reqPersons
      reqSupportEquips
      reqSupplies
      reqSpares
      reqSafety
    mainProcedure
      proceduralStep
    closeRqmts
```

Le profil procedural reprend aussi les elements communs necessaires :

- paragraphes ;
- listes ;
- warnings, cautions et notes ;
- figures ;
- tableaux ;
- references internes ;
- references vers d'autres DM.

Les balises `preliminaryRqmts`, `mainProcedure` et `closeRqmts` doivent etre generees comme conteneurs de leur zone fonctionnelle, meme si certaines donnees sont absentes. Dans ce cas, un commentaire `TODO` doit expliquer ce qui manque.

## 7. Enrichissement de l'IR

L'IR doit rester independant du XML, mais porter assez d'information pour permettre une generation controlee.

### 7.1 Role metier

Ajouter ou calculer un role metier pour les sections et blocs, par exemple :

- `introduction` ;
- `description` ;
- `operation` ;
- `characteristics` ;
- `preliminary_requirements` ;
- `required_conditions` ;
- `required_personnel` ;
- `support_equipment` ;
- `supplies` ;
- `spare_parts` ;
- `safety_requirements` ;
- `procedure_step` ;
- `closing_requirements`.

La determination combine titre, position dans le DM, forme du contenu, type du DM et eventuellement LLM. Le serializer ne doit pas demander au LLM de produire directement du XML.

### 7.2 Admonitions

Le noeud doit conserver :

```text
kind: warning | caution | note
confidence
rationale ou signaux detectes
```

La distinction doit suivre ces priorites :

1. danger pour une personne : `warning` ;
2. dommage ou dysfonctionnement materiel : `caution` ;
3. information sans danger : `note` ;
4. marqueur explicite coherent avec le contenu ;
5. cas contradictoire ou ambigu : choix prudent + commentaire de verification.

Signaux `warning` : blessure, brulure, electrocution, intoxication, exposition, mort, danger pour l'operateur.

Signaux `caution` : endommagement, casse, corrosion, surtension, mauvais fonctionnement, perte de reglage, deterioration d'un composant.

Si un texte contient un danger humain et un danger materiel, `warning` est prioritaire et un commentaire peut signaler la double consequence.

Les deux structures utilisent le contenu enfant `warningAndCautionPara` :

```xml
<warning>
  <warningAndCautionPara>Danger pour une personne.</warningAndCautionPara>
</warning>
```

```xml
<caution>
  <warningAndCautionPara>Risque de deterioration du materiel.</warningAndCautionPara>
</caution>
```

### 7.3 References

Le champ actuel `refs` doit devenir une structure suffisamment riche pour contenir :

```text
kind: internal | dm | uri | unresolved
target_kind: figure | table | dm
target_label
source_text
target_dmc
target_dm_id
confidence
resolution_status
```

Conserver les metadonnees de liens provenant des parseurs, en plus des references detectees dans le texte.

## 8. References internes

### 8.1 Cas couverts

- `Voir figure 3.`
- `Voir figure 6.1.`
- `Se reporter au tableau 2.`
- `Voir le tableau suivant.` lorsque la cible peut etre determinee de facon fiable.

### 8.2 Resolution

Construire une table d'ancres pour chaque DM :

```text
label source       -> identifiant XML final
figure 3           -> fig-....
tableau 2          -> tbl-....
```

La resolution doit utiliser le numero ou libelle de la source et non uniquement le compteur interne du serializer.

Le resultat attendu est un `internalRef` dont :

- `internalRefId` pointe vers l'id reel de la figure ou du tableau ;
- `internalRefTargetType` utilise la valeur conforme a la norme ;
- la reference est placee dans une position XML valide, idealement dans le `para` concerne.

Si la cible est absente ou non unique :

- conserver le texte d'origine ;
- ajouter un commentaire XML `TODO` ;
- ajouter une violation de niveau `warning` ;
- ne pas bloquer la generation.

## 9. References externes vers un autre DM

### 9.1 Source du DMC

Priorite de resolution :

1. DMC explicite dans le texte ou le lien ;
2. correspondance avec un titre de la DMRL ;
3. correspondance avec un alias ou une arborescence connue ;
4. reference non resolue avec commentaire.

La DMRL doit fournir un catalogue global de references :

```text
dm_id
titre
DMC
type
alias
```

Le serializer d'un DM doit recevoir ce catalogue, et pas uniquement les metadonnees du DM courant.

### 9.2 Generation

Pour un DM cible connu, produire :

```xml
<dmRef>
  <dmRefIdent>
    <dmCode ... />
  </dmRefIdent>
</dmRef>
```

Le parsing des DMC existant dans `core/pmc.py` doit etre reutilise pour remplir les attributs de `dmCode`.

Pour un DMC non standard :

- conserver la valeur brute ;
- ajouter un commentaire `TODO` indiquant que le DMC doit etre verifie ;
- ne pas interrompre la generation.

Un lien HTTP ou une publication externe non-S1000D ne doit pas etre force en `dmRef` sans DMC. Il doit rester identifie comme lien externe a traiter selon une regle distincte.

## 10. Donnees obligatoires manquantes

Regle generale : produire, signaler, ne pas bloquer.

Exemple de commentaire :

```xml
<!-- TODO: verifier l'attribut unitOfMeasure requis pour reqQuantity -->
```

Pour une rubrique procedural vide :

```xml
<!-- TODO: aucune condition prealable detectee dans le document source -->
<reqCondGroup />
```

Chaque manque doit pouvoir apparaitre dans :

- le XML sous forme de commentaire ;
- la liste des violations du DM ;
- l'etape `generate` du wizard.

Les violations de contenu manquant sont des `warning`, sauf erreur XML ou regle bloquante explicitement definie plus tard par le client.

## 11. Plan d'implementation

### Phase 0 - Verifier la reference S1000D

- [ ] Recuperer les schemas officiels des Issues supportees.
- [ ] Verifier les relations parent/enfant des profils descriptif et procedural.
- [ ] Verifier les attributs obligatoires.
- [ ] Verifier les valeurs normalisees de `internalRefTargetType`.
- [ ] Verifier la structure exacte de `dmRef` et `dmCode`.
- [ ] Documenter les ecarts entre la norme, le classeur et le besoin metier.

### Phase 1 - Normaliser le guide metier

- [x] Lire les onglets `Descript` et `Proced`.
- [x] Decomposer les lignes composites.
- [x] Detecter les cellules incompletes ou ambigues.
- [x] Produire une representation interne versionnee.
- [x] Conserver un registre versionne des codes S1000D fournis.
- [ ] Marquer les balises non encore implementees.
- [x] Ajouter des tests de chargement et de normalisation.

Implementation initiale : `backend/app/core/s1000d_guide.py` charge le classeur
sans le modifier et produit des regles versionnees, avec les composants des
lignes composites, les attributs, les exemples et les alertes de configuration.
Les relations parent/enfant restent volontairement non renseignees tant
qu'elles ne sont pas verifiees avec les schemas officiels.

### Phase 2 - Enrichir l'IR et la classification

- [ ] Ajouter les roles metier des sections et blocs.
- [ ] Ajouter confiance et justification pour les classifications.
- [ ] Renforcer la detection `warning` / `caution` / `note`.
- [ ] Propager le type du DM a tous ses noeuds avant la resolution.
- [ ] Conserver les metadonnees de liens des parseurs.
- [ ] Ajouter les champs de resolution des references.

### Phase 3 - Resoudre les balises par profil

- [ ] Definir les candidats autorises pour `descriptive`.
- [ ] Definir les candidats autorises pour `procedural`.
- [ ] Definir les conteneurs proceduraux.
- [ ] Definir les regles parent/enfant.
- [ ] Conserver des candidats alternatifs pour la revue humaine.
- [ ] Ajouter des commentaires lorsque la resolution reste incertaine.

### Phase 4 - Implementer les references

- [ ] Construire les ancres figure/table de chaque DM.
- [ ] Resoudre les references internes vers des ids XML reels.
- [ ] Construire le catalogue global des DM et DMC.
- [ ] Resoudre les references externes vers la DMRL.
- [ ] Produire les `dmRef` complets.
- [ ] Ajouter le fallback non bloquant pour les cibles inconnues.
- [ ] Placer les references dans une position XML valide.

### Phase 5 - Revoir le serializer du `<content>`

- [x] Generer le squelette descriptif selon le profil descriptif pour le cas
  `TERMINOLOGIE` (page 5 de `WEG-WMO.pdf`).
- [ ] Generer `preliminaryRqmts`, `mainProcedure` et `closeRqmts` pour les procedures.
- [ ] Injecter les roles metier dans les bons conteneurs.
- [ ] Generer les attributs connus.
- [ ] Ajouter des commentaires pour les attributs absents.
- [ ] Ne jamais emettre de XML libre provenant directement du LLM.

### Phase 6 - Integrer le wizard

- [ ] Afficher le role metier et la balise retenue.
- [ ] Afficher les alertes `warning` / `caution` incertaines.
- [ ] Permettre la correction humaine d'une balise ou d'une cible.
- [ ] Afficher les references non resolues.
- [ ] Afficher les champs obligatoires manquants.
- [ ] Regenerer le XML sans perdre les corrections manuelles.

### Phase 7 - Validation et tests

- [x] Tester un DM descriptif simple sur la page 5 de `WEG-WMO.pdf`.
- [ ] Tester les DM proceduraux.
- [ ] Tester les warnings et cautions en francais et en anglais.
- [ ] Tester les textes ambigus.
- [ ] Tester les references figure/table.
- [ ] Tester les references par DMC explicite.
- [ ] Tester les references par titre DMRL.
- [ ] Tester les references non resolues.
- [ ] Tester les attributs manquants.
- [ ] Verifier que chaque cas produit un XML bien forme.
- [ ] Verifier que les alertes n'empechent pas le telechargement.

## 12. Criteres d'acceptation

### Content descriptif

- Un texte descriptif est genere en `description` avec les paragraphes et sections adaptes.
- Une liste a puces devient une liste descriptive.
- Une figure et un tableau peuvent etre references depuis le meme DM.
- Un danger humain devient un `warning`.
- Un risque materiel devient un `caution`.

### Content procedural

- Le DM contient `procedure`.
- Les exigences preliminaires sont placees dans `preliminaryRqmts` lorsqu'elles sont detectees.
- Les actions sont placees dans `mainProcedure` sous forme de `proceduralStep`.
- Les exigences de cloture sont placees dans `closeRqmts` lorsqu'elles sont detectees.
- Les informations absentes produisent des commentaires et des avertissements, sans blocage.

### References

- Une reference a une figure ou un tableau du meme DM produit un `internalRef` resolu.
- Une reference a un autre DM connu produit un `dmRef` contenant son DMC.
- Une cible inconnue reste visible dans le texte et produit un `TODO` explicite.
- Aucun `internalRef` ne pointe vers un identifiant invente ou non present dans le DM.

### Robustesse

- Le XML reste bien forme dans tous les cas.
- Les corrections humaines du wizard sont conservees.
- La validation explique les manques sans rendre le resultat inutilisable.
- La sortie IPD n'est pas enrichie dans cette premiere phase.

## 13. Points encore ouverts

- [ ] Choisir si le classeur est charge directement a l'execution ou converti en ressource normalisee versionnee.
- [ ] Valider les codes exacts de `internalRefTargetType` avec les schemas officiels.
- [ ] Definir la liste definitive des roles metier proceduraux.
- [ ] Definir le traitement des URLs et publications externes non-S1000D.
- [ ] Definir si un DM sans DMC peut tout de meme etre reference par titre.
- [ ] Definir les regles client supplementaires a appliquer via BREX.
- [ ] Definir le niveau de detail attendu pour les commentaires `TODO` dans l'interface.

## 14. Ordre recommande pour commencer

1. Verifier les schemas officiels et les codes de references.
2. Normaliser le classeur sans le modifier.
3. Corriger le modele IR pour porter roles, ancres et references.
4. Implementer d'abord un DM descriptif complet.
5. Implementer ensuite le squelette procedural et ses rubriques preliminaires.
6. Ajouter les references internes.
7. Ajouter les `dmRef` relies a la DMRL.
8. Terminer par l'interface de revue et les tests de non-blocage.
