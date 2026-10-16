# Requires PowerShell 7. Creates local credentials without printing them.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (Test-Path -LiteralPath '.env') { Write-Host '.env 已存在，保留原配置。'; exit 0 }
function New-OxSecret { [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)) }
$oxLines = @(
    'OXSTORE_VERSION=0.1.0-docker.1', 'COMPOSE_PROJECT_NAME=oxstore',
    'APP_BIND_ADDRESS=127.0.0.1', 'APP_PORT=8088',
    ('DB_PASSWORD=' + (New-OxSecret)), ('JWT_SECRET=' + (New-OxSecret)),
    ('TOKEN_LOOKUP_KEY=' + (New-OxSecret)), ('ADMIN_INITIAL_PASSWORD=Ox!' + (New-OxSecret)),
    'HISTORY_COMPLETE_SINCE='
)
[IO.File]::WriteAllLines((Join-Path $PSScriptRoot '.env'), $oxLines, [Text.UTF8Encoding]::new($false))
Write-Host '已生成 .env。管理员用户名为 admin；首次密码请在本地 .env 查看并妥善保存。'
