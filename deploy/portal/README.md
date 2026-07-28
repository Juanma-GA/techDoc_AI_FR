# Portail ATEXIS POCS

Page d'accueil statique qui liste les POCs déployés et pointe vers chacun. Elle
se pose **à la racine du chemin parent** sous lequel les POCs sont montés en IIS,
et sert de point d'entrée unique + de cible du bouton « Portail » présent dans
chaque app.

## Modèle de déploiement

Les POCs sont déployés comme sous-applications IIS sous un **chemin parent
commun**. Exemples observés :

- `https://172.21.28.92/Customizations/AtexisPOCS/<poc>/` (cf.
  `apps/corpus-agent/DEPLOYMENT_GUIDE.md`)
- `http://172.21.28.81/app/atexispocs-cd/<poc>/`

Le portail se pose à la **racine de ce parent** :

```
/<parent>/                 <-- index.html (ce portail)
/<parent>/corpus-agent/    <-- sous-application IIS
/<parent>/doc-writer/      <-- sous-application IIS
```

Comme les liens du portail sont **relatifs** (`href="corpus-agent/"`), la même
page fonctionne quel que soit le parent — **aucune URL ni IP en dur**.

## Pose sur IIS

1. Copier `index.html` dans le dossier physique mappé sur le chemin parent
   (p. ex. `C:\inetpub\wwwroot\Customizations\AtexisPOCS\`).
2. S'assurer que `index.html` est dans les **Default Documents** du site/dossier
   (sinon activer *Directory Browsing*, mais le `index.html` est préférable).
3. Chaque POC reste une application IIS distincte sous ce parent, buildée avec
   son `VITE_BASE=/<parent>/<poc>/` (cf. le guide de déploiement du POC).

## Ajouter / retirer un POC

Éditer le tableau `POCS` en bas de `index.html` (slug = dossier de la
sous-application, `name`, `desc`). Aucune étape de build.

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

Artefact de **déploiement**, hors périmètre du standard POC. Contrairement à la
règle #4, les couleurs sont un **miroir manuel** de `design-tokens/tokens.json` :
une page statique autonome ne peut pas consommer le preset Tailwind sans build.
Le dual-theme (toggle + anti-flash, clé `localStorage["theme"]`) et les fonts
(Inter / Orbitron / JetBrains Mono) restent alignés sur les POCs.
