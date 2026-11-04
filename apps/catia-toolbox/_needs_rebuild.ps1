# Determine si le front React doit etre reconstruit.
#
# Exit 1  -> rebuild necessaire (dist absent OU une source front est plus
#            recente que le dernier build dist\index.html).
# Exit 0  -> dist a jour, aucun build necessaire.
#
# Appele par _run.bat avant de servir frontend\dist. Comparaison de dates
# fiable (impossible a faire proprement en batch pur).
param([Parameter(Mandatory = $true)][string]$FrontendDir)

$dist = Join-Path $FrontendDir 'dist\index.html'
if (-not (Test-Path $dist)) { exit 1 }

$distTime = (Get-Item $dist).LastWriteTime

# Changes to framework and consumer-owned shared sources also require a rebuild.
$repo = [IO.Path]::GetFullPath((Join-Path $FrontendDir '..\..\..'))
$roots = @(
    (Join-Path $FrontendDir 'src'),
    (Join-Path $FrontendDir 'index.html'),
    (Join-Path $FrontendDir 'package.json'),
    (Join-Path $FrontendDir 'vite.config.ts'),
    (Join-Path $FrontendDir 'tailwind.config.ts'),
    (Join-Path $FrontendDir 'postcss.config.js'),
    (Join-Path $repo 'framework\packages\ui\src'),
    (Join-Path $repo 'framework\design-tokens'),
    (Join-Path $repo 'packages\techdoc-brand\src'),
    (Join-Path $repo 'pnpm-lock.yaml'),
    (Join-Path $repo 'pnpm-workspace.yaml'),
    (Join-Path $repo 'tsconfig.base.json')
)

foreach ($root in $roots) {
    if (-not (Test-Path $root)) { continue }
    $newer = Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -gt $distTime } |
        Select-Object -First 1
    if ($newer) { exit 1 }
}

exit 0
