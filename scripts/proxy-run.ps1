[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Ref,

    [Parameter(Mandatory = $true)]
    [string]$RunName,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 65535)]
    [int]$Port,

    [ValidateRange(1, 10000)]
    [int]$Samples = 16,

    [ValidateRange(1, 100)]
    [int]$Repeats = 1,

    [ValidateRange(1, 100)]
    [int]$GenerationConcurrency = 2,

    [ValidateRange(1, 100)]
    [int]$JudgeConcurrency = 8,

    [ValidateRange(1, 3600)]
    [int]$TimeoutSeconds = 240,

    [ValidateRange(10, 600)]
    [int]$StartupTimeoutSeconds = 120,

    [ValidateSet("conquer_val", "consensus", "hard", "main")]
    [string]$Dataset = "conquer_val",

    [ValidateSet("balanced", "representative", "random")]
    [string]$Sampling = "representative",

    [int]$Seed = 0,

    [string]$Model,

    [string]$LunitKeyEnv = "LUNIT_FM_API_KEY",

    [string]$JudgeKeyEnv = "HEALTHBENCH_JUDGE_API_KEY",

    [string]$EnvFile = ".env",

    [string]$JudgeModel = "gpt-4.1",

    [string]$EvaluatorImage = "daintlab-b-eval:local",

    [string]$CandidateImage,

    [switch]$Score,

    [switch]$Fetch,

    [switch]$KeepContainer,

    [switch]$KeepWorktree,

    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
}

function Invoke-NativeQuiet {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $output = @(& $Command @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        $tail = ($output | Select-Object -Last 20) -join [Environment]::NewLine
        throw "Command failed with exit code ${LASTEXITCODE}: $Command`n$tail"
    }
}

