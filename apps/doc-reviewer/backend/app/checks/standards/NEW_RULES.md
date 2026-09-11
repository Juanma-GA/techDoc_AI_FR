Pour ajouter une autre entreprise demain
cp -r app/checks/standards/user_rules.py app/checks/standards/<autre_entreprise>.py, adapter STANDARD_CODE/règles.
L'ajouter à BUILTIN_STANDARDS (catalogue de règles — déjà le pattern existant).
Si ce standard a aussi besoin de classifier des pages : ajouter une entrée dans PAGE_CLASSIFIERS.
Aucune modification d'analyze.py, rules_engine.py ou de l'exécuteur requise.