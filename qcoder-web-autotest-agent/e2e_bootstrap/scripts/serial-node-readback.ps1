param(
  [string]$EnvFile = ".\.env",
  [switch]$SkipCredentials
)

$ErrorActionPreference = "Stop"

function Get-EnvMap {
  param([string]$Path)
  $map = @{}
  if (-not (Test-Path $Path)) {
    return $map
  }

  $lines = Get-Content -Path $Path -Encoding UTF8
  foreach ($line in $lines) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    if ($line.TrimStart().StartsWith("#")) { continue }
    $m = [regex]::Match($line, "^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
    if (-not $m.Success) { continue }
    $key = $m.Groups[1].Value.Trim()
    $val = $m.Groups[2].Value.Trim()
    $map[$key] = $val
  }
  return $map
}

function Get-Config {
  param(
    [hashtable]$Map,
    [string]$Key,
    [string]$Default = ""
  )
  if ($Map.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($Map[$Key])) {
    return $Map[$Key]
  }
  return $Default
}

function Read-Burst {
  param(
    [System.IO.Ports.SerialPort]$Port,
    [int]$WaitMs
  )
  Start-Sleep -Milliseconds $WaitMs
  try {
    return $Port.ReadExisting()
  } catch {
    return ""
  }
}

function Append-Log {
  param(
    [System.Text.StringBuilder]$Sb,
    [string]$Text
  )
  [void]$Sb.AppendLine($Text)
}

function Sanitize-Text {
  param(
    [string]$Text,
    [string[]]$Secrets
  )
  $safe = [string]$Text
  foreach ($s in $Secrets) {
    if (-not [string]::IsNullOrEmpty($s)) {
      $safe = $safe.Replace($s, "<hidden>")
    }
  }
  return $safe
}

$envMap = Get-EnvMap -Path $EnvFile

$portName = Get-Config -Map $envMap -Key "E2E_SERIAL_PORT" -Default "COM52"
$baudRate = [int](Get-Config -Map $envMap -Key "E2E_SERIAL_BAUD" -Default "115200")
$wakeEnters = [int](Get-Config -Map $envMap -Key "E2E_SERIAL_WAKE_ENTERS" -Default "2")
$stepWaitMs = [int](Get-Config -Map $envMap -Key "E2E_SERIAL_WAIT_MS" -Default "900")
$tailWaitMs = [int](Get-Config -Map $envMap -Key "E2E_SERIAL_TAIL_WAIT_MS" -Default "1200")

$level1User = Get-Config -Map $envMap -Key "E2E_SERIAL_LEVEL1_USER"
$level1Pass = Get-Config -Map $envMap -Key "E2E_SERIAL_LEVEL1_PASS"
$level2User = Get-Config -Map $envMap -Key "E2E_SERIAL_LEVEL2_USER"
$level2Pass = Get-Config -Map $envMap -Key "E2E_SERIAL_LEVEL2_PASS"
$enterCmd1 = Get-Config -Map $envMap -Key "E2E_SERIAL_ENTER_CMD_1" -Default "ddd"
$enterCmd2 = Get-Config -Map $envMap -Key "E2E_SERIAL_ENTER_CMD_2" -Default "ts"
$nodeReadCmd = Get-Config -Map $envMap -Key "E2E_SERIAL_NODE_READ_CMD"
$nodeReadbackCmd = Get-Config -Map $envMap -Key "E2E_SERIAL_NODE_READBACK_CMD"
$logPath = Get-Config -Map $envMap -Key "E2E_SERIAL_LOG_PATH" -Default ".\self-test-reports\serial-node-readback.log"
$credentialMode = (Get-Config -Map $envMap -Key "E2E_SERIAL_CREDENTIAL_MODE" -Default "auto").ToLower()
$secretWords = @($level1Pass, $level2Pass)

$parity = [System.IO.Ports.Parity]::None
$dataBits = 8
$stopBits = [System.IO.Ports.StopBits]::One
$serialPort = New-Object System.IO.Ports.SerialPort $portName, $baudRate, $parity, $dataBits, $stopBits
$serialPort.NewLine = "`r`n"
$serialPort.ReadTimeout = 1500
$serialPort.WriteTimeout = 1500
$serialPort.DtrEnable = $true
$serialPort.RtsEnable = $true

$sb = New-Object System.Text.StringBuilder

