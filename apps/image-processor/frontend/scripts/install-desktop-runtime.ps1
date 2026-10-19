$ErrorActionPreference = "Stop"
$runtimeRoot = $PSScriptRoot
$tempRoot = $null
$script:httpClient = $null
$env:PYTHONNOUSERSITE = "1"
if (Test-Path Env:PYTHONUSERBASE) {
  Remove-Item Env:PYTHONUSERBASE
}

try {
  . (Join-Path $runtimeRoot "desktop-install-runtime-functions.ps1")
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Add-Type -AssemblyName System.Net.Http
  $configPath = Join-Path $runtimeRoot "desktop-install.json"
  if (!(Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "Missing desktop install configuration: $configPath"
  }
  $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
  $cache = $config.model_cache
  $paddleCache = Join-Path $runtimeRoot $cache.paddlex
  foreach ($model in $cache.ocr_models) {
    if (!(Test-Path -LiteralPath (Join-Path $paddleCache $model) -PathType Container)) {
      throw "Bundled PaddleOCR model is missing: $model"
    }
  }
  $lamaCheckpoint = Join-Path (Join-Path $runtimeRoot $cache.torch_home) "hub\checkpoints\big-lama.pt"
  if (!(Test-Path -LiteralPath $lamaCheckpoint -PathType Leaf) -or
      (Get-Item -LiteralPath $lamaCheckpoint).Length -eq 0) {
    throw "Bundled LaMa checkpoint is missing or empty."
  }

  $apiVersion = [string]$config.python_versions.api
  $lamaVersion = [string]$config.python_versions.lama
  $apiFingerprint = Get-EnvironmentFingerprint "python-ocr" $apiVersion "requirements-api.lock" "backend" @("../backend")
  $lamaFingerprint = Get-EnvironmentFingerprint "python-lama" $lamaVersion "requirements-lama.lock" "backend\lama_service" @("../backend/lama_service")
  $installApi = !(Test-InstalledEnvironment "python-ocr" $apiFingerprint)
  $installLama = !(Test-InstalledEnvironment "python-lama" $lamaFingerprint)

  if (!$installApi -and !$installLama) {
    Write-InstallerProgress "Python dependencies are already installed."
  } else {
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.Proxy = [System.Net.WebRequest]::DefaultWebProxy
    $script:httpClient = [System.Net.Http.HttpClient]::new($handler)
    $script:httpClient.Timeout = [TimeSpan]::FromMinutes(30)
    $env:PIP_NO_CACHE_DIR = "1"
    $env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
    $env:PIP_PROGRESS_BAR = "on"
    $tempRoot = Join-Path $env:TEMP ("image-processor-install-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    $getPipPath = Join-Path $tempRoot "get-pip.py"
    Download-File ([string]$config.get_pip_url) $getPipPath "pip bootstrap"

    if ($installApi) {
      $archiveName = "python-$apiVersion-embed-amd64.zip"
      $archivePath = Join-Path $tempRoot $archiveName
      Download-File "https://www.python.org/ftp/python/$apiVersion/$archiveName" $archivePath "Python $apiVersion"
      Write-InstallerProgress "Installing the PaddleOCR Python environment..."
      Install-PythonEnvironment "python-ocr" $apiVersion $archivePath $getPipPath `
        "requirements-api.lock" "backend" @("../backend") $apiFingerprint
    }
    if ($installLama) {
      $archiveName = "python-$lamaVersion-embed-amd64.zip"
      $archivePath = Join-Path $tempRoot $archiveName
      Download-File "https://www.python.org/ftp/python/$lamaVersion/$archiveName" $archivePath "Python $lamaVersion"
      Write-InstallerProgress "Installing the LaMa Python environment..."
      Install-PythonEnvironment "python-lama" $lamaVersion $archivePath $getPipPath `
        "requirements-lama.lock" "backend\lama_service" @("../backend/lama_service") $lamaFingerprint
    }
  }
  Write-InstallerProgress "Runtime installation completed. The bundled models are ready for offline use."
} finally {
  if ($script:httpClient) {
    $script:httpClient.Dispose()
  }
  if ($tempRoot -and (Test-Path -LiteralPath $tempRoot)) {
    try {
      Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction Stop
    } catch {
      [Console]::Error.WriteLine("[Image Processor] Temporary files remain at ${tempRoot}: $($_.Exception.Message)")
    }
  }
}
