# Portail AI4TECHDOC

Page d'accueil statique qui liste les POCs déployés et pointe vers chacun. Elle
se pose **à la racine du chemin parent** sous lequel les POCs sont montés en IIS,
et sert de point d'entrée unique + de cible du bouton « Portail » présent dans
chaque app.

## Modèle de déploiement

Les POCs sont déployés comme sous-applications IIS sous un **chemin parent
commun**. Exemple de forme observée (IP/hôte réel non reproduit ici — voir le
guide de déploiement de l'app concernée pour la valeur réelle) :

- `https://<hote-iis-interne>/Customizations/AtexisPOCS/<poc>/` (cf.
  `apps/corpus-agent/DEPLOYMENT_GUIDE.md`)

Le portail se pose à la **racine de ce parent** :

```
/<parent>/                 <-- index.html, roadmap.html, ia-ecosystem.html
                             portal.css, portal.js, config.json
/<parent>/corpus-agent/    <-- sous-application IIS
/<parent>/doc-writer/      <-- sous-application IIS
```

Comme les liens du portail sont **relatifs** (`href="corpus-agent/"`), la même
page fonctionne quel que soit le parent — **aucune URL ni IP en dur**.

## Pose sur IIS

1. Copier les trois fichiers HTML, `portal.css`, `portal.js` et `config.json`
  dans le dossier physique mappé sur le chemin parent (p. ex.
  `C:\inetpub\wwwroot\Customizations\AtexisPOCS\`).
2. S'assurer que `index.html` est dans les **Default Documents** du site/dossier
   (sinon activer *Directory Browsing*, mais le `index.html` est préférable).
3. Chaque POC reste une application IIS distincte sous ce parent, buildée avec
   son `VITE_BASE=/<parent>/<poc>/` (cf. le guide de déploiement du POC).

## Ajouter / retirer un POC

**Éditer uniquement `config.json`**, pas `index.html`. La liste des POCs et les textes i18n sont maintenant externalisés (HR0/HR8 — Everything configurable).

```json
// config.json
{
  "pocs": [
    { "slug": "corpus-agent", "name": "...", "category": "quality", "desc": { "fr": "...", "en": "..." } },
    { "slug": "future-app", "name": "...", "category": "assistants", "status": "planned", "desc": { "fr": "...", "en": "..." } },
    // ajouter ici
  ],
  "subtitle": { "fr": "...", "en": "..." },
  "footer": { "fr": "...", "en": "..." }
}
```

Le statut `planned` affiche une carte « À venir » sans créer de lien vers une
route qui n'existe pas encore. Le statut `validation` conserve une carte
cliquable avec le badge « À valider ».

Les familles et leur ordre d'affichage sont déclarés dans `categories`. Chaque
application référence une famille avec la propriété `category`; une catégorie
inconnue reste visible dans une section de repli « Autres applications ».

Aucune étape de build : les pages chargent `portal.css` et `portal.js` pour
l'UI commune, puis `config.json` pour les applications et textes configurables.

## Retour au portail depuis un POC

Chaque app affiche un lien **« Portail »** en tête de sa barre latérale
(composant partagé `PortalLink` de `@internal/ui`). Il pointe vers le **chemin
parent** de la base de l'app, calculé à partir de `import.meta.env.BASE_URL` au
build. En développement local (base `/`), le lien est **masqué**.

> Actuellement câblé sur **corpus-agent** et **doc-writer**. Pour l'ajouter à
> un autre POC : `import { PortalLink } from "@internal/ui"`, placer
> `<PortalLink className="nav-item" label={t("nav.portal")} />` en tête du `<nav>`
> de la sidebar, et ajouter la clé i18n `nav.portal` (FR « Portail » / EN
> « Portal »).

## Écart au standard (assumé)

Artefact de **déploiement**, hors périmètre du standard POC. Le portail adopte une approche hybrid AACF :

- **HR0/HR8 (Everything configurable)** : ✅ La liste POCS et textes i18n sont externalisés dans `config.json`, pas hardcodés.
- **HR1 (No localStorage for auth)** : ✅ Accepté — localStorage utilisé uniquement pour **préférences UI** (langue, thème), pas d'auth/state métier. Fallback gracieux si localStorage indisponible.
- **HR21 (Humanized UI)** : ✅ Couleurs via CSS variables (dual-theme), fonts AACF (Inter, Orbitron, JetBrains Mono).
- **HR6/HR7** : ✅ Pas de truncate; fallback explicite si `config.json` indisponible (message à l'écran).

**Compliance** : 4/4 AACF rules (hard rules relevant to static portal)
