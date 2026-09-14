Pour ajouter une autre entreprise demain
cp -r app/checks/standards/thales_custom.py app/checks/standards/<autre_entreprise>_custom.py, adapter STANDARD_CODE/règles et STANDARD_SPEC.
Le module est découvert automatiquement via STANDARD_SPEC et rejoint le catalogue compilé.
Si ce standard a aussi besoin de classifier des pages : exposer une fonction classify_pages dans son module.
Aucune modification d'analyze.py, rules_engine.py ou de l'exécuteur requise.