# Determine si le front React doit etre reconstruit.
param([Parameter(Mandatory = $true)][string]$FrontendDir)

$dist = Join-Path $FrontendDir 'dist\index.html'
if (-not (Test-Path $dist)) { exit 1 }

$distTime = (Get-Item $dist).LastWriteTime
$roots = @(
    (Join-Path $FrontendDir 'src'),
    (Join-Path $FrontendDir 'index.html'),
    (Join-Path $FrontendDir 'package.json'),
    (Join-Path $FrontendDir 'vite.config.ts'),
    (Join-Path $FrontendDir 'tailwind.config.ts'),
    (Join-Path $FrontendDir 'postcss.config.js')
)

foreach ($root in $roots) {
    if (-not (Test-Path $root)) { continue }
    $newer = Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -gt $distTime } |
        Select-Object -First 1
    if ($newer) { exit 1 }
}

exit 0