- 1.2 - comparaison : Avant après sur les old P/N --> il faudrait OLD P/N (vinitial) OLD P/N (vfinal) / Pas faire apparaitre les colonnes new P/N

- Il faut analyser 2 fichiers en 1. pour pouvoir faire une comparaison en 1.2, pas très pratique, ça serait bien de pouvoir directement comparer avec 2 fichiers

- Faire un outil permettant de comparer de dossier de pieces catia avec la taille des fichiers
Sortir (on s'en occupe pas) tous les fichiers avec même noms et même taille et faire apparaitre les fichiers qui restes, et afficher ceux 
--> But faire ressortir les pièces qui ont changés de taille (et peut etre de nom mais faut capter que c'est la même piece)

- SMGXML color + colorisation des pièces mono-corps (pareil donc regrouper sous un seul onglet) : Recup le nom du profil et le coller à un endroit du code XML de la piece 
SIN d'une piece mono corps, ça fait le lien avec la nomenclature (lien nomenclature + fichier de liens + dossier avec les pieces). Une fois qu'on a le SIN mono corps récupérer dans la nomenclature le code de la couleur à prendre et on cherche le bon XML du SIN et on met au bon endroit. 

- Arbo + optimisation + Export plan : bonne arborescence mais ça va pas tout en bas --> on s'en fou de la voir enfait l'arbo donc on enlève !
Le but de ça c'est que t'as des lignes inutiles (on garde la derniere balise (exemple clitassygroup on garde celui le plus indenté à l'intérieur))
Slide 39

- SMGXML renommage : Code XML du Sin tu fais appel à ta Part (représenté par le P/N) , ya une variable qui appel la part --> Dans le code XML du SIN remplacer tous les noms avec les nouveau P/N. Sur la V0 on rajoute les pièces de la v1 donc la v0 devient au final la v1. Slide 56 --> 63 du PPT de Paul ? 

- C'est quoi la diff entre "1919 mono-corps" et "0 mono" dans la liste des nomenclatures analysées