function Get-SecretValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $processValue = [Environment]::GetEnvironmentVariable($Name)
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        return $processValue.Trim()
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ""
    }
    foreach ($rawLine in [IO.File]::ReadAllLines($Path)) {
        $line = $rawLine.Trim()
        if ($line -match "^$([regex]::Escape($Name))\s*=\s*(.*)$") {
            return $matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return ""
}

function Test-TcpPortAvailable {
    param([Parameter(Mandatory = $true)][int]$CandidatePort)

    $listener = $null
    try {
        $listener = [Net.Sockets.TcpListener]::new(
            [Net.IPAddress]::Loopback,
            $CandidatePort
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

function Get-SafeName {
    param([Parameter(Mandatory = $true)][string]$Value)

    $safe = ($Value -replace "[^A-Za-z0-9_.-]+", "-").Trim("-")
    if ([string]::IsNullOrWhiteSpace($safe)) {
        return "candidate"
    }
    return $safe
}

function Get-RepositoryRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootPrefix = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $fullPath = [IO.Path]::GetFullPath($Path)
    if ($fullPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        return $fullPath.Substring($rootPrefix.Length).Replace('\', '/')
    }
    return $fullPath
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$safeRunName = Get-SafeName $RunName
$safeImageName = $safeRunName.ToLowerInvariant()
$resolvedEnvFile = if ([IO.Path]::IsPathRooted($EnvFile)) {
    $EnvFile
}
else {
    Join-Path $repositoryRoot $EnvFile
}

if ($Fetch) {
    Invoke-Native git @("-C", $repositoryRoot, "fetch", "origin", "--prune")
}

$candidateSha = (& git -C $repositoryRoot rev-parse --verify "$Ref^{commit}" 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($candidateSha)) {
    throw "Cannot resolve candidate ref '$Ref'. Run with -Fetch if the remote ref is stale."
}
$candidateSha = $candidateSha.Trim()

if ([string]::IsNullOrWhiteSpace($CandidateImage)) {
    $CandidateImage = "daintlab-b-${safeImageName}:$($candidateSha.Substring(0, 12).ToLowerInvariant())"
}

$plan = [ordered]@{
    run_name = $RunName
    ref = $Ref
    candidate_sha = $candidateSha
    port = $Port
    samples = $Samples
    repeats = $Repeats
    generation_concurrency = $GenerationConcurrency
    judge_concurrency = if ($Score) { $JudgeConcurrency } else { $null }
    scored = [bool]$Score
    candidate_image = $CandidateImage
    evaluator_image = $EvaluatorImage
    lunit_key_env = $LunitKeyEnv
    judge_key_env = if ($Score) { $JudgeKeyEnv } else { $null }
    embedded_key_env_removed = $false
}

if ($DryRun) {
    $plan | ConvertTo-Json -Depth 5
    return
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required but was not found in PATH."
}
if (-not (Test-TcpPortAvailable $Port)) {
    throw "Host port $Port is already in use. Choose another -Port value."
}

$lunitKey = Get-SecretValue -Name $LunitKeyEnv -Path $resolvedEnvFile
if ([string]::IsNullOrWhiteSpace($lunitKey)) {
    throw "Candidate key '$LunitKeyEnv' was not found in the process environment or $resolvedEnvFile."
}
if ($lunitKey -match "[`r`n]") {
    throw "Candidate API key contains an invalid newline."
}
if ($Score) {
    $judgeKey = Get-SecretValue -Name $JudgeKeyEnv -Path $resolvedEnvFile
    if ([string]::IsNullOrWhiteSpace($judgeKey)) {
        throw "Judge key '$JudgeKeyEnv' was not found in the process environment or $resolvedEnvFile."
    }
}

$runtimeRoot = Join-Path $repositoryRoot "eval\.runtime"
$worktreeRoot = Join-Path $repositoryRoot ".worktrees\proxy-runs"
$resultRoot = Join-Path $repositoryRoot "eval\results\$safeRunName"
[IO.Directory]::CreateDirectory($runtimeRoot) | Out-Null
[IO.Directory]::CreateDirectory($worktreeRoot) | Out-Null
[IO.Directory]::CreateDirectory($resultRoot) | Out-Null

$uniqueSuffix = "$(Get-Date -Format 'yyyyMMddHHmmss')-$PID"
$worktreePath = Join-Path $worktreeRoot "$safeRunName-$uniqueSuffix"
$containerName = "daintlab-b-$safeImageName-$Port-$PID"
$candidateEnvFile = Join-Path $runtimeRoot "$containerName.env"
$evaluatorEnvFile = Join-Path $runtimeRoot "$containerName.judge.env"
$logPath = Join-Path $resultRoot "run-$uniqueSuffix.log"
$metadataPath = Join-Path $resultRoot "run-$uniqueSuffix.metadata.json"
$startedAt = [DateTime]::UtcNow
$containerStarted = $false
$worktreeCreated = $false
$evalExitCode = $null
$resultPath = $null
$failure = $null

try {
    Invoke-Native git @(
        "-C", $repositoryRoot, "worktree", "add", "--quiet", "--detach",
        $worktreePath, $candidateSha
    )
    $worktreeCreated = $true

    if (-not (Test-Path -LiteralPath (Join-Path $worktreePath "Dockerfile"))) {
        throw "Candidate ref '$Ref' has no root Dockerfile."
    }

    $candidateDockerfile = Join-Path $worktreePath "Dockerfile"
    $dockerfileLines = [IO.File]::ReadAllLines($candidateDockerfile)
    $safeDockerfileLines = @(
        $dockerfileLines | Where-Object {
            $_ -notmatch "^\s*ENV\s+LUNIT_FM_API_KEY\s*="
        }
    )
    if ($safeDockerfileLines.Count -ne $dockerfileLines.Count) {
        [IO.File]::WriteAllLines(
            $candidateDockerfile,
            $safeDockerfileLines,
            [Text.UTF8Encoding]::new($false)
        )
        $plan["embedded_key_env_removed"] = $true
    }

    Invoke-NativeQuiet docker @("build", "--quiet", "-t", $CandidateImage, $worktreePath)

    & docker image inspect $EvaluatorImage *> $null
    if ($LASTEXITCODE -ne 0) {
        Invoke-NativeQuiet docker @(
            "build", "--quiet", "-f", (Join-Path $repositoryRoot "eval\Dockerfile"),
            "-t", $EvaluatorImage, $repositoryRoot
        )
    }

    $candidateEnvLines = [Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $resolvedEnvFile -PathType Leaf) {
        foreach ($rawLine in [IO.File]::ReadAllLines($resolvedEnvFile)) {
            $line = $rawLine.Trim()
            if ($line -notmatch "^([A-Za-z_][A-Za-z0-9_]*)\s*=") {
                continue
            }
            $name = $matches[1]
            if (
                $name -ne "LUNIT_FM_API_KEY" -and
                $name -match "^(LUNIT_|DRIVER_|UPSTREAM_|REQUEST_|RETRIEVAL_|FINAL_|MCP_|MAX_|CITATION_)"
            ) {
                $candidateEnvLines.Add($line)
            }
        }
    }
    $candidateEnvLines.Add("LUNIT_FM_API_KEY=$lunitKey")
    [IO.File]::WriteAllLines(
        $candidateEnvFile,
        $candidateEnvLines,
        [Text.UTF8Encoding]::new($false)
    )
    if ($Score) {
        [IO.File]::WriteAllLines(
            $evaluatorEnvFile,
            @("$JudgeKeyEnv=$judgeKey"),
            [Text.UTF8Encoding]::new($false)
        )
    }

    $containerId = (& docker run --detach --rm --name $containerName `
        --env-file $candidateEnvFile -p "${Port}:8000" $CandidateImage)
    if ($LASTEXITCODE -ne 0) {
        throw "Candidate container failed to start."
    }
    $containerStarted = $true

    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-RestMethod `
                -Uri "http://127.0.0.1:$Port/v1/models" `
                -Method Get `
                -TimeoutSec 5
            if ($null -ne $response.data -and $response.data.Count -gt 0) {
                $ready = $true
                break
            }
        }
        catch {
            # The service can refuse connections while uvicorn is starting.
        }
        if (-not $ready) {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $ready) {
        Write-Warning "Candidate did not become ready. Recent container logs follow."
        & docker logs --tail 100 $containerName
        throw "Candidate readiness timed out after $StartupTimeoutSeconds seconds."
    }

    $repositoryMount = "${repositoryRoot}:/workspace"
    $containerOutputDir = "/workspace/eval/results/$safeRunName"
    $evalArguments = [Collections.Generic.List[string]]::new()
    @(
        "run", "--rm", "-v", $repositoryMount, "-w", "/workspace"
    ) | ForEach-Object { $evalArguments.Add($_) }
    if ($Score) {
        $evalArguments.Add("--env-file")
        $evalArguments.Add($evaluatorEnvFile)
    }
    @(
        $EvaluatorImage,
        "--endpoint", "http://host.docker.internal:$Port/v1",
        "--run-name", $RunName,
        "--candidate-sha", $candidateSha,
        "--dataset", $Dataset,
        "--sampling", $Sampling,
        "--samples", [string]$Samples,
        "--repeats", [string]$Repeats,
        "--seed", [string]$Seed,
        "--timeout", [string]$TimeoutSeconds,
        "--generation-concurrency", [string]$GenerationConcurrency,
        "--output-dir", $containerOutputDir,
        "--env-file", "/workspace/$EnvFile"
    ) | ForEach-Object { $evalArguments.Add($_) }
    if (-not [string]::IsNullOrWhiteSpace($Model)) {
        $evalArguments.Add("--model")
        $evalArguments.Add($Model)
    }
    if ($Score) {
        @(
            "--score",
            "--judge-model", $JudgeModel,
            "--judge-concurrency", [string]$JudgeConcurrency,
            "--judge-api-key-env", $JudgeKeyEnv
        ) | ForEach-Object { $evalArguments.Add($_) }
    }

    Write-Host "[$RunName] START | $($Samples * $Repeats) cases"
    & docker @evalArguments 2>&1 | Tee-Object -FilePath $logPath
    $evalExitCode = $LASTEXITCODE
    if ($evalExitCode -ne 0) {
        throw "Evaluator failed with exit code $evalExitCode. See $logPath"
    }

    $resultPath = Get-ChildItem -LiteralPath $resultRoot -Filter "*.json" |
        Where-Object { $_.Name -notlike "*.metadata.json" } |
        Where-Object { $_.LastWriteTimeUtc -ge $startedAt.AddSeconds(-2) } |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1 -ExpandProperty FullName
    if ([string]::IsNullOrWhiteSpace($resultPath)) {
        throw "Evaluation finished but no result JSON was found in $resultRoot."
    }
}
catch {
    $failure = $_
}
finally {
    $finishedAt = [DateTime]::UtcNow
    $metadata = [ordered]@{}
    foreach ($key in $plan.Keys) {
        $metadata[$key] = $plan[$key]
    }
    $metadata["started_at"] = $startedAt.ToString("o")
    $metadata["finished_at"] = $finishedAt.ToString("o")
    $metadata["wall_seconds"] = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
    $metadata["status"] = if ($null -eq $failure) { "complete" } else { "failed" }
    $metadata["evaluator_exit_code"] = $evalExitCode
    $metadata["result_file"] = if ($null -ne $resultPath) {
        Get-RepositoryRelativePath -Root $repositoryRoot -Path $resultPath
    }
    else {
        $null
    }
    $metadata["log_file"] = Get-RepositoryRelativePath -Root $repositoryRoot -Path $logPath
    if ($null -ne $failure) {
        $metadata["error"] = $failure.Exception.Message
    }
    [IO.File]::WriteAllText(
        $metadataPath,
        ($metadata | ConvertTo-Json -Depth 6),
        [Text.UTF8Encoding]::new($false)
    )

    if (Test-Path -LiteralPath $candidateEnvFile) {
        Remove-Item -LiteralPath $candidateEnvFile -Force
    }
    if (Test-Path -LiteralPath $evaluatorEnvFile) {
        Remove-Item -LiteralPath $evaluatorEnvFile -Force
    }
    if ($containerStarted -and -not $KeepContainer) {
        & docker stop $containerName *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Could not stop candidate container $containerName."
        }
    }
    if ($worktreeCreated -and -not $KeepWorktree) {
        $resolvedWorktreeRoot = [IO.Path]::GetFullPath($worktreeRoot).TrimEnd('\') + '\'
        $resolvedWorktreePath = [IO.Path]::GetFullPath($worktreePath)
        if (-not $resolvedWorktreePath.StartsWith($resolvedWorktreeRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Write-Warning "Refusing to remove unexpected worktree path: $resolvedWorktreePath"
        }
        else {
            & git -C $repositoryRoot worktree remove --force $resolvedWorktreePath *> $null
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Could not remove temporary worktree $resolvedWorktreePath."
            }
        }
    }
}

if ($null -ne $failure) {
    throw $failure
}
