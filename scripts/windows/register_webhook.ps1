# Registers the Ziplin Meta app directly against NorthStar's signed webhook.
# A configured permanent callback is preferred. In non-production environments
# only, the script can discover a cloudflared quick-tunnel URL for a temporary
# end-to-end test.
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

function Get-GraphCollection([string]$initialUrl, [hashtable]$headers) {
    $items = @()
    $nextUrl = $initialUrl
    $pages = 0
    while ($nextUrl) {
        $pages += 1
        if ($pages -gt 100) { throw 'Meta pagination exceeded the safety limit.' }
        $page = Invoke-RestMethod -Uri $nextUrl -Headers $headers -TimeoutSec 30
        $items += @($page.data)
        $nextUrl = [string]$page.paging.next
    }
    return $items
}

function Test-DnsCallbackHost([Uri]$uri) {
    $hostName = $uri.DnsSafeHost.TrimEnd('.').ToLowerInvariant()
    if (-not $hostName -or -not $hostName.Contains('.')) { return $false }
    if ($hostName -eq 'localhost' -or $hostName.EndsWith('.localhost') -or $hostName.EndsWith('.local')) {
        return $false
    }
    $parsedAddress = $null
    if ([System.Net.IPAddress]::TryParse($hostName, [ref]$parsedAddress)) { return $false }
    return $true
}

$env_values = Read-DotEnv (Join-Path $repoRoot '.env')

$appId     = if ($env_values['META_APP_ID']) { $env_values['META_APP_ID'] } else { $env_values['FACEBOOK_APP_ID'] }
$appSecret = if ($env_values['WHATSAPP_APP_SECRET']) { $env_values['WHATSAPP_APP_SECRET'] } else { $env_values['META_APP_SECRET'] }
$verifyToken = $env_values['WHATSAPP_VERIFY_TOKEN']
$accessToken = if ($env_values['WHATSAPP_ACCESS_TOKEN']) { $env_values['WHATSAPP_ACCESS_TOKEN'] } else { $env_values['WHATSAPP_TOKEN'] }
$phoneNumberId = $env_values['WHATSAPP_PHONE_NUMBER_ID']
$wabaId = $env_values['WHATSAPP_BUSINESS_ACCOUNT_ID']
$configuredCallback = $env_values['WHATSAPP_WEBHOOK_CALLBACK_URL']
$publicBaseUrl = $env_values['NORTHSTAR_PUBLIC_BASE_URL']
$appEnvironment = $env_values['APP_ENVIRONMENT']
$graphBase = $env_values['WHATSAPP_GRAPH_BASE']
if (-not $graphBase) {
    $version = if ($env_values['WHATSAPP_GRAPH_API_VERSION']) { $env_values['WHATSAPP_GRAPH_API_VERSION'] } else { 'v25.0' }
    $graphBase = "https://graph.facebook.com/$version"
}
$graphBase = $graphBase.TrimEnd('/')

if (-not $verifyToken) {
    Write-Host '[FAIL] Direct Ziplin registration requires WHATSAPP_VERIFY_TOKEN.' -ForegroundColor Red
    exit 1
}

if (-not $appId -or -not $appSecret) {
    Write-Host '[FAIL] Direct Ziplin registration requires META_APP_ID and WHATSAPP_APP_SECRET.' -ForegroundColor Red
    exit 1
}
if (-not $accessToken -or -not $phoneNumberId -or -not $wabaId) {
    Write-Host '[FAIL] Direct Ziplin registration requires the system-user token, Phone Number ID, and WABA ID.' -ForegroundColor Red
    exit 2
}

