param(
    [Parameter(Mandatory = $true)][string]$FrontendDir,
    [string]$StaticDir = (Join-Path $FrontendDir '..\backend\web\static\generated')
)
$ErrorActionPreference = 'Stop'
$index = Join-Path $StaticDir 'index.html'
if (-not (Test-Path -LiteralPath $index -PathType Leaf)) { exit 1 }
$builtAt = (Get-Item -LiteralPath $index).LastWriteTimeUtc
$repo = [IO.Path]::GetFullPath((Join-Path $FrontendDir '..\..\..'))
$roots = @('src', 'public', 'index.html', 'package.json', 'tsconfig.json',
    'vite.config.ts', 'tailwind.config.ts', 'postcss.config.js') |
    ForEach-Object { Join-Path $FrontendDir $_ }
$roots += @('framework\packages\ui\src', 'framework\design-tokens',
    'packages\techdoc-brand\src', 'pnpm-lock.yaml',
    'pnpm-workspace.yaml', 'tsconfig.base.json') |
    ForEach-Object { Join-Path $repo $_ }
foreach ($root in $roots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $item = Get-Item -LiteralPath $root
    if ($item.PSIsContainer) { $files = Get-ChildItem -LiteralPath $root -File -Recurse }
    else { $files = @($item) }
    if ($files | Where-Object { $_.LastWriteTimeUtc -gt $builtAt } | Select-Object -First 1) { exit 1 }
}
exit 0
