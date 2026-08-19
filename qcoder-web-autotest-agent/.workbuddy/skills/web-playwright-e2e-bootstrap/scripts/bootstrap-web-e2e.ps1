param(
  [string]$ProjectPath = ".",
  [switch]$Force,
  [switch]$SkipInstall,
  [switch]$InstallBrowser,
  [switch]$SkipSelfTest
)

$ErrorActionPreference = "Stop"

function Assert-Command {
  param(
    [string]$CommandName,
    [string]$InstallUrl
  )

  $cmd = Get-Command $CommandName -ErrorAction SilentlyContinue
  if (-not $cmd) {
    throw "Missing '$CommandName'. Please install required runtime first: $InstallUrl"
  }
}

function Get-EnvKeys {
  param([string]$Path)

  $keys = @{}
  if (-not (Test-Path $Path)) {
    return $keys
  }

  $lines = Get-Content -Path $Path -Encoding UTF8
  foreach ($line in $lines) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=') {
      $keys[$Matches[1]] = $true
    }
  }
  return $keys
}

function Merge-MissingEnvLines {
  param(
    [string]$EnvPath,
    [string]$EnvExamplePath
  )

  if (-not (Test-Path $EnvExamplePath)) {
    return 0
  }

  if (-not (Test-Path $EnvPath)) {
    Copy-Item -Path $EnvExamplePath -Destination $EnvPath -Force
    return -1
  }

  $existingKeys = Get-EnvKeys -Path $EnvPath
  $exampleLines = Get-Content -Path $EnvExamplePath -Encoding UTF8
  $missingLines = New-Object System.Collections.Generic.List[string]

  foreach ($line in $exampleLines) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=') {
      $key = $Matches[1]
      if (-not $existingKeys.ContainsKey($key)) {
        $missingLines.Add($line)
      }
    }
  }

  if ($missingLines.Count -gt 0) {
    Add-Content -Path $EnvPath -Value "" -Encoding UTF8
    Add-Content -Path $EnvPath -Value "# Added by bootstrap-web-e2e.ps1" -Encoding UTF8
    foreach ($line in $missingLines) {
      Add-Content -Path $EnvPath -Value $line -Encoding UTF8
    }
  }

  return $missingLines.Count
}

function Test-IsCriticalTemplateFile {
  param([string]$RelativePath)

  $normalized = $RelativePath.Replace("/", "\")
  $criticalFiles = @(
    ".env.example",
    "README.md",
    "package.json",
    "playwright.config.js",
    "TEST_CASE_SPEC.md",
    "reporters\self-test-report-reporter.js",
    "scripts\generate-case-from-spec.js",
    "scripts\serial-node-readback.ps1",
    "scripts\static-server.js",
    "templates\test-report-template.docx"
  )

  return $criticalFiles -contains $normalized
}

function Assert-FileExists {
  param(
    [string]$Path,
    [string]$Hint
  )

  if (-not (Test-Path $Path)) {
    throw "Missing required file: $Path ($Hint)"
  }
}

function Run-NpmAndAssert {
  param(
    [string]$Label,
    [scriptblock]$Block,
    [switch]$AllowFailure
  )

  Write-Host "[bootstrap] $Label"
  & $Block
  if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
    throw "Command failed: $Label (exit=$LASTEXITCODE)"
  }
}

Assert-Command -CommandName "node" -InstallUrl "https://nodejs.org/"
Assert-Command -CommandName "npm" -InstallUrl "https://nodejs.org/"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillRoot = Resolve-Path (Join-Path $scriptDir "..")
$templateRoot = Join-Path $skillRoot "assets\e2e-template"

if (-not (Test-Path $templateRoot)) {
  throw "Template directory not found: $templateRoot"
}

if (-not (Test-Path $ProjectPath)) {
  New-Item -ItemType Directory -Path $ProjectPath -Force | Out-Null
}

$projectRoot = Resolve-Path $ProjectPath
$targetE2e = Join-Path $projectRoot "e2e"
New-Item -ItemType Directory -Path $targetE2e -Force | Out-Null
$targetE2eFull = [System.IO.Path]::GetFullPath($targetE2e)

$copied = New-Object System.Collections.Generic.List[string]
$overwritten = New-Object System.Collections.Generic.List[string]
$syncedCritical = New-Object System.Collections.Generic.List[string]
$skipped = New-Object System.Collections.Generic.List[string]

