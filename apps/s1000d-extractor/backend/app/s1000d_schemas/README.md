# Schémas XSD S1000D

Les schémas disponibles sont chargés automatiquement par version depuis ce
dossier. Chaque version doit conserver tous ses fichiers XSD et leurs
dépendances dans son propre sous-dossier :

- `issue-4.1/` (validation `descript` et `proced` 4.1)
- `issue-4.2/` (validation `descript` et `proced` 4.2)
- `issue-5.0/` (répertoire réservé à l’Issue 5.0)

Le moteur choisit `descript.xsd` ou `proced.xsd` selon le type du DM. Si le
dossier d’une version est vide ou absent, [`app/core/s1000d_schema.py`](../core/s1000d_schema.py)
signale la validation XSD comme « non installée » (dégradation gracieuse).
La validation **BREX** reste active indépendamment.