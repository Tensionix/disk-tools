param(
    [Parameter(Mandatory = $true)]
    [string]$PairName,

    [Parameter(Mandatory = $true)]
    [string]$PairsConfig
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $PairsConfig)) {
    Write-Host "[ERROR] Pair config was not found:"
    Write-Host $PairsConfig
    exit 1
}

try {
    $config = Get-Content -LiteralPath $PairsConfig -Raw | ConvertFrom-Json
} catch {
    Write-Host "[ERROR] Pair config could not be parsed:"
    Write-Host $PairsConfig
    exit 1
}

$pair = @($config.pairs) | Where-Object { $_.name -eq $PairName } | Select-Object -First 1
if (-not $pair) {
    Write-Host "[ERROR] Pair was not found: $PairName"
    exit 1
}

$source = [string]$pair.source
$target = [string]$pair.target

if ([string]::IsNullOrWhiteSpace($source)) {
    Write-Host "[ERROR] Pair source path is empty for: $PairName"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($target)) {
    Write-Host "[ERROR] Pair target path is empty for: $PairName"
    exit 1
}

if (-not (Test-Path -LiteralPath $source)) {
    Write-Host "[ERROR] Pair source path was not found:"
    Write-Host $source
    exit 1
}

try {
    $null = Get-Item -LiteralPath $source -ErrorAction Stop
} catch {
    Write-Host "[ERROR] Pair source path is not accessible:"
    Write-Host $source
    exit 1
}

try {
    if (Test-Path -LiteralPath $target) {
        $null = Get-Item -LiteralPath $target -ErrorAction Stop
    } else {
        $targetParent = Split-Path -Path $target -Parent
        if (-not [string]::IsNullOrWhiteSpace($targetParent) -and (Test-Path -LiteralPath $targetParent)) {
            $null = Get-Item -LiteralPath $targetParent -ErrorAction Stop
        }
    }
} catch {
    Write-Host "[ERROR] Pair target path is not accessible:"
    Write-Host $target
    exit 1
}

exit 0
