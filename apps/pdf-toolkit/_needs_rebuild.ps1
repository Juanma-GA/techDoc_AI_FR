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
    if ($item.PSIsContainer) {
        foreach ($file in [IO.Directory]::EnumerateFiles($root, '*', [IO.SearchOption]::AllDirectories)) {
            if ([IO.File]::GetLastWriteTimeUtc($file) -gt $builtAt) { exit 1 }
        }
    } elseif ($item.LastWriteTimeUtc -gt $builtAt) {
        exit 1
    }
}
exit 0
