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

-----

- CUSTOM_TITLE_PAGE_COPYRIGHT : ça ne doit pas être 1966 en dur mais l'année de date de premiere issue mise en mapping. En mapping on met par exemple JUL 30/73 il faut qu'il capte le 73 comme 1973 ! et si c'est inférieur à 50 c'est que c'est les années 2000 sinon c'est les années 1900

- CUSTOM_HIGHLIGHTS_PNR_HEADER : Vu que ça peut être une liste dans le mapping mais en en-tete c'est uniquement le premier de la liste, parce que ducoup la il vérifie "["33140-02"]" alors que j'ai juste mis "33140-02" en mapping mais il rajoute les guillemets et les crochets mais il faut pas 

- CUSTOM_HIGHLIGHTS_HOLDER : 
Il dit : Règle non satisfaite : La phrase TO: HOLDER OF des Highlights ne correspond pas au titre TP1. Le contenu doit commencer par : « TO: HOLDER OF RATE OF CLIMB INDICATOR ». alors que y'a bien écrit ce qu'il faut donc bizarre !

- CUSTOM_HIGHLIGHTS_DOCUMENT_TYPE : Accepter " with Illustrated Parts List" après le type

-----

- CUSTOM_HIGHLIGHTS_PAGE_LABEL_FORMAT : Je comprend pas pourquoi dans "Page  1001" il détecte qu'il manque un espace alors que y'a bien les 2...

- 