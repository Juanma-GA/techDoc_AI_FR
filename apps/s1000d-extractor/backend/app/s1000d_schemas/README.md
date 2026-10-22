# Schémas XSD S1000D

Les schémas disponibles sont chargés automatiquement par version depuis ce
dossier. Chaque version doit conserver tous ses fichiers XSD et leurs
dépendances dans son propre sous-dossier :

- `issue-4.1/` (validation `descript`, `proced` et `ipd` 4.1)
- `issue-4.2/` (validation `descript`, `proced` et `ipd` 4.2)
- `issue-5.0/` (répertoire réservé à l’Issue 5.0)

Le moteur choisit le XSD correspondant à l’issue et au type du DM. Pour la
génération 4.1/4.2, [`app/core/xsd_model.py`](../core/xsd_model.py) lit les
particules, occurrences, attributs requis et facettes des XSD locaux; le
sérialiseur métier reste explicite et n’est pas généré automatiquement. Les
éléments sont ordonnés et contraints avant l’écriture, puis le document final
est validé avec le même XSD.

La génération est limitée aux issues 4.1 et 4.2 et aux types descriptive,
procedural et IPD dont le XSD local existe. L’Issue 5.0 n’est pas une cible de
génération. Les valeurs obligatoires absentes reçoivent seulement des valeurs
provisoires acceptées par le XSD et apparaissent dans la liste des champs à
confirmer. Les structures source sans correspondance sont omises et signalées
dans les violations XSD/mapping; les erreurs et les champs métier restent deux
listes distinctes. Ces diagnostics ne bloquent pas les téléchargements XML ou
ZIP. Les prérequis procéduraux réellement absents sont représentés par les
éléments `no*` prévus par le XSD et ne produisent pas d’avertissement.

Si le dossier d’une version est vide ou absent,
[`app/core/s1000d_schema.py`](../core/s1000d_schema.py) signale la validation
XSD comme « non installée » (dégradation gracieuse). La validation **BREX**
reste active indépendamment.