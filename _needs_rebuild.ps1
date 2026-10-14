param(
    [Parameter(Mandatory = $true)]
    [string]$FrontendDir,
    [Parameter(Mandatory = $true)]
    [string]$StaticDir
)

$builtIndex = Join-Path $StaticDir "index.html"
if (-not (Test-Path -LiteralPath $builtIndex -PathType Leaf)) {
    exit 1
}

$builtAt = (Get-Item -LiteralPath $builtIndex).LastWriteTimeUtc
$sourcePaths = @(
    (Join-Path $FrontendDir "src"),
    (Join-Path $FrontendDir "index.html"),
    (Join-Path $FrontendDir "package.json"),
    (Join-Path $FrontendDir "pnpm-lock.yaml"),
    (Join-Path $FrontendDir "pnpm-workspace.yaml"),
    (Join-Path $FrontendDir "tsconfig.json"),
    (Join-Path $FrontendDir "vite.config.ts")
)

foreach ($sourcePath in $sourcePaths) {
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        continue
    }
    $sourceItem = Get-Item -LiteralPath $sourcePath
    if ($sourceItem.PSIsContainer) {
        $sourceFiles = Get-ChildItem -LiteralPath $sourcePath -File -Recurse
    }
    else {
        $sourceFiles = @($sourceItem)
    }
    foreach ($sourceFile in $sourceFiles) {
        if ($sourceFile.LastWriteTimeUtc -gt $builtAt) {
            exit 1
        }
    }
}

exit 0
