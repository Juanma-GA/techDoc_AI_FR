FRONT :

- Dans l'onglet "règles" il faut pas que quand on desactive ou active ça mette en bas la regle, faut qu'elle reste au meme endroit juste on voit que c'est désactivé quoi aussi simple que ça

BACK :

- execution "manual" pas relié jusqu'au user
- L’exécution sémantique n’est pas intégrée au contrat CompiledRule --> divergence entre le modèle conceptuel et l’implémentation réelle; donc rajouter la possibilité de semantic qui sera un appel LLM en fonction du besoin semantique
- Implémenter le PDF vers DOCX dans les exports possibles

OTHER :

- Mettre les tests aussi dans le dossier client ? Pas tous, mais ceux spécifiques aux regles et operators specifique au client

- Attention si il faut mapper tous les PNR ça va faire bcp si y'en a plein dans le doc (des docs avec plusieurs PNR ??) --> Racine + 
--> une règle différente pour la page TP1 avec toutes les PNR et une pour les en-tetes Racines series

- Ajouter l'ancienne version en input pour qu'il puisse detecter et comparer la LEP pour etre sur des R U N D

- Vérifier que 250ms pour le regex suffit

- Installer libre office (ou word je sais plus) pour la conversion en .docx ou .doc et la tester 

- Faire une détection par exemple si le numéro CMM est noté 90% du temps X alors dire que le mapping n'est pas bon et il faut le vérifier et relancer l'analyse

- Pourquoi ça met bcp de temps l'analyse avant de tout afficher ? ça passe de 5% à 100% direct apres 20 secondes au lieu d'analyser petit à petit et d'afficher le poucentage en meme temps

PROBLEMES REGLES : 

- Custom Revision Page Not In Lep : Page du document absente de la liste des pages effectives Page 801
--> Pourquoi pour cette erreur il met une box en page 1 sur le logo et pas au niveau de la LEP. Et surtout pourquoi il détecte cette erreur alors qu'il y a bien la page 801 dans le LEP et existe bien dans le document...

- Custom Paragraph Justification : Il detecte actuellement des pb de justification sur "une seule ligne" est ce que c'est possible ça ? Si non, faire en sorte qu'il faut minimum 2 lignes à de

- Custom Storage Note Page 10 : Règle non satisfaite : L'introduction ou les catégories NOTE de la page STORAGE sont absentes ou incorrectes. Élément attendu: "Pressure:" --> c'est pas la bonne page... il lis "STORAGE" sauf que ce n'est pas la page STORAGE, le pied de page est bien LEP PAge 2 et le titre de la page c'est "List of effective pages" souligné donc il devrait pas détecter que la page est STORAGE

- Custom Introduction Shop Verification p.17 --> il dit qu'il manque le "Shop Verification: A. Verification of the procedures in this manual (1) The shop verification will be done at the first repair of the equipment." Alors qu'il y a bien écrit "Shop Verification 
A. 
Verification of the procedures in this manual 
(1) 
The shop verification will be done at the first repair of the 
equipment." 
Peut être pas les mêmes espaces et tout mais y'a bien écrit ce qu'il faut !

- 
