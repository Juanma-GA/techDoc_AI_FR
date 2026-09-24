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

- Enfait j'aimerais bien faire en sorte d'avoir un seul dossier de fichiers personnalisés pour le client, par exemple ici c'est THALES pour l'instant, dans le dossier @file:checks , avoir un dossier "thales_rules" et dedans tous les fichiers persos à la règle necessaires qu'il faut pour le bon fonctionnement des règles. 
Actuellement, ça modifie pleins de fichiers coeurs du programme mais qui ducoup ne rend pas du tout le tout personnalisable si un jour on veut ajouter des clients etc... Pareil pour le mapping, il faut que ça parte d'un fichier type dans ce dossier client; J'avais noté pendant une modif : "Attention y'a plein de fichiers modifié pour changer le mapping en dehors de user_rules(analyze; document_context; documents; compiled_rule_operators/runtime;compiled_rules;rules_engine;models;schémas; domaisns.ts;usedocuments.ts;DocumentMetaPanel.tsx; et les en.json et fr.json) mais l'objectif c'est qu'on puisse facilement modifier en fonction du client donc avoir des mapping différents. il faudrait donc regrouper ça dans un fichier spécifique au client et que tous les fichiers cités soient eux généraux et récupère en fonction du client. Pareil pour la règle des fareneit y'a eu une modif dans compiled_rule_suggestion qui doit plutot être dans un fichier unique au client (maybe c'est tout ce fichier enfait suggestion qui est unique au client)" 
Je pense que pour que ça fonctionne il faudrait aussi revoir le coeur pour qu'il soit parametrable et utilisable en fonction des fonctions et trucs des fichiers clients. Pour ça il faut définir les fichiers clients, leur formes et utilité, avec un des templates par exemple. Du coté client j'imagine : un fichier pour le mapping (en json ou xml ou simple juste définir les inputs et leurs types), un fichiers avec les operations et tout les calculs typiques aux règles clients, un fichier qui liste les règle (comme thales_custom actuelement), un fichier avec toute la metadata et traduction des règles. Et de l'autre coté il faut que le coeur du moteur puisse fonctionner avec ces fichiers là. 
Qu'est ce que t'en penses et comment tu t'y prendrais ? 
--> Commit avant de faire cette modif : (September 23, 2026 at 3:22 PM) : plan rebuild generalisation catalogue de règles f163bc6b2d1312eb1244dbf20c8f58f6e3bef12f

- Mettre les tests aussi dans le dossier client ? Pas tous, mais ceux spécifiques aux regles et operators specifique au client


- Attention si il faut mapper tous les PNR ça va faire bcp si y'en a plein dans le doc (des docs avec plusieurs PNR ??) --> Racine + 
--> une règle différente pour la page TP1 avec toutes les PNR et une pour les en-tetes Racines series