param(
    [Parameter(Mandatory = $true)]
    [string]$ReportDirectory,
    [double]$MaxReadP95Ms = 300,
    [double]$MaxSubmitP95Ms = 1000,
    [double]$MaxQueryP95Ms = 500,
    [double]$MaxErrorPct = 0
)

$statisticsPath = Join-Path $ReportDirectory "statistics.json"
if (-not (Test-Path -LiteralPath $statisticsPath -PathType Leaf)) {
    throw "JMeter statistics file not found: $statisticsPath"
}

$statistics = Get-Content -LiteralPath $statisticsPath -Raw | ConvertFrom-Json
$thresholds = @(
    [pscustomobject]@{
        Sampler = "Browse current product"
        MaxP95Ms = $MaxReadP95Ms
    },
    [pscustomobject]@{
        Sampler = "Submit unique buyer intent"
        MaxP95Ms = $MaxSubmitP95Ms
    },
    [pscustomobject]@{
        Sampler = "Query submitted intent"
        MaxP95Ms = $MaxQueryP95Ms
    }
)

$failures = @()
$results = foreach ($threshold in $thresholds) {
    $entryProperty = $statistics.PSObject.Properties[$threshold.Sampler]
    if ($null -eq $entryProperty) {
        throw "Sampler is missing from JMeter statistics: $($threshold.Sampler)"
    }

    $entry = $entryProperty.Value
    $p95 = [double]$entry.pct2ResTime
    $errorPct = [double]$entry.errorPct
    $passed = $p95 -le $threshold.MaxP95Ms -and $errorPct -le $MaxErrorPct

    if (-not $passed) {
        $failures += "$($threshold.Sampler): p95=${p95}ms (limit $($threshold.MaxP95Ms)ms), error=${errorPct}% (limit $MaxErrorPct%)"
    }

    [pscustomobject]@{
        Sampler = $threshold.Sampler
        Samples = $entry.sampleCount
        Errors = $entry.errorCount
        ErrorPct = $errorPct
        MeanMs = [math]::Round([double]$entry.meanResTime, 2)
        P95Ms = [math]::Round($p95, 2)
        P99Ms = [math]::Round([double]$entry.pct3ResTime, 2)
        LimitP95Ms = $threshold.MaxP95Ms
        Result = if ($passed) { "PASS" } else { "FAIL" }
    }
}

$totalProperty = $statistics.PSObject.Properties["Total"]
if ($null -eq $totalProperty) {
    throw "Total statistics entry is missing from JMeter report."
}

$total = $totalProperty.Value
if ([double]$total.errorPct -gt $MaxErrorPct) {
    $failures += "Total error rate is $($total.errorPct)% (limit $MaxErrorPct%)"
}

$results | Format-Table -AutoSize
Write-Output "Total samples: $($total.sampleCount); total errors: $($total.errorCount); error rate: $($total.errorPct)%"

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Output "SLA validation: PASS"
