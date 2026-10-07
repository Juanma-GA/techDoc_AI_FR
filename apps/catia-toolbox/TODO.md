- Y'a un problème de fonctionnement pour dans la nomenclature puis analyse mono-corps car les résultats de l'analyse  mono-corps dépend des choix des colonnes de l'analyse de base, il faudrait tout détecter automatiquement dans l'analyse de base déjà, sinon ça fausse un peut tout

- Faire apparaitre Old P/N dans l'analyse des mono-corps 

- Faire un outil permettant de comparer de dossier de pieces catia avec la taille des fichiers
Sortir (on s'en occupe pas) tous les fichiers avec même noms et même taille et faire apparaitre les fichiers qui restes, et afficher ceux 
--> But faire ressortir les pièces qui ont changés de taille (et peut etre de nom mais faut capter que c'est la même piece)

- SMGXML color + colorisation des pièces mono-corps (pareil donc regrouper sous un seul onglet) : Recup le nom du profil et le coller à un endroit du code XML de la piece 
SIN d'une piece mono corps, ça fait le lien avec la nomenclature (lien nomenclature + fichier de liens + dossier avec les pieces). Une fois qu'on a le SIN mono corps récupérer dans la nomenclature le code de la couleur à prendre et on cherche le bon XML du SIN et on met au bon endroit. 

- Optimisation arbo (à reprendre après spécification, slide 39) : certaines balises intermédiaires de l'arbre XML sont inutiles ; conserver la dernière balise, la plus indentée (ex. ClitAssyGroup).

- SMGXML renommage : Code XML du Sin tu fais appel à ta Part (représenté par le P/N) , ya une variable qui appel la part --> Dans le code XML du SIN remplacer tous les noms avec les nouveau P/N. Sur la V0 on rajoute les pièces de la v1 donc la v0 devient au final la v1. Slide 56 --> 63 du PPT de Paul ?
