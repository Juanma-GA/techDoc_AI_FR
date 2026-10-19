function Write-InstallerProgress {
  param([string]$Message)
  [Console]::Out.WriteLine("[Image Processor] $Message")
}

function Download-File {
  param(
    [string]$Url,
    [string]$Destination,
    [string]$Label
  )

  $response = $null
  $sourceStream = $null
  $outputStream = $null
  $failure = $null
  $receivedBytes = 0L
  try {
    Write-InstallerProgress "Downloading $Label..."
    $response = $script:httpClient.GetAsync(
      $Url,
      [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
    ).GetAwaiter().GetResult()
    $null = $response.EnsureSuccessStatusCode()
    $sourceStream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
    $outputStream = [System.IO.File]::Create($Destination)
    $buffer = New-Object byte[] 1048576
    $totalBytes = $response.Content.Headers.ContentLength
    $nextPercent = 10
    $nextBytes = 64MB
    while (($readBytes = $sourceStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
      $outputStream.Write($buffer, 0, $readBytes)
      $receivedBytes += $readBytes
      if ($totalBytes -gt 0) {
        $percent = [int](100 * $receivedBytes / $totalBytes)
        while ($percent -ge $nextPercent) {
          Write-InstallerProgress "${Label}: $nextPercent%"
          $nextPercent += 10
        }
      } elseif ($receivedBytes -ge $nextBytes) {
        Write-InstallerProgress ("{0}: {1:N0} MiB received" -f $Label, ($receivedBytes / 1MB))
        $nextBytes += 64MB
      }
    }
  } catch {
    $failure = $_.Exception.Message
  } finally {
    if ($outputStream) { $outputStream.Dispose() }
    if ($sourceStream) { $sourceStream.Dispose() }
    if ($response) { $response.Dispose() }
  }
  if (!$failure -and $receivedBytes -eq 0) {
    $failure = "The downloaded file is empty."
  }
  if ($failure) {
    Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
    throw "Download failed for ${Label}: $failure"
  }
  Write-InstallerProgress "$Label downloaded."
}

function Invoke-Python {
  param(
    [string]$Python,
    [string[]]$Arguments,
    [string]$WorkingDirectory
  )

  Push-Location -LiteralPath $WorkingDirectory
  try {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Python command failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
  } finally {
    Pop-Location
  }
}

function Get-EnvironmentFingerprint {
  param(
    [string]$Name,
    [string]$Version,
    [string]$LockName,
    [string]$ProjectRelativePath,
    [string[]]$ImportPaths
  )

  $lockPath = Join-Path $runtimeRoot $LockName
  $manifestPath = Join-Path (Join-Path $runtimeRoot $ProjectRelativePath) "pyproject.toml"
  foreach ($file in @($lockPath, $manifestPath)) {
    if (!(Test-Path -LiteralPath $file -PathType Leaf)) {
      throw "Missing dependency input for ${Name}: $file"
    }
  }
  $lockHash = (Get-FileHash -LiteralPath $lockPath -Algorithm SHA256).Hash
  $manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash
  return "$Name`n$Version`n$($ImportPaths -join "`n")`n$lockHash`n$manifestHash"
}

function Test-InstalledEnvironment {
  param(
    [string]$Name,
    [string]$Fingerprint
  )

  $environment = Join-Path $runtimeRoot $Name
  $python = Join-Path $environment "python.exe"
  $marker = Join-Path $environment ".image-processor-installed"
  if (!(Test-Path -LiteralPath $python -PathType Leaf) -or
      !(Test-Path -LiteralPath $marker -PathType Leaf)) {
    return $false
  }
  return (Get-Content -LiteralPath $marker -Raw).Trim() -eq $Fingerprint
}

function Install-PythonEnvironment {
  param(
    [string]$Name,
    [string]$Version,
    [string]$ArchivePath,
    [string]$GetPipPath,
    [string]$LockName,
    [string]$ProjectRelativePath,
    [string[]]$ImportPaths,
    [string]$Fingerprint
  )

  $staging = Join-Path $runtimeRoot "$Name.installing"
  $target = Join-Path $runtimeRoot $Name
  $backup = Join-Path $runtimeRoot "$Name.previous"
  $lockPath = Join-Path $runtimeRoot $LockName
  $projectPath = Join-Path $runtimeRoot $ProjectRelativePath
  if (Test-Path -LiteralPath $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force
  }
  if (Test-Path -LiteralPath $backup) {
    Remove-Item -LiteralPath $backup -Recurse -Force
  }

  try {
    New-Item -ItemType Directory -Path $staging | Out-Null
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $staging -Force
    $pthFile = Get-ChildItem -LiteralPath $staging -Filter "python*._pth" -File |
      Select-Object -First 1
    if (!$pthFile) {
      throw "Missing embedded Python path file for $Name."
    }
    $versionParts = $Version.Split(".")
    $pathLines = @("python$($versionParts[0])$($versionParts[1]).zip", ".")
    $pathLines += $ImportPaths
    $pathLines += @("Lib/site-packages", "import site")
    [System.IO.File]::WriteAllLines($pthFile.FullName, $pathLines, [System.Text.Encoding]::ASCII)
    New-Item -ItemType Directory -Path (Join-Path $staging "Lib\site-packages") -Force |
      Out-Null

    $python = Join-Path $staging "python.exe"
    Write-InstallerProgress "Bootstrapping pip for Python $Version..."
    Invoke-Python $python @($GetPipPath, "--no-warn-script-location") $runtimeRoot
    Invoke-Python $python @(
      "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
      "--progress-bar", "on", "--upgrade", "--requirement", $lockPath
    ) $runtimeRoot
    Write-InstallerProgress "Installing the $Name application package..."
    Invoke-Python $python @(
      "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
      "--progress-bar", "on", "--no-build-isolation", "--no-deps", $projectPath
    ) $runtimeRoot
    [System.IO.File]::WriteAllText(
      (Join-Path $staging ".image-processor-installed"),
      $Fingerprint,
      [System.Text.Encoding]::ASCII
    )

    if (Test-Path -LiteralPath $target) {
      Move-Item -LiteralPath $target -Destination $backup
    }
    try {
      Move-Item -LiteralPath $staging -Destination $target
    } catch {
      if (Test-Path -LiteralPath $backup) {
        Move-Item -LiteralPath $backup -Destination $target
      }
      throw
    }
    if (Test-Path -LiteralPath $backup) {
      Remove-Item -LiteralPath $backup -Recurse -Force
    }
  } finally {
    if (Test-Path -LiteralPath $staging) {
      Remove-Item -LiteralPath $staging -Recurse -Force
    }
  }
}