try {
  $serialPort.Open()
  Append-Log -Sb $sb -Text "=== OPENED $portName @$baudRate ==="
  Append-Log -Sb $sb -Text ("[boot]<< " + (Read-Burst -Port $serialPort -WaitMs 1000))

  $wakeSnapshot = ""
  for ($i = 1; $i -le $wakeEnters; $i += 1) {
    $serialPort.Write("`r`n")
    $resp = Read-Burst -Port $serialPort -WaitMs $stepWaitMs
    Append-Log -Sb $sb -Text "[wake_$i]>> <enter>"
    $safeWakeResp = Sanitize-Text -Text $resp -Secrets $secretWords
    Append-Log -Sb $sb -Text ("[wake_$i]<< " + $safeWakeResp)
    $wakeSnapshot += $safeWakeResp

    if ($safeWakeResp -match "(?i)login|username|password|Config#|/fhrom/fhshell #|#\s*$") {
      break
    }
  }

  $steps = New-Object System.Collections.Generic.List[object]
  $recentPrompt = $wakeSnapshot + (Sanitize-Text -Text (Read-Burst -Port $serialPort -WaitMs 200) -Secrets $secretWords)
  $alreadyInShell = $recentPrompt -match "Config#|/fhrom/fhshell #|#\s*$"
  $needLoginPrompt = $recentPrompt -match "(?i)login|username|password"
  $shouldUseCredentials = $false

  if ($credentialMode -eq "always") {
    $shouldUseCredentials = $true
  } elseif ($credentialMode -eq "never") {
    $shouldUseCredentials = $false
  } else {
    $shouldUseCredentials = $needLoginPrompt -or (-not $alreadyInShell)
  }

  if ($SkipCredentials) {
    $shouldUseCredentials = $false
  }

  if ($shouldUseCredentials) {
    if ($level1User) { $steps.Add(@{ name = "level1_user"; cmd = $level1User; secret = $false }) }
    if ($level1Pass) { $steps.Add(@{ name = "level1_pass"; cmd = $level1Pass; secret = $true }) }
    if ($level2User) { $steps.Add(@{ name = "level2_user"; cmd = $level2User; secret = $false }) }
    if ($level2Pass) { $steps.Add(@{ name = "level2_pass"; cmd = $level2Pass; secret = $true }) }
  } else {
    Append-Log -Sb $sb -Text "[credentials]>> skipped (mode=$credentialMode, prompt indicates shell ready)"
  }
  if ($enterCmd1) { $steps.Add(@{ name = "enter_cmd_1"; cmd = $enterCmd1; secret = $false }) }
  if ($enterCmd2) { $steps.Add(@{ name = "enter_cmd_2"; cmd = $enterCmd2; secret = $false }) }
  if ($nodeReadCmd) { $steps.Add(@{ name = "node_read"; cmd = $nodeReadCmd; secret = $false }) }
  if ($nodeReadbackCmd) { $steps.Add(@{ name = "node_readback"; cmd = $nodeReadbackCmd; secret = $false }) }

  foreach ($s in $steps) {
    $serialPort.Write("$($s.cmd)`r`n")
    $resp = Read-Burst -Port $serialPort -WaitMs $stepWaitMs
    $displayCmd = if ($s.secret) { "<hidden>" } else { $s.cmd }
    Append-Log -Sb $sb -Text ("[{0}]>> {1}" -f $s.name, $displayCmd)
    Append-Log -Sb $sb -Text ("[{0}]<< {1}" -f $s.name, (Sanitize-Text -Text $resp -Secrets $secretWords))
  }

  $tail = Read-Burst -Port $serialPort -WaitMs $tailWaitMs
  if ($tail) {
    Append-Log -Sb $sb -Text ("[tail]<< " + (Sanitize-Text -Text $tail -Secrets $secretWords))
  }
}
catch {
  Append-Log -Sb $sb -Text ("ERROR: " + $_.Exception.Message)
  throw
}
finally {
  if ($serialPort -and $serialPort.IsOpen) {
    $serialPort.Close()
  }

  $finalLog = $sb.ToString()
  $finalLog = Sanitize-Text -Text $finalLog -Secrets $secretWords
  New-Item -ItemType Directory -Path (Split-Path -Parent $logPath) -Force | Out-Null
  Set-Content -Path $logPath -Value $finalLog -Encoding UTF8
  Write-Output $finalLog
}
