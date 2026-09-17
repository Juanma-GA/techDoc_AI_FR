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

- Attention y'a plein de fichiers modifié pour changer le mapping en dehors de user_rules(analyze; document_context; documents; compiled_rule_operators/runtime;compiled_rules;rules_engine;models;schémas; domaisns.ts;usedocuments.ts;DocumentMetaPanel.tsx; et les en.json et fr.json) mais l'objectif c'est qu'on puisse facilement modifier en fonction du client donc avoir des mapping différents. il faudrait donc regrouper ça dans un fichier spécifique au client et que tous les fichiers cités soient eux généraux et récupère en fonction du client. PAreil pour la règle des fareneit y'a eu une modif dans compiled_rule_suggestion qui doit plutot être dans un fichier unique au client (maybe c'est tout ce fichier enfait suggestion qui est unique au client)  

Il faut faire en sorte qu'au début on détecte les pages qui sont modifiées. Pour détecter cela il faut croiser plusieurs informations, de la page HIGHTLIGHTS + LEP.
Dans les pages Highlights il y a un tableau avec une liste de pages et si elles ont été R (révisées), N(new) ou U (unchanged).
Et dans les pages LEP il y a la liste de toutes les pages effectives (List Effective Pages), avec les dates et le sujet (attention c'est un tableau doublé, donc une ligne = 2 fois les 3 mêmes colonnes)

Highlight et LEP précises quelles pages ont été modifiées ou non 
Dans la LEP les * = modifiées et la date doit aussi etre modifiée ducoup --> Donc il faut vérifier pour chaque sujet : - la cohérence entre la date : si c'est la date de révision du mapping alors vérifier qu'elle est bien R ou N sur la page Hightlights + y'a une étoile après la date dans le LEP + que la page de la révision (ou nouvelle page) en elle même soit à la nouvelle date de revision. Et si y'a un des trois qui n'est pas bon alors il faut le flag au user.

Dans Highlights les pages pairs doivent toujours etre précédées d'une impaire

Highlights : page(s) si pas de 's' 2 espaces pour etre aligné avec

--> Higltght + LEP + pied de page

Pied de page : Il faudra vérifier les pieds de pages seulements des pages mentionnées en LEP/Highlights des pages modifiées, vérifier donc que la date est bien la bonne et dans l'autre sens vérifier toutes les autres pour savoir si la date est bien celle de derniere révision ou premiere issue, et sinon alors la flag et vérifier peut etre qu'elle manque au LEP et HIGHLIGHTS.


Le but est de détecter les pages modifiées avant de lancer les autres contrôles, en croisant trois sources :

1. Highlights

- R = page révisée
- N = nouvelle page
- U = page inchangée

2. LEP (List of Effective Pages)

- liste des pages effectives ;
- sujet associé ;
- date de révision ;
- "*" après la date si la page est modifiée ;
- attention : chaque ligne contient deux groupes de trois colonnes, qu’il faut donc traiter comme deux entrées distinctes.

3. Pied de page de la page

- date affichée sur la page elle-même.

Règle principale

Le mapping fournit deux dates :

- la **date de révision**, attendue pour les pages révisées (`R`) ou nouvelles (`N`) ;
- la **date de première issue**, attendue pour les pages qui n’ont jamais été révisées.

Pour chaque page et chaque sujet, les trois sources doivent être cohérentes :

| Statut dans Highlights | Date attendue dans le LEP | Étoile dans le LEP | Date du pied de page | Résultat attendu |
| --- | --- | --- | --- | --- |
| `R` - page révisée | Date de révision du mapping | Obligatoire | Date de révision | Cohérent |
| `N` - nouvelle page | Date de révision du mapping | Obligatoire | Date de révision | Cohérent |
| `U` - page inchangée, jamais révisée | Date de première issue du mapping | Absente | Date de première issue | Cohérent |
| `U` - page inchangée, déjà révisée | Dernière date de révision connue dans le LEP ou l’historique | Absente | Cette dernière date de révision | Cohérent |
| Toute autre combinaison | Date ou valeur incohérente | Étoile absente ou inattendue | Date incorrecte ou absente | À signaler |

Il faut donc signaler notamment :

- une page marquée R ou N dans Highlights mais sans * dans le LEP ;
- une page avec * dans le LEP mais marquée U dans Highlights ;
- une date LEP différente de la date de révision attendue ;
- une date de pied de page incorrecte ;
- une page qui porte la nouvelle date dans son pied de page mais qui n’est déclarée comme modifiée nulle part ;
- une page présente dans un document mais absente des Highlights ou du LEP.

Contrôles complémentaires

- Dans Highlights, une page paire doit être précédée par la page impaire correspondante. Par exemple, si la page 4 apparaît, la page 3 doit aussi être présente.
- Vérifier le formatage de page / pages et les espaces nécessaires à l’alignement. Parce que quand il y a plusieurs pages il fuat noté sous la forme "Pages 701 to 704" et quand il y a qu'un page : "Page  401".
- Pour les pages non modifiées, vérifier que le pied de page contient bien la dernière date de révision connue ou la date de première émission, et non la nouvelle date de révision.

Ordre de traitement envisagé

1. Récupérer les dates de révision attendues, probablement par sujet.
2. Extraire les statuts des Highlights.
3. Extraire et séparer les deux entrées de chaque ligne du LEP.
4. Comparer Highlights, LEP et pieds de page.
5. Produire une alerte précise avec le numéro de page, le sujet et la source incohérente.

Le contrôle consiste à comparer, pour chaque page et chaque sujet :

1. son statut dans Highlights ;
2. sa date et son étoile dans le LEP ;
3. sa date de pied de page ;
4. les dates fournies par le mapping.


Pour une page `U` déjà révisée, la dernière date de révision doit être récupérée dans le LEP ou l’historique du document. Elle ne doit pas être remplacée par la date de révision actuelle du mapping. --> ajouter dans le mapping une "date de derniere issue"
