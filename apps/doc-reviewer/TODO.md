FRONT :



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


21-33-13 : 
JUL 30/26
JUL 30/73
AUG 30/75
05
33140-02

79-30-02:
JUL 27/26
JUL 66
01
1-879-SB



- Ajouter Uun onglet avec la liste des rejets (si pas de rejets mettre au mileu "Aucun rejet"). Il faut que ce soit organisé par documents et qu'on puisse plier ou déplier les rejets des documents. Et faire en sorte que sur le dashboard la box "Corrections rejetées" devienne un cliquable et ça redirige vers l'onglet des rejets
Mais ducoup il faut vérifier si dans la DB y'a les rejets stockés ou non et si oui il faut que ce soit pas une table en plus evidemment 
