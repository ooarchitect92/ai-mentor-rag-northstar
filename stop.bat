@echo off
rem Manual stop, in case the stack is still running (for example after a crash
rem or a forced shutdown of the launcher window).
setlocal
pushd "%~dp0"

echo Stopping AI Mentor containers...
docker compose --profile tunnel --profile permanent-tunnel down

echo.
docker compose ps
echo.
pause

popd
endlocal