# Validate all system-user authorization before mutating the app callback.
$preflightStage = 'token permission lookup'
try {
    $systemHeaders = @{ Authorization = "Bearer $accessToken" }
    $permissions = Invoke-RestMethod -Uri "$graphBase/me/permissions" -Headers $systemHeaders -TimeoutSec 30
    $grantedScopes = @($permissions.data | Where-Object { $_.status -eq 'granted' } | ForEach-Object { $_.permission })
    foreach ($requiredScope in @('whatsapp_business_messaging', 'whatsapp_business_management')) {
        if ($grantedScopes -notcontains $requiredScope) {
            throw "The system-user token is missing $requiredScope."
        }
    }
    $preflightStage = 'Phone Number ID authorization'
    Invoke-RestMethod -Uri "$graphBase/$phoneNumberId`?fields=id" -Headers $systemHeaders -TimeoutSec 30 | Out-Null
    $preflightStage = 'WABA phone ownership lookup'
    $phoneNumbers = Get-GraphCollection "$graphBase/$wabaId/phone_numbers?fields=id" $systemHeaders
    $wabaPhoneIds = @($phoneNumbers | ForEach-Object { [string]$_.id })
    if ($wabaPhoneIds -notcontains [string]$phoneNumberId) {
        throw 'The configured Phone Number ID does not belong to the configured WABA.'
    }
} catch {
    Write-Host '[FAIL] Meta rejected the Ziplin system-user/WABA preflight.' -ForegroundColor Red
    Write-Host "       Failed during: $preflightStage"
    exit 2
}
Write-Host '[OK] Ziplin outbound token, Phone Number ID, and WABA authorization passed.' -ForegroundColor Green

if ($configuredCallback) {
    $callbackUrl = $configuredCallback
    try { $callbackUri = [Uri]$callbackUrl } catch {
        Write-Host '[FAIL] WHATSAPP_WEBHOOK_CALLBACK_URL is not a valid URL.' -ForegroundColor Red
        exit 1
    }
    if (-not $callbackUri.IsAbsoluteUri) {
        Write-Host '[FAIL] WHATSAPP_WEBHOOK_CALLBACK_URL must be an absolute HTTPS URL.' -ForegroundColor Red
        exit 1
    }
    $tunnelUrl = $callbackUri.GetLeftPart([System.UriPartial]::Authority)
} else {
    if ($appEnvironment -and $appEnvironment.ToLowerInvariant() -eq 'production') {
        Write-Host '[FAIL] Production requires WHATSAPP_WEBHOOK_CALLBACK_URL on a permanent HTTPS hostname.' -ForegroundColor Red
        exit 1
    }
    Write-Host 'Waiting for the temporary public test tunnel...'
    $tunnelUrl = if ($publicBaseUrl) { $publicBaseUrl.TrimEnd('/') } else { Get-TunnelUrl }
    if (-not $tunnelUrl) {
        Write-Host '[FAIL] No public tunnel URL appeared in the cloudflared logs.' -ForegroundColor Red
        Write-Host '       Check: docker compose logs public-tunnel'
        exit 1
    }
    $callbackUrl = "$tunnelUrl/v1/whatsapp/ziplin/webhook"
    $callbackUri = [Uri]$callbackUrl
}

if (-not $callbackUri.IsAbsoluteUri -or $callbackUri.Scheme.ToLowerInvariant() -ne 'https') {
    Write-Host '[FAIL] Meta requires an HTTPS WhatsApp callback.' -ForegroundColor Red
    exit 1
}
if ($callbackUri.AbsolutePath -cne '/v1/whatsapp/ziplin/webhook') {
    Write-Host '[FAIL] WHATSAPP_WEBHOOK_CALLBACK_URL must use the exact direct Ziplin path.' -ForegroundColor Red
    Write-Host '       Expected path: /v1/whatsapp/ziplin/webhook'
    exit 1
}
if ($callbackUri.Query -or $callbackUri.Fragment -or $callbackUri.UserInfo) {
    Write-Host '[FAIL] The direct callback must not contain credentials, a query, or a fragment.' -ForegroundColor Red
    exit 1
}
if (-not $callbackUri.IsDefaultPort -and $callbackUri.Port -ne 443) {
    Write-Host '[FAIL] The production callback must use the standard HTTPS port.' -ForegroundColor Red
    exit 1
}
$callbackHost = $callbackUri.DnsSafeHost.TrimEnd('.').ToLowerInvariant()
if (-not (Test-DnsCallbackHost $callbackUri)) {
    Write-Host '[FAIL] The callback must use a permanent DNS hostname, not a local or literal IP address.' -ForegroundColor Red
    exit 1
}
$temporaryCallback = $callbackHost.EndsWith('.trycloudflare.com')
if ($temporaryCallback -and $appEnvironment -and $appEnvironment.ToLowerInvariant() -eq 'production') {
    Write-Host '[FAIL] Production cannot register a temporary trycloudflare.com callback.' -ForegroundColor Red
    exit 1
}
if ($temporaryCallback) {
    Write-Host '[WARN] This is a temporary test callback and will change after the tunnel restarts.' -ForegroundColor Yellow
}
if (-not (Wait-ForTunnel $tunnelUrl)) {
    Write-Host "[FAIL] $tunnelUrl did not serve /ready in time - Meta was not changed." -ForegroundColor Red
    exit 1
}

