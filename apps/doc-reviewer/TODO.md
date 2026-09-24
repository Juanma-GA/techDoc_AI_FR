FRONT :

- Trop d'infos sur les input dans les paramètre pour la checklist
- DocumentReviewer.tsx utilise encore des caractères Unicode ◀ et ▶, en contradiction avec la règle locale interdisant les icônes Unicode.


BACK :

- execution "manual" pas relié jusqu'au user
- L’exécution sémantique n’est pas intégrée au contrat CompiledRule --> divergence entre le modèle conceptuel et l’implémentation réelle; donc rajouter la possibilité de semantic qui sera un appel LLM en fonction du besoin semantique
- Implémenter le PDF vers DOCX dans les exports possibles
- La suppression de la regle checklist ne la supprime pas elle la rend juste pas active

OTHER :

- Faire un préprocess avant les règles pour déterminer avant l'analyse les pages modifiées et celles non modifiées, ensuite l'analyse se fait que sur les pages modifiées. Les pages modifiées on les connait avec la cohérence entre HIGHLIGHTS , LEP et les date de revisions de bas de page. On garde celle avec un doute. 

- Mettre les tests aussi dans le dossier client ? Pas tous, mais ceux spécifiques aux regles et operators specifique au client


- Attention si il faut mapper tous les PNR ça va faire bcp si y'en a plein dans le doc (des docs avec plusieurs PNR ??) --> Racine + 
--> une règle différente pour la page TP1 avec toutes les PNR et une pour les en-tetes Racines series