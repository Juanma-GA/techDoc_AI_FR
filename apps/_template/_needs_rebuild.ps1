param([Parameter(Mandatory = $true)][string]$FrontendDir)
$ErrorActionPreference = 'Stop'
$index = Join-Path $FrontendDir 'dist\index.html'
if (-not (Test-Path -LiteralPath $index -PathType Leaf)) { exit 1 }
$builtAt = (Get-Item -LiteralPath $index).LastWriteTimeUtc
$repo = [IO.Path]::GetFullPath((Join-Path $FrontendDir '..\..\..'))
$roots = @('src', 'public', 'index.html', 'package.json', 'tsconfig.json',
    'vite.config.ts', 'tailwind.config.ts', 'postcss.config.js', '.env.production') |
    ForEach-Object { Join-Path $FrontendDir $_ }
$roots += @('packages\ui\src', 'design-tokens', 'pnpm-lock.yaml',
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
