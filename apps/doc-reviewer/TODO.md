FRONT :

- Trop d'infos sur les input dans les paramètre pour la checklist
- DocumentReviewer.tsx utilise encore des caractères Unicode ◀ et ▶, en contradiction avec la règle locale interdisant les icônes Unicode.
- Ajouter un bouton pour supprimer toutes les règles non compilées si il y en a
- Détecter les colonnes auto uniquement, on fera en sorte que les colonnes excel suivantes : topic / rules 
- Peut etre même sup tout la partie review du tableau pas forcément utile, juste on importe la checklist et hop ça part


BACK :

- execution "manual" pas relié jusqu'au user
- L’exécution sémantique n’est pas intégrée au contrat CompiledRule --> divergence entre le modèle conceptuel et l’implémentation réelle; donc rajouter la possibilité de semantic qui sera un appel LLM en fonction du besoin semantique
- Implémenter le PDF vers DOCX dans les exports possibles
- La suppression de la regle checklist ne la supprime pas elle la rend juste pas active


OTHER :

- Faire un préprocess avant les règles pour déterminer avant l'analyse les pages modifiées et celles non modifiées, ensuite l'analyse se fait que sur les pages modifiées. Les pages modifiées on les connait avec la cohérence entre HIGHLIGHTS , LEP et les date de revisions de bas de page. On garde celle avec un doute. 

- Attention y'a plein de fichiers modifié pour changer le mapping en dehors de user_rules(analyze; document_context; documents; compiled_rule_operators/runtime;compiled_rules;rules_engine;models;schémas; domaisns.ts;usedocuments.ts;DocumentMetaPanel.tsx; et les en.json et fr.json) mais l'objectif c'est qu'on puisse facilement modifier en fonction du client donc avoir des mapping différents. il faudrait donc regrouper ça dans un fichier spécifique au client et que tous les fichiers cités soient eux généraux et récupère en fonction du client. PAreil pour la règle des fareneit y'a eu une modif dans compiled_rule_suggestion qui doit plutot être dans un fichier unique au client (maybe c'est tout ce fichier enfait suggestion qui est unique au client)  

- Attention si il faut mapper tous les PNR ça va faire bcp si y'en a plein dans le doc (des docs avec plusieurs PNR ??) --> Racine + 
--> une règle différente pour la page TP1 avec toutes les PNR et une pour les en-tetes Racines series