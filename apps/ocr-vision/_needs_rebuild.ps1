# Determine si le front React doit etre reconstruit.
param([Parameter(Mandatory = $true)][string]$FrontendDir)

$dist = Join-Path $FrontendDir 'dist\index.html'
if (-not (Test-Path $dist)) { exit 1 }

$distTime = (Get-Item $dist).LastWriteTime
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
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $item = Get-Item -LiteralPath $root
    if ($item.PSIsContainer) {
        foreach ($file in [IO.Directory]::EnumerateFiles($root, '*', [IO.SearchOption]::AllDirectories)) {
            if ([IO.File]::GetLastWriteTime($file) -gt $distTime) { exit 1 }
        }
    } elseif ($item.LastWriteTime -gt $distTime) {
        exit 1
    }
}

exit 0