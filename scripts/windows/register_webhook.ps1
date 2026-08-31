# Points the Meta app's WhatsApp webhook at the tunnel URL of the current run.
#
# docker-compose.yml uses a cloudflared *quick* tunnel, which is handed a new
# random *.trycloudflare.com hostname every time the stack starts. Meta keeps
# calling whatever URL was registered last, so after a restart the old URL is
# dead and no incoming message ever reaches the bot. This script reads the URL
# for the current run out of the tunnel's logs, waits until the API answers
# through it, and re-registers it on the app subscription.
#
# Run by start.bat on every launch. Safe to run by hand at any time.

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

function Read-DotEnv([string]$path) {
    $values = @{}
    if (-not (Test-Path $path)) { return $values }
    foreach ($line in Get-Content $path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        $split = $trimmed.IndexOf('=')
        if ($split -lt 1) { continue }
        $key = $trimmed.Substring(0, $split).Trim()
        $value = $trimmed.Substring($split + 1).Trim().Trim('"').Trim("'")
        $values[$key] = $value
    }
    return $values
}

function Get-TunnelUrl([int]$timeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $logs = docker compose logs --no-color public-tunnel 2>&1 | Out-String
        $matches = [regex]::Matches($logs, 'https://[a-z0-9-]+\.trycloudflare\.com')
        if ($matches.Count -gt 0) { return $matches[$matches.Count - 1].Value }
        Start-Sleep -Seconds 3
    }
    return $null
}

function Wait-ForTunnel([string]$baseUrl, [int]$timeoutSeconds = 120) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri "$baseUrl/ready" -TimeoutSec 10 -UseBasicParsing
            if ($response.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep -Seconds 3
    }
    return $false
}

$env_values = Read-DotEnv (Join-Path $repoRoot '.env')

$appId     = if ($env_values['META_APP_ID']) { $env_values['META_APP_ID'] } else { $env_values['FACEBOOK_APP_ID'] }
$appSecret = if ($env_values['WHATSAPP_APP_SECRET']) { $env_values['WHATSAPP_APP_SECRET'] } else { $env_values['META_APP_SECRET'] }
$verifyToken = $env_values['WHATSAPP_VERIFY_TOKEN']
$accessToken = if ($env_values['WHATSAPP_ACCESS_TOKEN']) { $env_values['WHATSAPP_ACCESS_TOKEN'] } else { $env_values['WHATSAPP_TOKEN'] }
$phoneNumberId = $env_values['WHATSAPP_PHONE_NUMBER_ID']
$configuredCallback = $env_values['WHATSAPP_WEBHOOK_CALLBACK_URL']
$relayToken = $env_values['WHATSAPP_RELAY_TOKEN']
$publicBaseUrl = $env_values['NORTHSTAR_PUBLIC_BASE_URL']
$graphBase = $env_values['WHATSAPP_GRAPH_BASE']
if (-not $graphBase) {
    $version = if ($env_values['WHATSAPP_GRAPH_API_VERSION']) { $env_values['WHATSAPP_GRAPH_API_VERSION'] } else { 'v25.0' }
    $graphBase = "https://graph.facebook.com/$version"
}
$graphBase = $graphBase.TrimEnd('/')
$routingFailure = $false

if (-not $verifyToken) {
    Write-Host '[SKIP] Webhook validation: WHATSAPP_VERIFY_TOKEN is not set in .env' -ForegroundColor Yellow
    exit 0
}

