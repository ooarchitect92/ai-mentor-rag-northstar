@echo off
setlocal enabledelayedexpansion
title AI Mentor - NorthStar Persistent Launcher

pushd "%~dp0"

echo ============================================
echo   AI Mentor RAG - NorthStar
echo ============================================
echo.

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker was not found on PATH.
    echo         Install Docker Desktop, then run this file again.
    goto :fail
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running.
    echo         Start Docker Desktop, wait until it reports "Running", then retry.
    goto :fail
)

if not exist ".env" (
    echo [SETUP] .env not found - creating it from .env.example
    copy /y ".env.example" ".env" >nul
    echo         Add NVIDIA_API_KEY / GEMINI_API_KEY and the WhatsApp values in .env,
    echo         then run this file again.
    goto :fail
)

rem Application code is copied into an immutable image. Rebuild by default so
rem dashboard/backend changes are always included; pass "no-build" only when
rem deliberately restarting the exact image that is already present locally.
set "BUILD_ARG=--build"
if /i "%~1"=="no-build" set "BUILD_ARG="
if /i "%~1"=="--no-build" set "BUILD_ARG="

rem Read APP_PORT from .env so the printed URL matches the real port.
set "APP_PORT=8000"
set "ADMIN_TOKEN="
set "WHATSAPP_APP_SECRET="
set "META_APP_SECRET="
set "WHATSAPP_VERIFY_TOKEN="
set "WHATSAPP_USE_MOCK=false"
set "WHATSAPP_WEBHOOK_CALLBACK_URL="
set "WHATSAPP_RELAY_TOKEN="
set "CLOUDFLARE_TUNNEL_TOKEN="
set "NORTHSTAR_PUBLIC_BASE_URL="
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
    if /i "%%a"=="APP_PORT" set "APP_PORT=%%b"
    if /i "%%a"=="ADMIN_TOKEN" set "ADMIN_TOKEN=%%b"
    if /i "%%a"=="WHATSAPP_APP_SECRET" set "WHATSAPP_APP_SECRET=%%b"
    if /i "%%a"=="META_APP_SECRET" set "META_APP_SECRET=%%b"
    if /i "%%a"=="WHATSAPP_VERIFY_TOKEN" set "WHATSAPP_VERIFY_TOKEN=%%b"
    if /i "%%a"=="WHATSAPP_USE_MOCK" set "WHATSAPP_USE_MOCK=%%b"
    if /i "%%a"=="WHATSAPP_WEBHOOK_CALLBACK_URL" set "WHATSAPP_WEBHOOK_CALLBACK_URL=%%b"
    if /i "%%a"=="WHATSAPP_RELAY_TOKEN" set "WHATSAPP_RELAY_TOKEN=%%b"
    if /i "%%a"=="CLOUDFLARE_TUNNEL_TOKEN" set "CLOUDFLARE_TUNNEL_TOKEN=%%b"
    if /i "%%a"=="NORTHSTAR_PUBLIC_BASE_URL" set "NORTHSTAR_PUBLIC_BASE_URL=%%b"
)

if "%ADMIN_TOKEN%"=="" (
    echo [ERROR] ADMIN_TOKEN is empty. Generate a long random value in .env first.
    goto :fail
)
if /i "%ADMIN_TOKEN%"=="change-me" (
    echo [ERROR] ADMIN_TOKEN still uses the insecure example value. Replace it in .env.
    goto :fail
)
if /i not "%WHATSAPP_USE_MOCK%"=="true" if "%WHATSAPP_RELAY_TOKEN%"=="" if "%WHATSAPP_APP_SECRET%%META_APP_SECRET%"=="" (
    echo [ERROR] WHATSAPP_APP_SECRET or META_APP_SECRET is required when no authenticated relay is configured.
    goto :fail
)
if /i not "%WHATSAPP_USE_MOCK%"=="true" if "%WHATSAPP_VERIFY_TOKEN%"=="" (
    echo [ERROR] WHATSAPP_VERIFY_TOKEN is required before opening a public tunnel.
    goto :fail
)
if /i "%WHATSAPP_VERIFY_TOKEN%"=="change-me-whatsapp" (
    echo [ERROR] WHATSAPP_VERIFY_TOKEN still uses the insecure example value.
    goto :fail
)

echo Starting containers. The very first run builds the image and takes a few minutes.
echo.
set "COMPOSE_PROFILE_ARGS="
if not "%CLOUDFLARE_TUNNEL_TOKEN%"=="" (
    if "%NORTHSTAR_PUBLIC_BASE_URL%"=="" (
        echo [ERROR] NORTHSTAR_PUBLIC_BASE_URL is required with CLOUDFLARE_TUNNEL_TOKEN.
        echo         Configure the hostname published by the named Cloudflare tunnel.
        goto :fail
    )
    set "COMPOSE_PROFILE_ARGS=--profile permanent-tunnel"
    docker compose stop public-tunnel >nul 2>&1
    echo Starting the persistent named Cloudflare tunnel.
) else (
    docker compose stop named-tunnel >nul 2>&1
    if not "%WHATSAPP_WEBHOOK_CALLBACK_URL%"=="" if not "%NORTHSTAR_PUBLIC_BASE_URL%"=="" (
        echo Preserving external WhatsApp callback and using the configured stable relay origin.
    ) else if not "%WHATSAPP_WEBHOOK_CALLBACK_URL%"=="" if "%WHATSAPP_RELAY_TOKEN%"=="" (
        echo Preserving external WhatsApp callback; no NorthStar relay is configured.
    ) else (
        set "COMPOSE_PROFILE_ARGS=--profile tunnel"
        echo [WARN] No CLOUDFLARE_TUNNEL_TOKEN is configured.
        echo        Starting a quick test tunnel; its hostname is not permanent.
    )
)
docker compose %COMPOSE_PROFILE_ARGS% up -d %BUILD_ARG%
if errorlevel 1 (
    echo.
    echo [WARN] First attempt failed. Retrying once in 5 seconds - Docker Desktop
    echo        often loses DNS for a moment after a sleep/resume or VPN change.
    powershell -NoProfile -Command "Start-Sleep -Seconds 5" >nul 2>&1

    rem Do not force a rebuild on the retry: if the failure was a registry
    rem lookup, the already-built local image can still start just fine.
    docker compose %COMPOSE_PROFILE_ARGS% up -d
    if errorlevel 1 (
        echo.
        echo [ERROR] Containers failed to start. See the output above.
        echo.
        echo   If the error mentions registry-1.docker.io or "no such host",
        echo   Docker cannot reach the registry. Check your internet connection,
        echo   then restart Docker Desktop and run this file again.
        goto :fail
    )
)

echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\register_webhook.ps1"
if errorlevel 1 (
    echo [WARN] WhatsApp startup validation failed. Review the [FAIL] message above.
    echo        The chat UI still works, but WhatsApp delivery or replies may not.
)

echo.
echo   Chat UI    http://localhost:%APP_PORT%
echo   Admin       http://localhost:%APP_PORT%/admin/
echo   API docs   http://localhost:%APP_PORT%/docs
echo.
echo   The application is running persistently in the background.
echo   Closing this window will NOT stop it.
echo   Docker restart policies will restart the containers with Docker Desktop.
echo   To stop everything deliberately, run stop.bat.
echo ============================================
echo.
docker compose %COMPOSE_PROFILE_ARGS% ps
echo.
pause
popd
endlocal
exit /b 0

:fail
echo.
pause
popd
endlocal
exit /b 1
