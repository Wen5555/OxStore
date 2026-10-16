param(
    [Parameter(Mandatory=$true)][string]$BaseUrl,
    [string]$OutputDirectory = 'output/playwright'
)
# Run only on a dedicated test instance with no active product: this publishes a demo product and completes its transaction.
$ErrorActionPreference = 'Stop'
$oxPassword = Read-Host '隔离测试实例当前管理员密码' -MaskInput
$oxOutput = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $oxOutput -Force | Out-Null
$oxSession = 'oxstore-ui-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$oxImage = Join-Path $env:TEMP ($oxSession + '.png')
$oxScript = Join-Path $env:TEMP ($oxSession + '.js')
[IO.File]::WriteAllBytes($oxImage, [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII='))
$oxConfig = @{url=$BaseUrl.TrimEnd('/');password=$oxPassword;imageFile=$oxImage;evidenceDir=$oxOutput;pauseMs=1200} | ConvertTo-Json -Compress
$oxCode = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'docker_ui_smoke.js')).Replace('__OXSTORE_UI_CONFIG__', $oxConfig)
[IO.File]::WriteAllText($oxScript, $oxCode, [Text.UTF8Encoding]::new($false))
try {
    npx --yes --package '@playwright/cli@0.1.22' playwright-cli "-s=$oxSession" open about:blank --browser=chrome
    if ($LASTEXITCODE -ne 0) { throw 'Browser launch failed' }
    npx --yes --package '@playwright/cli@0.1.22' playwright-cli "-s=$oxSession" video-start (Join-Path $oxOutput 'docker-ui.webm') --size=1280x900
    npx --yes --package '@playwright/cli@0.1.22' playwright-cli "-s=$oxSession" run-code --filename $oxScript | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Real UI verification failed' }
} finally {
    npx --yes --package '@playwright/cli@0.1.22' playwright-cli "-s=$oxSession" video-stop
    npx --yes --package '@playwright/cli@0.1.22' playwright-cli "-s=$oxSession" close
    Remove-Item -LiteralPath $oxScript,$oxImage -ErrorAction SilentlyContinue
}