if ($configuredCallback) {
    $callbackUrl = $configuredCallback.TrimEnd('/')
    Write-Host "Validating the existing WhatsApp webhook without changing Meta: $callbackUrl"
    try {
        $separator = if ($callbackUrl.Contains('?')) { '&' } else { '?' }
        $challenge = 'NORTHSTAR_WEBHOOK_OK'
        $verifyUrl = "$callbackUrl$separator`hub.mode=subscribe&hub.verify_token=$([uri]::EscapeDataString($verifyToken))&hub.challenge=$challenge"
        $verification = Invoke-WebRequest -Uri $verifyUrl -TimeoutSec 30 -UseBasicParsing
        if ($verification.StatusCode -ne 200 -or $verification.Content -ne $challenge) {
            throw 'The existing callback did not return the verification challenge.'
        }
        if ($appId -and $appSecret) {
            $subscriptions = Invoke-RestMethod -Uri "$graphBase/$appId/subscriptions?access_token=$([uri]::EscapeDataString("$appId|$appSecret"))" -TimeoutSec 30
            $active = ($subscriptions.data | Where-Object { $_.object -eq 'whatsapp_business_account' }).callback_url
            if ($active -ne $callbackUrl) {
                throw "Meta reports a different active callback: $active"
            }
        } elseif (-not $relayToken) {
            throw 'META_APP_ID and META_APP_SECRET are required to validate a direct Meta callback.'
        } else {
            Write-Host '[INFO] Relay mode: callback challenge passed; Meta app-secret subscription inspection was skipped.' -ForegroundColor Yellow
        }
    } catch {
        Write-Host '[FAIL] Existing WhatsApp callback validation failed.' -ForegroundColor Red
        Write-Host "       $($_.Exception.Message)"
        exit 1
    }
    Write-Host "[OK] Existing WhatsApp webhook is active and preserved: $callbackUrl" -ForegroundColor Green
    if ($relayToken) {
        $tunnelUrl = if ($publicBaseUrl) { $publicBaseUrl.TrimEnd('/') } else { Get-TunnelUrl }
        if (-not $tunnelUrl -or -not (Wait-ForTunnel $tunnelUrl)) {
            Write-Host '[FAIL] The existing webhook relay is configured, but the NorthStar public tunnel is unavailable.' -ForegroundColor Red
            exit 1
        }
        $relayUri = [Uri]$tunnelUrl
        $relayHost = $relayUri.Host
        $stableRelay = (
            $publicBaseUrl -and
            $relayUri.Scheme -eq 'https' -and
            -not $relayHost.EndsWith('.trycloudflare.com', [StringComparison]::OrdinalIgnoreCase)
        )
        if (-not $stableRelay) {
            Write-Host '[FAIL] Ziplin relay ingress is temporary, not production-ready.' -ForegroundColor Red
            Write-Host '       Set NORTHSTAR_PUBLIC_BASE_URL to a permanent HTTPS origin and configure Xolox once.'
            $routingFailure = $true
        }
        Write-Host "[ACTION] Existing webhook must forward Ziplin POST payloads to: $tunnelUrl/v1/whatsapp/ziplin/relay" -ForegroundColor Yellow
        Write-Host '         Header: X-Ziplin-Relay-Token = WHATSAPP_RELAY_TOKEN from this .env' -ForegroundColor Yellow
    }
} else {
    if (-not $appId -or -not $appSecret) {
        Write-Host '[FAIL] Direct Meta registration requires META_APP_ID and META_APP_SECRET.' -ForegroundColor Red
        exit 1
    }
    Write-Host 'Waiting for the public tunnel...'
    $tunnelUrl = if ($publicBaseUrl) { $publicBaseUrl.TrimEnd('/') } else { Get-TunnelUrl }
    if (-not $tunnelUrl) {
        Write-Host '[FAIL] No trycloudflare URL appeared in the public-tunnel logs.' -ForegroundColor Red
        Write-Host '       Check: docker compose logs public-tunnel'
        exit 1
    }
    $callbackUrl = "$tunnelUrl/v1/whatsapp/ziplin/webhook"
    if (-not (Wait-ForTunnel $tunnelUrl)) {
        Write-Host "[FAIL] $tunnelUrl did not serve /ready in time - not registering." -ForegroundColor Red
        exit 1
    }
    try {
        $response = Invoke-RestMethod -Method Post -Uri "$graphBase/$appId/subscriptions" -TimeoutSec 60 -Body @{
            object = 'whatsapp_business_account'; callback_url = $callbackUrl; verify_token = $verifyToken
            fields = 'messages'; include_values = 'true'; access_token = "$appId|$appSecret"
        }
    } catch {
        Write-Host '[FAIL] Meta rejected the webhook registration.' -ForegroundColor Red
        Write-Host "       $($_.Exception.Message)"
        exit 1
    }
    if (-not $response.success) {
        Write-Host '[FAIL] Meta did not accept the webhook registration.' -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] WhatsApp webhook registered: $callbackUrl" -ForegroundColor Green
}

# Registration uses the app token and proves only that inbound delivery works.
# Validate the separate system-user token needed for outbound replies so a
# healthy start.bat window cannot misleadingly look like messaging is ready.
if (-not $accessToken -or -not $phoneNumberId) {
    Write-Host '[FAIL] Inbound webhook works, but outbound WhatsApp credentials are missing.' -ForegroundColor Red
    Write-Host '       Set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID in .env.'
    exit 2
}

try {
    $permissions = Invoke-RestMethod -Uri "$graphBase/me/permissions" -Headers @{ Authorization = "Bearer $accessToken" } -TimeoutSec 30
    $grantedScopes = @($permissions.data | Where-Object { $_.status -eq 'granted' } | ForEach-Object { $_.permission })
    if ($grantedScopes -notcontains 'whatsapp_business_messaging') {
        Write-Host '[FAIL] Inbound webhook works, but the access token cannot send WhatsApp replies.' -ForegroundColor Red
        Write-Host '       Generate a System User token with whatsapp_business_messaging and assign the WABA asset.'
        exit 2
    }
    Invoke-RestMethod -Uri "$graphBase/$phoneNumberId`?fields=id" -Headers @{ Authorization = "Bearer $accessToken" } -TimeoutSec 30 | Out-Null
} catch {
    Write-Host '[FAIL] Inbound webhook works, but Meta rejected the outbound token/Phone Number ID.' -ForegroundColor Red
    Write-Host '       Copy the token and Phone Number ID from WhatsApp > API Setup, then rerun start.bat.'
    exit 2
}

Write-Host '[OK] WhatsApp outbound token and Phone Number ID are authorized.' -ForegroundColor Green
if ($routingFailure) {
    Write-Host '[FAIL] Outbound authorization is healthy, but stable Ziplin inbound routing is not configured.' -ForegroundColor Red
    exit 3
}
exit 0
