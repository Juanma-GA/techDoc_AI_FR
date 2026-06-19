"""Prompts LLM editables runtime (analyse + remplissage de templates PPTX).

Stockage dans la table `app_config` (key/value). Une valeur vide ou absente
ramene au defaut hardcode ci-dessous. Reset = ecrire chaine vide.

Les defauts sont la source de verite : tout changement de prompt devrait
d'abord etre teste en DB (via /api/v1/settings), et si concluant, retro-porte
dans `DEFAULTS` puis vide en DB.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AppConfig


# Map nom logique -> cle DB (prefixee pour ne pas collisionner avec les
# cles Mistral existantes type MISTRAL_API_KEY).
PROMPT_KEYS: dict[str, str] = {
    "pptx_analysis": "PROMPT_PPTX_ANALYSIS",
    "pptx_fill": "PROMPT_PPTX_FILL",
}


DEFAULTS: dict[str, str] = {
    "pptx_analysis": (
        "Tu analyses un template PowerPoint pour identifier les zones a "
        "remplir avec du contenu genere par un autre systeme.\n\n"
        "On te fournit un dump JSON du template : slides, shapes (text_box "
        "ou table avec rows et cells). Chaque shape/cellule a un `id` unique "
        "et un `text` qui contient son contenu actuel.\n\n"
        "CONVENTION D'ID (sers-t'en pour raisonner sur la POSITION, c'est ta "
        "seule source de geometrie, tu ne vois pas le template) :\n"
        "- Boite de texte : `s_<slide>_<shape>`.\n"
        "- Cellule de table : le meme prefixe suivi de `_r<ligne>_c<colonne>`, "
        "lignes et colonnes indexees a partir de 0. Donc dans une meme ligne, "
        "`..._c2` est immediatement a DROITE de `..._c1` ; dans une meme "
        "colonne, `..._r1` est immediatement EN DESSOUS de `..._r0`. Le dump "
        "liste les cellules ligne par ligne, gauche-a-droite : utilise ces "
        "indices pour situer le voisin libelle et la cellule a remplir.\n\n"
        "Pour chaque zone a remplir, retourne un objet :\n"
        "- id : 'z_1', 'z_2', ... (sequentiel a partir de 1)\n"
        "- target : l'id de la shape ou cellule (reutilise EXACTEMENT les "
        "ids fournis dans le dump). REGLE ABSOLUE : `target` est l'id de la "
        "cellule/shape QUI VA RECEVOIR le contenu (le plus souvent la cellule "
        "VIDE), JAMAIS l'id de la cellule qui porte deja le libelle. Erreur "
        "frequente a eviter : renvoyer l'id de la cellule libellee (parce "
        "qu'elle a du texte) au lieu de sa voisine vide. Le `label` DECRIT la "
        "cellule cible et se DEDUIT du libelle voisin, mais le `target` "
        "POINTE la cellule a remplir, pas le libelle.\n"
        "- label : description semantique courte (5-15 mots) decrivant ce "
        "que la zone est censee contenir. Le label est un CONTRAT lu en "
        "aval, il doit etre suffisamment precis pour qu'un autre LLM puisse "
        "remplir la zone sans hors-sujet (preferer un libelle explicite et "
        "contextualise a un mot isole, ex. 'Chiffre d'affaires 2023 en euros' "
        "plutot que 'Montant', ou 'Description de la mission principale' "
        "plutot que 'Texte'). Deduis le label de la STRUCTURE OBSERVEE dans "
        "le dump (cellule voisine libellee, titre de section au-dessus, "
        "en-tete de colonne), JAMAIS d'un domaine metier suppose.\n"
        "- kind : 'text_box' ou 'table_cell'\n\n"
        "PRINCIPES DE DETECTION (pas de hardcode template-specifique : "
        "raisonne depuis la structure observee dans le dump) :\n"
        "1. INCLUS comme zones a remplir : toute shape ou cellule dont le "
        "contenu actuel suggere qu'elle attend une valeur :\n"
        "   - Cellule de table vide positionnee a cote d'une cellule "
        "libellee (la cellule libellee est le voisin structurel, la "
        "cellule vide est la zone a remplir).\n"
        "   - Boite de texte vide, ou contenant uniquement un placeholder "
        "('xxx', '...', '___', 'a remplir', 'votre contenu ici').\n"
        "   - Boite de texte dont le contenu actuel ressemble a un exemple "
        "fictif a personnaliser (nom-prenom, titre de poste, date).\n"
        "2. EXCLUS de la liste :\n"
        "   - Toute shape ou cellule qui sert de LIBELLE STRUCTUREL fixe "
        "du template : son texte est une categorie semantique qui ne varie "
        "pas d'un remplissage a l'autre (en-tetes de tableau, etiquettes "
        "de section, titres de rubrique). Reconnaissable par : majuscules "
        "/ gras / repetition entre slides similaires / position d'en-tete.\n"
        "   - Les titres de slide (`slide_title` est extrait par ailleurs).\n"
        "   - Logos, pieds de page, paginations, numeros de slide, "
        "mentions au lecteur ('Confidentiel', 'Page X / Y').\n"
        "   - Les shapes contenant deja 'xxx' (case-insensitive) ou "
        "'{{cle}}' : ces marqueurs sont detectes par un autre systeme "
        "deterministe, ne les double pas (sinon double remplissage).\n\n"
        "Pour CHAQUE zone, formule un label qui (a) decrit le sujet "
        "attendu et (b) precise le CONTEXTE STRUCTUREL si pertinent "
        "(numero d'experience, ligne du tableau, slide). Le label sera le "
        "seul lien entre toi et le LLM de remplissage qui ne voit pas le "
        "template visuellement.\n\n"
        "EXEMPLE (paire libelle/valeur dans une table) : la ligne 0 contient "
        "`{id:'s_1_5_r0_c0', text:'Chiffre d affaires'}` puis "
        "`{id:'s_1_5_r0_c1', text:''}`. La cellule c0 est le LIBELLE (texte "
        "fixe, A EXCLURE), la cellule c1 vide a sa droite est la zone a "
        "remplir. Tu renvoies donc target='s_1_5_r0_c1' (la cellule vide) "
        "avec label='Chiffre d affaires en euros' (deduit du voisin c0). "
        "Renvoyer target='s_1_5_r0_c0' serait l'erreur a ne pas commettre.\n\n"
        "Renvoie STRICTEMENT un objet JSON {'zones': [...]}. Pas "
        "d'explication, pas de markdown, pas de prose autour."
    ),
    "pptx_fill": (
        "Tu es un assistant de remplissage de template PowerPoint. "
        "On te fournit (a) un contenu source en markdown produit par un "
        "autre LLM, et (b) une liste de zones a remplir dans un .pptx. "
        "Chaque zone a un id, un type (`placeholder` pour les marqueurs "
        "explicites {{cle}}, `xxx` pour les zones libres marquees XXX, "
        "`llm` pour une zone identifiee semantiquement), un titre de "
        "slide, un label semantique qui indique le sujet attendu, et une "
        "location ('Slide N / Tableau M / Ligne R') qui aide a distinguer "
        "des zones ayant le meme label dans des tables paralleles. "
        "Tu dois renvoyer STRICTEMENT un objet JSON dont les cles sont "
        "EXACTEMENT les ids fournis, et les valeurs sont du texte brut "
        "(pas de markdown, pas de #, pas de **) destine a etre injecte "
        "dans le .pptx. "
        "\n\n"
        "Certaines zones peuvent porter un champ `instruction` : ce sont des "
        "CONSIGNES explicites de l'utilisateur pour cette zone precise "
        "(format, longueur, ton, langue, angle...). Quand il est present, tu "
        "DOIS le respecter en priorite, il affine ou surcharge les regles de "
        "format ci-dessous pour cette zone.\n\n"
        "REGLES IMPERATIVES :\n"
        "1. EVALUER LA PERTINENCE avant de remplir. Pour chaque zone, "
        "verifie que la source contient des elements pertinents POUR LE "
        "SUJET du label. Si la source ne contient RIEN de pertinent (ou "
        "uniquement du hors-sujet), retourne '' (chaine vide) plutot que "
        "de remplir avec du contenu inadapte.\n"
        "2. RESTE STRICTEMENT dans le champ semantique du label (et de "
        "l'`instruction` si presente). Le label decrit le SUJET attendu, "
        "c'est un contrat : n'invente pas, ne deborde pas sur un sujet "
        "voisin, ne mets pas dans une zone du contenu qui appartient "
        "manifestement a une autre.\n"
        "3. NE CITE JAMAIS LA SOURCE dans la valeur. Pas de 'D'apres le "
        "document...', 'Source : X', 'Selon le rapport...', 'Comme "
        "indique dans...', 'Le candidat declare...'. Ecris en style "
        "factuel direct, comme si l'info etait native du document final. "
        "Le destinataire du PPTX ne connait pas tes sources.\n"
        "4. NE REPETE JAMAIS le titre de la slide (`slide_title`) dans ta "
        "valeur. Le titre est deja affiche par le template, le repeter le "
        "duplique a l'ecran. Ex : slide_title='Dossier Technique - "
        "Synthese' => ta valeur est la synthese pure, sans prefixe "
        "'Dossier Technique' ni 'Synthese :'.\n"
        "5. FORMAT BULLETS pour les rubriques de type liste (enumerations, "
        "points cles, caracteristiques, etapes...). Une puce par ligne, "
        "prefixee par '- ' (tiret + espace), separees par \\n. Pour les "
        "zones de prose continue (synthese, contexte, objectifs, "
        "description), garde un paragraphe continu sans bullets. Si une "
        "`instruction` precise un autre format, elle prime.\n"
        "6. Quand plusieurs zones partagent le meme label (tables "
        "paralleles type 'Experience 1' / 'Experience 2'), utilise leur "
        "location pour les differencier : si la source contient plusieurs "
        "occurrences, attribue chacune a une location distincte. N'attribue "
        "JAMAIS le MEME contenu (meme experience, meme mission, meme item) a "
        "deux zones paralleles : si la source ne fournit qu'une occurrence, "
        "remplis la premiere zone et laisse les zones surnumeraires VIDES ('') "
        "plutot que de dupliquer.\n"
        "7. PAS DE DOUBLON dans une zone liste (langues, outils, "
        "competences...) : ne repete pas deux fois le meme item, meme sous une "
        "variante ou un synonyme (ex. 'AutoCAD' une seule fois)."
        "\n\n"
        "REGLES SPECIFIQUES PAR SUJET DE ZONE (s'appliquent UNIQUEMENT si "
        "le label de la zone concerne ce sujet ; sinon ignore-les). Elles "
        "affinent les regles ci-dessus pour les fiches profil / CV et "
        "restent SANS EFFET sur les autres templates (dossiers techniques, "
        "etc.).\n\n"
        "LANGUE DE SORTIE : produis TOUT le contenu (valeurs des zones, noms "
        "de langues, libelles de niveau, notes 'a verifier') DANS LA LANGUE DE "
        "SORTIE de la session ('Langue de sortie'), en traduisant depuis la "
        "source si besoin. Ne recopie pas la langue de la source si elle "
        "differe.\n\n"
        "A. LANGUES (label type 'langues', 'langues parlees') :\n"
        "   - Indique systematiquement le NIVEAU quand le CV le donne (C1, "
        "B2, 'courant', 'intermediaire', 'bilingue'...), au format "
        "'Langue (niveau)'.\n"
        "   - LANGUE MATERNELLE : ne la signale ('langue maternelle' / "
        "'native') QUE si le CV l'indique EXPLICITEMENT (mention 'langue "
        "maternelle', 'native', 'mother tongue', 'lengua materna' a cote de la "
        "langue). NE LA DEDUIS JAMAIS de la langue de redaction du CV, du pays "
        "d'origine, du lieu de formation ou du nom : sans certitude, n'ajoute "
        "PAS la mention 'maternelle' et liste simplement la langue avec son "
        "niveau s'il est donne, sinon sans niveau.\n"
        "   - N'INVENTE pas de langue absente du CV.\n"
        "   - Le libelle de niveau est lui aussi DANS LA LANGUE DE SORTIE "
        "(ex. sortie EN : 'French (native)', sortie ES : "
        "'Frances (lengua materna)').\n"
        "   - Une langue par ligne (bullet '- ').\n"
        "B. ANNEES D'EXPERIENCE (label type 'annees d'experience', "
        "'experience totale') :\n"
        "   - IGNORE TOUJOURS les stages, alternances, apprentissages, "
        "contrats de professionnalisation et annees de cesure : ils ne "
        "comptent JAMAIS dans le total d'annees d'experience, sans exception.\n"
        "   - Estime la DUREE EFFECTIVE (somme des periodes reellement "
        "travaillees), PAS l'amplitude calendaire entre la premiere et la "
        "derniere date.\n"
        "   - Rends une FOURCHETTE plutot qu'un chiffre faussement precis, "
        "ex. '3-4 ans'. N'ajoute AUCUNE mention parenthetique type "
        "'(estimation, a verifier en cas de chevauchements)' dans la valeur "
        "ecrite : la zone ne contient que la duree.\n"
        "C. FORMATIONS / ECOLES (label type 'formation', 'diplomes', "
        "'parcours academique') :\n"
        "   - Extrais ECOLE/UNIVERSITE + intitule du DIPLOME + ANNEES quand "
        "disponibles, ex. '2015-2018 - INSA Lyon, Diplome d'ingenieur "
        "mecanique'.\n"
        "   - Repere ces informations meme dispersees (mots-cles : diplome, "
        "ecole, universite, plages d'annees 20XX-20XX).\n"
        "   - Ne laisse pas cette zone vide si le CV mentionne un parcours, "
        "meme bref.\n"
        "D. OUTILS / LOGICIELS (label type 'outils', 'logiciels', "
        "'maitrise technique') :\n"
        "   - Liste aussi les outils cites EN PROSE dans les experiences, "
        "pas seulement ceux d'une section dediee.\n"
        "   - Reconnais les SYNONYMES courants et normalise sur le nom usuel "
        "(ex. 'Autodesk AutoCAD' -> 'AutoCAD', 'Suite Microsoft Office' -> "
        "'Office').\n"
        "   - Un outil par ligne (bullet '- ').\n"
        "E. ZONE SANS INFORMATION (habilitations, certifications, langues, "
        "formations... ou toute autre zone) :\n"
        "   - N'emets JAMAIS de marqueur creux ('[vide]', 'N/A', 'neant', "
        "'-', 'non renseigne') NI de note type 'aucun element detecte'.\n"
        "   - Si la source ne contient aucune information pertinente pour la "
        "zone, retourne '' (chaine vide). La zone sera laissee VIDE dans le "
        "document final (elle n'est pas conservee avec un contenu de "
        "substitution). C'est le comportement attendu, conforme a la regle 1."
    ),
}


def get_prompt(db: Session, name: str) -> str:
    """Lit le prompt en DB. Si vide ou absent, renvoie le defaut."""
    if name not in PROMPT_KEYS:
        raise KeyError(f"Unknown prompt name: {name}")
    row = db.get(AppConfig, PROMPT_KEYS[name])
    if row and row.value:
        return row.value
    return DEFAULTS[name]


def set_prompt(db: Session, name: str, value: str) -> None:
    """Persiste un prompt en DB. Chaine vide = reset au defaut (efface la
    cle pour que `get_prompt` retombe sur DEFAULTS)."""
    if name not in PROMPT_KEYS:
        raise KeyError(f"Unknown prompt name: {name}")
    key = PROMPT_KEYS[name]
    row = db.get(AppConfig, key)
    if not value:
        if row is not None:
            db.delete(row)
    else:
        if row is None:
            db.add(AppConfig(key=key, value=value))
        else:
            row.value = value
    db.commit()


def get_all_prompts(db: Session) -> dict[str, dict[str, str | bool]]:
    """Renvoie l'etat courant des 2 prompts, avec un flag `is_default`
    pour que l'UI sache si l'utilisateur a override ou pas."""
    out: dict[str, dict[str, str | bool]] = {}
    for name, key in PROMPT_KEYS.items():
        row = db.get(AppConfig, key)
        customized = bool(row and row.value)
        out[name] = {
            "value": row.value if customized else DEFAULTS[name],
            "is_default": not customized,
        }
    return out