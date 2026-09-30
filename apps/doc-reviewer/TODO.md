FRONT :

- DocumentReviewer.tsx utilise encore des caractères Unicode ◀ et ▶, en contradiction avec la règle locale interdisant les icônes Unicode.

BACK :

- execution "manual" pas relié jusqu'au user
- L’exécution sémantique n’est pas intégrée au contrat CompiledRule --> divergence entre le modèle conceptuel et l’implémentation réelle; donc rajouter la possibilité de semantic qui sera un appel LLM en fonction du besoin semantique
- Implémenter le PDF vers DOCX dans les exports possibles
- La suppression de la regle checklist ne la supprime pas elle la rend juste pas active

OTHER :

- Mettre les tests aussi dans le dossier client ? Pas tous, mais ceux spécifiques aux regles et operators specifique au client

- Attention si il faut mapper tous les PNR ça va faire bcp si y'en a plein dans le doc (des docs avec plusieurs PNR ??) --> Racine + 
--> une règle différente pour la page TP1 avec toutes les PNR et une pour les en-tetes Racines series

- Ajouter l'ancienne version en input pour qu'il puisse detecter et comparer la LEP pour etre sur des R U N D

PROBLEMES REGLES : 

- CUSTOM_HIGHLIGHTS_PAGE_LABEL_FORMAT : Je comprend pas pourquoi dans "Page  1001" il détecte qu'il manque un espace alors que y'a bien les 2...
Il peut y avoir des pages sur plusieurs page "1101-1 to 1101-2" qui correspondent enfait à 1101 Page 1 et 1102 Page 2 attention dans Highlights et LEP mais ducoup le tiret correspond pas à plusieurs pas : quand y'a juste marqué "Page  1101-1" c'est bien une seule page

- CUSTOM_HIGHLIGHTS_PAGE_PAIRING : Pourquoi il detecte ici Page Highlights déclarée sans sa page paire ou impaire associée : INTRO 1101 Page 3 to INTRO Page 4

- 