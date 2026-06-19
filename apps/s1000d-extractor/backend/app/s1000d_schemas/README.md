# Schémas XSD S1000D (non redistribués)

Les jeux de schémas officiels S1000D sont volumineux et ne sont pas committés
dans ce repo. Pour activer la **validation XSD réelle** de la sortie :

1. Récupère les schémas officiels de l'Issue voulue sur
   [users.s1000d.org](https://users.s1000d.org/) (téléchargement gratuit).
2. Dépose les `.xsd` dans :
   - `issue-4.2/`  (pour la version 4.2)
   - `issue-5.0/`  (pour la version 5.0)

Sans ces fichiers, [`app/core/s1000d_schema.py`](../core/s1000d_schema.py)
signale la validation XSD comme « non installée » (dégradation gracieuse) et
s'appuie sur le vocabulaire d'éléments interne. La validation **BREX** reste
active indépendamment.