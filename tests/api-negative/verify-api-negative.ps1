param(
    [string]$BaseUrl = "http://127.0.0.1:8080"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http
$BaseUrl = $BaseUrl.TrimEnd("/")
$client = [System.Net.Http.HttpClient]::new()
$client.Timeout = [TimeSpan]::FromSeconds(10)
$results = [System.Collections.Generic.List[object]]::new()

function Invoke-ApiCase {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Path,
        [int]$ExpectedStatus,
        [string]$Body,
        [string]$Authorization
    )

    $request = [System.Net.Http.HttpRequestMessage]::new(
        [System.Net.Http.HttpMethod]::new($Method),
        "$BaseUrl$Path"
    )

    if (-not [string]::IsNullOrEmpty($Body)) {
        $request.Content = [System.Net.Http.StringContent]::new(
            $Body,
            [System.Text.Encoding]::UTF8,
            "application/json"
        )
    }

    if ($Authorization) {
        [void]$request.Headers.TryAddWithoutValidation("Authorization", $Authorization)
    }

    try {
        $response = $client.SendAsync($request).GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        $content = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $validEnvelope = $false

        try {
            $json = $content | ConvertFrom-Json
            $validEnvelope = (
                $json.code -eq $ExpectedStatus -and
                -not [string]::IsNullOrWhiteSpace([string]$json.message) -and
                $null -eq $json.data
            )
        } catch {
            $validEnvelope = $false
        }

        $passed = ($status -eq $ExpectedStatus -and $validEnvelope)
        $detail = "HTTP $status; error envelope " + $(if ($validEnvelope) { "valid" } else { "invalid" })
        $results.Add([pscustomobject]@{
            Test = $Name
            Expected = $ExpectedStatus
            Actual = $status
            Result = $(if ($passed) { "PASS" } else { "FAIL" })
            Detail = $detail
        })
    } finally {
        $request.Dispose()
        if ($null -ne $response) {
            $response.Dispose()
        }
    }
}

try {
    Invoke-ApiCase -Name "Admin API rejects missing JWT" -Method "GET" `
        -Path "/api/admin/products/current" -ExpectedStatus 401
    Invoke-ApiCase -Name "Admin API rejects malformed JWT" -Method "GET" `
        -Path "/api/admin/products/current" -ExpectedStatus 401 `
        -Authorization "Bearer invalid.token.value"
    Invoke-ApiCase -Name "Admin mutation rejects missing JWT" -Method "POST" `
        -Path "/api/admin/intents/999999999/start" -ExpectedStatus 401
    Invoke-ApiCase -Name "Intent submission rejects invalid phone" -Method "POST" `
        -Path "/api/intents" -ExpectedStatus 400 `
        -Body '{"buyerName":"ApiNegativeTest","buyerPhone":"123"}'
    Invoke-ApiCase -Name "Intent submission rejects missing phone" -Method "POST" `
        -Path "/api/intents" -ExpectedStatus 400 `
        -Body '{"buyerName":"ApiNegativeTest"}'
    Invoke-ApiCase -Name "Unknown token query is forbidden" -Method "GET" `
        -Path "/api/intents/INVALID_API_NEGATIVE_TEST_TOKEN" -ExpectedStatus 403
    Invoke-ApiCase -Name "Unknown token modification is forbidden" -Method "PUT" `
        -Path "/api/intents/INVALID_API_NEGATIVE_TEST_TOKEN" -ExpectedStatus 403 `
        -Body '{"buyerName":"Changed"}'
    Invoke-ApiCase -Name "Unknown token cancellation is forbidden" -Method "DELETE" `
        -Path "/api/intents/INVALID_API_NEGATIVE_TEST_TOKEN" -ExpectedStatus 403
    Invoke-ApiCase -Name "Unsupported method returns 405" -Method "PATCH" `
        -Path "/api/products/current" -ExpectedStatus 405 -Body "{}"
} finally {
    $client.Dispose()
}

$results | Format-Table -AutoSize
$failed = @($results | Where-Object { $_.Result -ne "PASS" })
"API negative checks: $($results.Count - $failed.Count) passed, $($failed.Count) failed."

if ($failed.Count -gt 0) {
    exit 1
}