$files = Get-ChildItem -Path $templateRoot -Recurse -File
foreach ($file in $files) {
  $relative = $file.FullName.Substring($templateRoot.Length).TrimStart('\')
  $targetFile = Join-Path $targetE2e $relative
  $targetFileFull = [System.IO.Path]::GetFullPath($targetFile)

  if (-not $targetFileFull.StartsWith($targetE2eFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refuse to write outside e2e directory: $targetFileFull"
  }

  $targetDir = Split-Path -Parent $targetFile
  New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

  $exists = Test-Path $targetFile
  $isCriticalTemplateFile = Test-IsCriticalTemplateFile -RelativePath $relative

  if ($exists -and -not $Force -and -not $isCriticalTemplateFile) {
    $skipped.Add($relative)
    continue
  }

  Copy-Item -Path $file.FullName -Destination $targetFile -Force
  if ($exists) {
    if ($isCriticalTemplateFile -and -not $Force) {
      $syncedCritical.Add($relative)
    }
    else {
      $overwritten.Add($relative)
    }
  } else {
    $copied.Add($relative)
  }
}

$envPath = Join-Path $targetE2e ".env"
$envExamplePath = Join-Path $templateRoot ".env.example"
$envMergeResult = Merge-MissingEnvLines -EnvPath $envPath -EnvExamplePath $envExamplePath
if ($envMergeResult -eq -1) {
  $copied.Add(".env")
}

$readmePath = Join-Path $targetE2e "README.md"
if (-not (Test-Path $readmePath)) {
  $defaultReadme = @'
# Playwright E2E Guide

Edit e2e/.env first (at least E2E_BASE_URL), then run:

```powershell
cd e2e
npm install
npx playwright install chromium
npm test
```
'@
  Set-Content -Path $readmePath -Value $defaultReadme -Encoding UTF8
  $copied.Add("README.md")
}

# Validate required files exist after injection.
Assert-FileExists -Path (Join-Path $targetE2e "package.json") -Hint "npm dependencies"
Assert-FileExists -Path (Join-Path $targetE2e "playwright.config.js") -Hint "Playwright config"
Assert-FileExists -Path (Join-Path $targetE2e "scripts\static-server.js") -Hint "local static server for auto web startup"
Assert-FileExists -Path (Join-Path $targetE2e "scripts\generate-case-from-spec.js") -Hint "simple 3-field case skeleton generator"
Assert-FileExists -Path (Join-Path $targetE2e "scripts\serial-node-readback.ps1") -Hint "serial node/readback runner"
Assert-FileExists -Path (Join-Path $targetE2e "index.html") -Hint "default demo page for bootstrap self-test"
Assert-FileExists -Path (Join-Path $targetE2e "TEST_CASE_SPEC.md") -Hint "solidified 3-field onboarding input template"
Assert-FileExists -Path (Join-Path $targetE2e "tests\demo.spec.js") -Hint "demo testcase"
Assert-FileExists -Path (Join-Path $targetE2e "tests\case-plan.js") -Hint "structured case plan for rich report fields"
Assert-FileExists -Path (Join-Path $targetE2e "tests\roaming-settings.spec.js") -Hint "template spec exercising structured case plan"
Assert-FileExists -Path (Join-Path $targetE2e "reporters\self-test-report-reporter.js") -Hint "DOCX reporter"
Assert-FileExists -Path (Join-Path $targetE2e "templates\test-report-template.docx") -Hint "DOCX template"

Write-Host "[bootstrap] target: $targetE2e"
Write-Host "[bootstrap] copied: $($copied.Count), overwritten: $($overwritten.Count), skipped: $($skipped.Count)"
if ($syncedCritical.Count -gt 0) {
  Write-Host "[bootstrap] synced critical template files: $($syncedCritical.Count)"
}
if ($envMergeResult -gt 0) {
  Write-Host "[bootstrap] .env appended missing keys: $envMergeResult"
}

if (-not $SkipInstall) {
  Push-Location $targetE2e
  try {
    Run-NpmAndAssert -Label "npm install" -Block { npm install }
    Run-NpmAndAssert -Label "npm ls @playwright/test jszip dotenv --depth=0" -Block {
      npm ls @playwright/test jszip dotenv --depth=0
    }

    if ($InstallBrowser) {
      Run-NpmAndAssert -Label "npx playwright install chromium" -Block {
        npx playwright install chromium
      }
    }
  }
  finally {
    Pop-Location
  }
}

if (-not $SkipSelfTest) {
  Push-Location $targetE2e
  try {
    Run-NpmAndAssert -Label "npm test -- --list" -Block { npm test -- --list }

    Run-NpmAndAssert -Label "npm test" -AllowFailure -Block { npm test }
    if ($LASTEXITCODE -ne 0) {
      Write-Host "[bootstrap] note: test run has failing cases, continue checking report artifacts."
    }
  }
  finally {
    Pop-Location
  }

  $htmlReportPath = Join-Path $targetE2e "playwright-report\index.html"
  if (-not (Test-Path $htmlReportPath)) {
    throw "Missing html report: $htmlReportPath"
  }

  $docDir = Join-Path $targetE2e "self-test-reports"
  $docCount = @(Get-ChildItem -Path $docDir -Filter *.docx -ErrorAction SilentlyContinue).Count
  if ($docCount -lt 1) {
    throw "Missing DOCX self-test report under: $docDir"
  }
}

Write-Host "[bootstrap] done"
Write-Host "Next steps:"
Write-Host "1) Fill e2e/.env (E2E_BASE_URL at minimum)"
Write-Host "2) Call in chat: use web-playwright-e2e-bootstrap to initialize e2e automation"
Write-Host "3) Run manually when needed: cd e2e && npm test"