$registrationStage = 'local callback challenge'
try {
    $appHeaders = @{ Authorization = "Bearer $appId|$appSecret" }
    $challenge = 'NORTHSTAR_WEBHOOK_OK'
    $verifyUrl = "$callbackUrl`?hub.mode=subscribe&hub.verify_token=$([uri]::EscapeDataString($verifyToken))&hub.challenge=$challenge"
    $verification = Invoke-WebRequest -Uri $verifyUrl -TimeoutSec 30 -UseBasicParsing
    if ($verification.StatusCode -ne 200 -or $verification.Content -ne $challenge) {
        throw 'NorthStar did not return the expected verification challenge.'
    }
    $registrationStage = 'Meta app callback registration'
    $response = Invoke-RestMethod -Method Post -Uri "$graphBase/$appId/subscriptions" -Headers $appHeaders -TimeoutSec 60 -Body @{
        object = 'whatsapp_business_account'; callback_url = $callbackUrl; verify_token = $verifyToken
        fields = 'messages'; include_values = 'true'
    }
    if (-not $response.success) { throw 'Meta did not accept the webhook registration.' }
    $registrationStage = 'Meta app callback verification'
    $subscriptions = Get-GraphCollection "$graphBase/$appId/subscriptions" $appHeaders
    $activeSubscription = $subscriptions | Where-Object { $_.object -eq 'whatsapp_business_account' } | Select-Object -First 1
    $active = $activeSubscription.callback_url
    if ($active -ne $callbackUrl) { throw "Meta reports a different active callback: $active" }
    $activeFields = @($activeSubscription.fields | ForEach-Object {
        if ($_ -is [string]) { $_ } else { [string]$_.name }
    })
    if ($activeFields -notcontains 'messages') {
        throw 'The active WhatsApp subscription does not include the messages field.'
    }
    $registrationStage = 'Ziplin WABA app subscription'
    $wabaSubscription = Invoke-RestMethod -Method Post -Uri "$graphBase/$wabaId/subscribed_apps" -Headers $systemHeaders -TimeoutSec 30
    if (-not $wabaSubscription.success) { throw 'Meta did not subscribe the Ziplin app to the WABA.' }
    $subscribedApps = Get-GraphCollection "$graphBase/$wabaId/subscribed_apps" $systemHeaders
    $subscribedAppIds = @(
        $subscribedApps |
            ForEach-Object { [string]$_.whatsapp_business_api_data.id } |
            Where-Object { $_ }
    )
    if ($subscribedAppIds -notcontains [string]$appId) {
        throw 'The Ziplin Meta app is not present in the WABA subscribed-app list.'
    }
    $unexpectedAppIds = @($subscribedAppIds | Where-Object { $_ -and $_ -ne [string]$appId })
    if ($unexpectedAppIds.Count -gt 0) {
        throw 'An unexpected Meta app is also subscribed to the Ziplin WABA; remove it before cutover.'
    }
} catch {
    Write-Host '[FAIL] Direct Ziplin webhook registration or verification failed.' -ForegroundColor Red
    Write-Host "       Failed during: $registrationStage"
    exit 1
}
Write-Host "[OK] Ziplin Meta app is registered directly: $callbackUrl" -ForegroundColor Green
exit 0
