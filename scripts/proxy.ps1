[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Branch,

    [switch]$DryRun,

    [switch]$Confirm
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$utf8Encoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8Encoding
$OutputEncoding = $utf8Encoding

trap {
    Write-Host "ERROR | $($_.Exception.Message)"
    exit 1
}

function Open-ExclusiveLease {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$WaitSeconds = 0
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($WaitSeconds)
    do {
        try {
            return [IO.File]::Open(
                $Path,
                [IO.FileMode]::OpenOrCreate,
                [IO.FileAccess]::ReadWrite,
                [IO.FileShare]::None
            )
        }
        catch [IO.IOException] {
            if ([DateTime]::UtcNow -ge $deadline) {
                return $null
            }
            Start-Sleep -Milliseconds 500
        }
    } while ($true)
}

function Test-TcpPortAvailable {
    param([Parameter(Mandatory = $true)][int]$Port)

    $listener = $null
    try {
        $listener = [Net.Sockets.TcpListener]::new(
            [Net.IPAddress]::Loopback,
            $Port
        )
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $listener) {
            $listener.Stop()
        }
    }
}

function Get-LunitKeyNames {
    param([Parameter(Mandatory = $true)][string]$EnvFile)

    $candidates = [Collections.Generic.List[object]]::new()
    $seenValues = @{}
    foreach ($entry in [Environment]::GetEnvironmentVariables().GetEnumerator()) {
        $name = [string]$entry.Key
        $value = [string]$entry.Value
        if (
            $name -match "^LUNIT_FM_API_KEY(?:_[A-Za-z0-9_-]+)?$" -and
            -not [string]::IsNullOrWhiteSpace($value) -and
            -not $seenValues.ContainsKey($value)
        ) {
            $seenValues[$value] = $true
            $candidates.Add([pscustomobject]@{ Name = $name; Value = $value })
        }
    }
    if (Test-Path -LiteralPath $EnvFile -PathType Leaf) {
        foreach ($rawLine in [IO.File]::ReadAllLines($EnvFile)) {
            $line = $rawLine.Trim()
            if ($line -notmatch "^(LUNIT_FM_API_KEY(?:_[A-Za-z0-9_-]+)?)\s*=\s*(.*)$") {
                continue
            }
            $name = $matches[1]
            $value = $matches[2].Trim().Trim('"').Trim("'")
            if (
                -not [string]::IsNullOrWhiteSpace($value) -and
                -not $seenValues.ContainsKey($value)
            ) {
                $seenValues[$value] = $true
                $candidates.Add([pscustomobject]@{ Name = $name; Value = $value })
            }
        }
    }

    # A terminal can be killed while its Docker containers keep running. In
    # that case the file lease disappears, so also exclude credentials found
    # in active Daintlab candidate containers. Secret values stay in memory
    # and are never printed or written to metadata.
    $activeValues = @{}
    $containerIds = @(
        & docker ps --filter "name=daintlab-b-" --format "{{.ID}}" 2>$null
    )
    if ($LASTEXITCODE -eq 0) {
        foreach ($containerId in $containerIds) {
            $containerEnv = @(
                & docker inspect --format "{{range .Config.Env}}{{println .}}{{end}}" $containerId 2>$null
            )
            if ($LASTEXITCODE -ne 0) {
                continue
            }
            foreach ($line in $containerEnv) {
                if ($line -match "^LUNIT_FM_API_KEY=(.+)$") {
                    $activeValues[$matches[1]] = $true
                }
            }
        }
    }
    return @(
        $candidates |
            Where-Object { -not $activeValues.ContainsKey($_.Value) } |
            Sort-Object @{ Expression = { if ($_.Name -eq "LUNIT_FM_API_KEY") { 0 } else { 1 } } }, Name |
            ForEach-Object { $_.Name }
    )
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeRoot = Join-Path $repositoryRoot "eval\.runtime"
$envFile = Join-Path $repositoryRoot ".env"
$runner = Join-Path $PSScriptRoot "proxy-run.ps1"
[IO.Directory]::CreateDirectory($runtimeRoot) | Out-Null

$fetchLease = $null
$portLease = $null
$keyLease = $null
$selectedPort = $null
$selectedKeyName = $null

try {
    $fetchLease = Open-ExclusiveLease -Path (Join-Path $runtimeRoot "git-fetch.lock") -WaitSeconds 120
    if ($null -eq $fetchLease) {
        throw "Timed out waiting for another proxy process to finish git fetch."
    }
    Write-Host "Checking remote branch..."
    & git -C $repositoryRoot fetch --quiet origin --prune
    if ($LASTEXITCODE -ne 0) {
        throw "git fetch failed with exit code $LASTEXITCODE"
    }
    $fetchLease.Dispose()
    $fetchLease = $null

    $remoteCandidate = if ($Branch.StartsWith("origin/")) {
        $Branch
    }
    else {
        "origin/$Branch"
    }
    & git -C $repositoryRoot rev-parse --verify "$remoteCandidate^{commit}" *> $null
    if ($LASTEXITCODE -eq 0) {
        $resolvedRef = $remoteCandidate
    }
    else {
        & git -C $repositoryRoot rev-parse --verify "$Branch^{commit}" *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "Branch or commit '$Branch' could not be found after fetching origin."
        }
        $resolvedRef = $Branch
    }

    $branchName = $Branch -replace "^origin/", ""
    switch ($branchName) {
        "yh-submission" {
            $track = "benchmark"
            $versionPattern = "^(feat|fix|perf|refactor|test|docs|chore)\(benchmark/(B[0-9]{3})\):\s+\S.+$"
        }
        "yh-submission2" {
            $track = "frontier"
            $versionPattern = "^(feat|fix|perf|refactor|test|docs|chore)\(frontier/(F[0-9]{3})\):\s+\S.+$"
        }
        default {
            throw "Only yh-submission and yh-submission2 are supported candidate branches."
        }
    }
    $commitSubject = (& git -C $repositoryRoot log -1 --format=%s $resolvedRef).Trim()
    if ($LASTEXITCODE -eq 0 -and $commitSubject -match $versionPattern) {
        $Version = $matches[2]
    }
    else {
        $example = if ($track -eq "benchmark") {
            "perf(benchmark/B001): retrieval latency reduction"
        }
        else {
            "feat(frontier/F001): evidence synthesis strategy"
        }
        throw "Latest commit does not follow the candidate convention. Expected: $example"
    }

    foreach ($port in 8101..8199) {
        $candidateLease = Open-ExclusiveLease -Path (Join-Path $runtimeRoot "port-$port.lock")
        if ($null -eq $candidateLease) {
            continue
        }
        if (Test-TcpPortAvailable $port) {
            $portLease = $candidateLease
            $selectedPort = $port
            break
        }
        $candidateLease.Dispose()
    }
    if ($null -eq $portLease) {
        throw "No free local proxy port was found in the internal range 8101-8199."
    }

    $keyNames = @(Get-LunitKeyNames -EnvFile $envFile)
    if ($keyNames.Count -eq 0) {
        throw "No Lunit API key was found. Add LUNIT_FM_API_KEY=... to the root .env file."
    }
    foreach ($keyName in $keyNames) {
        $safeKeyName = $keyName -replace "[^A-Za-z0-9_.-]", "-"
        $candidateLease = Open-ExclusiveLease -Path (Join-Path $runtimeRoot "key-$safeKeyName.lock")
        if ($null -ne $candidateLease) {
            $keyLease = $candidateLease
            $selectedKeyName = $keyName
            break
        }
    }
    if ($null -eq $keyLease) {
        throw "All configured Lunit API keys are in use. Add another LUNIT_FM_API_KEY_N=... entry to .env."
    }

    $evaluationRunName = if ($Confirm) { "$Version-P32" } else { $Version }
    $evaluationSamples = if ($Confirm) { 32 } else { 16 }
    $evaluationSampling = if ($Confirm) { "coverage" } else { "representative" }

    Write-Host "[$evaluationRunName] PREPARING | $track | $resolvedRef"
    & $runner `
        -Ref $resolvedRef `
        -RunName $evaluationRunName `
        -Port $selectedPort `
        -LunitKeyEnv $selectedKeyName `
        -Samples $evaluationSamples `
        -Sampling $evaluationSampling `
        -GenerationConcurrency 2 `
        -JudgeConcurrency 8 `
        -Score `
        -DryRun:$DryRun
}
finally {
    if ($null -ne $fetchLease) {
        $fetchLease.Dispose()
    }
    if ($null -ne $portLease) {
        $portLease.Dispose()
    }
    if ($null -ne $keyLease) {
        $keyLease.Dispose()
    }
}
