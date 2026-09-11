FRONT :


- Est ce qu'on laisse le "Prompt IA Custom" (je pense pas)
- Trop d'infos sur les input dans les paramètre pour la checklist
- DocumentReviewer.tsx utilise encore des caractères Unicode ◀ et ▶, en contradiction avec la règle locale interdisant les icônes Unicode.
- Ajouter un bouton pour supprimer toutes les règles non compilées si il y en a
Détecter les colonnes auto uniquement, on fera en sorte que les colonnes excel suivantes : topic / rules 
Peut etre même sup tout la partie review du tableau pas forcément utile, juste on importe la checklist et hop ça part

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

- Rajouter point --> virgule