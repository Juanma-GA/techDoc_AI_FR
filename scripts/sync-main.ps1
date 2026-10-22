$ErrorActionPreference = "Stop"

function Stop-Script {
    param(
        [string]$Message,
        [int]$ExitCode = 1
    )

    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    exit $ExitCode
}

function Test-MergeInProgress {
    git rev-parse -q --verify MERGE_HEAD *> $null
    return ($LASTEXITCODE -eq 0)
}

function Get-UnresolvedFiles {
    return @(git diff --name-only --diff-filter=U)
}

# Vérification : sommes-nous dans un dépôt Git ?
git rev-parse --is-inside-work-tree *> $null

if ($LASTEXITCODE -ne 0) {
    Stop-Script "Le dossier courant n'est pas un dépôt Git."
}

# Récupération automatique du nom de la branche actuelle
$branch = git branch --show-current

if ([string]::IsNullOrWhiteSpace($branch)) {
    Stop-Script "Impossible de continuer : Git est en mode detached HEAD."
}

if ($branch -eq "main") {
    Stop-Script "Tu es déjà sur main. Ce script doit être lancé depuis une branche de travail."
}

Write-Host ""
Write-Host "Branche actuelle : $branch" -ForegroundColor Cyan

# Cas 1 : un merge est déjà en cours
if (Test-MergeInProgress) {
    Write-Host "Un merge est déjà en cours." -ForegroundColor Yellow

    $unresolvedFiles = Get-UnresolvedFiles

    if ($unresolvedFiles.Count -gt 0) {
        Write-Host ""
        Write-Host "Conflits encore présents :" -ForegroundColor Red

        foreach ($file in $unresolvedFiles) {
            Write-Host "  - $file"
        }

        Write-Host ""
        Write-Host "Résous les conflits dans VS Code, puis relance cette tâche." -ForegroundColor Yellow
        exit 1
    }

    Write-Host "Tous les conflits semblent résolus." -ForegroundColor Green
    Write-Host "Ajout des fichiers résolus..."

    git add -A

    if ($LASTEXITCODE -ne 0) {
        Stop-Script "Impossible d'ajouter les fichiers résolus."
    }

    Write-Host "Création du merge commit..."

    git commit -m "Merge origin/main into $branch"

    if ($LASTEXITCODE -ne 0) {
        Stop-Script "Impossible de créer le merge commit."
    }

    Write-Host "Push vers origin/$branch..."

    git push origin $branch

    if ($LASTEXITCODE -ne 0) {
        Stop-Script "Le commit a été créé, mais le push a échoué."
    }

    Write-Host ""
    Write-Host "Synchronisation terminée avec succès." -ForegroundColor Green
    exit 0
}

# Cas 2 : aucun merge en cours
Write-Host ""
Write-Host "État du dépôt :"
git status --short --branch

# Empêche le mélange avec des modifications locales existantes
$localChanges = @(git status --porcelain)

if ($localChanges.Count -gt 0) {
    Stop-Script "Le dépôt contient des modifications locales. Commit, stash ou supprime-les avant de continuer."
}

Write-Host ""
Write-Host "Récupération des dernières modifications de origin..."

git fetch origin

if ($LASTEXITCODE -ne 0) {
    Stop-Script "git fetch origin a échoué."
}

Write-Host ""
Write-Host "Merge de origin/main dans $branch..."

git merge --no-commit --no-ff origin/main
$mergeExitCode = $LASTEXITCODE

# Vérification des conflits
$unresolvedFiles = Get-UnresolvedFiles

if ($unresolvedFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "Le merge contient des conflits :" -ForegroundColor Red

    foreach ($file in $unresolvedFiles) {
        Write-Host "  - $file"
    }

    Write-Host ""
    Write-Host "Résous-les dans l'éditeur de merge de VS Code." -ForegroundColor Yellow
    Write-Host "Ensuite, relance exactement la même tâche avec Ctrl+Shift+B." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Pour annuler complètement : git merge --abort" -ForegroundColor DarkGray

    exit 1
}

if ($mergeExitCode -ne 0) {
    Stop-Script "Le merge a échoué pour une raison autre qu'un conflit classique."
}

if (-not (Test-MergeInProgress)) {
    Stop-Script "Git n'indique aucun merge en cours. Aucun commit ne sera créé."
}

Write-Host ""
Write-Host "Merge effectué sans conflit." -ForegroundColor Green
Write-Host "Création du commit..."

git commit -m "Merge origin/main into $branch"

if ($LASTEXITCODE -ne 0) {
    StopImpossible de créer le merge commit."
}

Write-Host ""
Write-Host "Push vers origin/$branch..."

git push origin $branch

if ($LASTEXITCODE -ne 0) {
    Stop-Script "Le commit a été créé, mais le push a échoué."
}

Write-Host ""
Write-Host "origin/main a bien été intégré dans $branch." -ForegroundColor Green