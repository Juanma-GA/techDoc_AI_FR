param([string]$AppDir = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
try {
    $app = [IO.Path]::GetFullPath($AppDir)
    $root = [IO.Path]::GetFullPath((Join-Path $app '..\..'))
    $backend = Join-Path $app 'backend'
    $goRoot = Join-Path $root 'go-embed'
    $go = Join-Path $goRoot 'bin\go.exe'
    $binary = Join-Path $backend 'bin\pdf-toolkit-backend.exe'
    foreach ($required in @($go, (Join-Path $backend 'vendor\modules.txt'),
        (Join-Path $backend 'web\static\generated\index.html'))) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Incomplete Go package: $required"
        }
    }
    $roots = @('cmd', 'handlers', 'services', 'pdf', 'web', 'vendor', 'go.mod', 'go.sum') |
        ForEach-Object { Join-Path $backend $_ }
    $roots += (Join-Path $goRoot 'VERSION'), $PSCommandPath
    $needsBuild = -not (Test-Path -LiteralPath $binary -PathType Leaf)
    if (-not $needsBuild) {
        $builtAt = (Get-Item -LiteralPath $binary).LastWriteTimeUtc
        foreach ($source in $roots) {
            $item = Get-Item -LiteralPath $source
            if ($item.PSIsContainer) { $files = Get-ChildItem -LiteralPath $source -Recurse -File }
            else { $files = @($item) }
            if ($files | Where-Object { $_.LastWriteTimeUtc -gt $builtAt } | Select-Object -First 1) {
                $needsBuild = $true
                break
            }
        }
    }
    if (-not $needsBuild) {
        Write-Output '[backend] Local Go binary up to date.'
        exit 0
    }
    $env:GOROOT = $goRoot
    $env:PATH = (Join-Path $goRoot 'bin') + ';' + $env:PATH
    $env:GOTOOLCHAIN = 'local'
    $env:GOWORK = 'off'
    $env:GOENV = 'off'
    $env:GOPROXY = 'off'
    $env:GOSUMDB = 'off'
    $env:GOFLAGS = '-mod=vendor'
    $env:CGO_ENABLED = '0'
    $env:GOOS = 'windows'
    $env:GOARCH = 'amd64'
    $env:GOCACHE = Join-Path $root '.go-cache'
    New-Item -ItemType Directory -Path (Split-Path $binary) -Force | Out-Null
    Write-Output '[build] Compiling with bundled Go, offline. First launch can take a few minutes.'
    Push-Location $backend
    try {
        & $go build -o $binary '.\cmd\pdf-toolkit'
        if ($LASTEXITCODE -ne 0) { throw "Go compilation failed with exit code $LASTEXITCODE." }
    }
    finally { Pop-Location }
    Write-Output '[build] Local Go compilation completed.'
    exit 0
}
catch {
    [Console]::Error.WriteLine("[error] $($_.Exception.Message)")
    [Console]::Error.WriteLine('[info] If Windows blocks a tool or executable, contact IT. Security settings are unchanged.')
    exit 1
}
