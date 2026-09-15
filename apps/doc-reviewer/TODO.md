FRONT :

- Trop d'infos sur les input dans les paramètre pour la checklist
- DocumentReviewer.tsx utilise encore des caractères Unicode ◀ et ▶, en contradiction avec la règle locale interdisant les icônes Unicode.
- Ajouter un bouton pour supprimer toutes les règles non compilées si il y en a
Détecter les colonnes auto uniquement, on fera en sorte que les colonnes excel suivantes : topic / rules 
Peut etre même sup tout la partie review du tableau pas forcément utile, juste on importe la checklist et hop ça part
- Quand il y a plusieurs occurences il ne faut pas que quand on déplie ça déroule direct jusqu'en pas des X occurences / actuellement ça bug quand on est sur une des occurence on ne peut pas replier, faut changer ça pour qu'on puisse replier meme si on est sur une des occurences / Le bouton "corriger les X occurences" ne doit pas apparaitre sur chaque X occurence mais sur le truc de base là où on plis déplis


BACK :

- execution "manual" pas relié jusqu'au user
- L’exécution sémantique n’est pas intégrée au contrat CompiledRule --> divergence entre le modèle conceptuel et l’implémentation réelle; donc rajouter la possibilité de semantic qui sera un appel LLM en fonction du besoin semantique
- Implémenter le PDF vers DOCX dans les exports possibles
- La suppression de la regle checklist ne la supprime pas elle la rend juste pas active


OTHER :

- Résoudre les fails ds tests

JUL 27/26
79-30-02
JUL 1966
Rev. 01
1-879-SB

Attention y'a plein de fichiers modifié pour changer le mapping en dehors de user_rules(analyze; document_context; documents; compiled_rule_operators/runtime;compiled_rules;rules_engine;models;schémas; domaisns.ts;usedocuments.ts;DocumentMetaPanel.tsx; et les en.json et fr.json) mais l'objectif c'est qu'on puisse facilement modifier en fonction du client donc avoir des mapping différents. il faudrait donc regrouper ça dans un fichier spécifique au client et que tous les fichiers cités soient eux généraux et récupère en fonction du client

Erreur de PNR dans la premiere page au milieu 

Page dans les Highlight marqué par un R LEP ... 
--> Cohérence des 3 pages bien intégré dans la LEP dans la U R etc

Highlight et LEP précises quelles pages ont été modifiées ou non 
Dans la LEP les * = modifiées et la date doit aussi etre modifiée ducoup
Dans Highlights les pairs doivent etre tjrs précédées d'une impaire

R revisé 
N new
U unchanged 

Highlights si pas de 's' 2 espaces pour ettre aligné avec 

Higltght + LEP + pied de page 

Pied de page : Il faudra vérifier les pieds de pages seulements des pages mentionnées en LEP/Highlights des pages modifiées, vérifier donc que la date est bien  la bonne et dasn l'autre sens vérifier toutes les autres pour savoir si la date est bien celle de derniere révision ou premiere issue, et sinon alors la flag et vérifier peut etre qu'elle manque au LEP et HIGHLIGHTS. 

60/62/67



