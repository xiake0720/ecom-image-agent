@echo off
setlocal

set HOST=1.12.37.94
set USER=ubuntu

set LOCAL_PG_PORT=15432
set LOCAL_REDIS_PORT=16379

set REMOTE_PG_HOST=127.0.0.1
set REMOTE_PG_PORT=15432
set REMOTE_REDIS_HOST=127.0.0.1
set REMOTE_REDIS_PORT=16379

echo.
echo ==========================================
echo   Opening SSH tunnel to %USER%@%HOST%
echo   PostgreSQL: 127.0.0.1:%LOCAL_PG_PORT% ^> %REMOTE_PG_HOST%:%REMOTE_PG_PORT%
echo   Redis:      127.0.0.1:%LOCAL_REDIS_PORT% ^> %REMOTE_REDIS_HOST%:%REMOTE_REDIS_PORT%
echo ==========================================
echo.
echo Keep this window open while developing.
echo Press Ctrl+C to close the tunnel.
echo.

ssh -N ^
  -o ServerAliveInterval=60 ^
  -o ServerAliveCountMax=3 ^
  -L %LOCAL_PG_PORT%:%REMOTE_PG_HOST%:%REMOTE_PG_PORT% ^
  -L %LOCAL_REDIS_PORT%:%REMOTE_REDIS_HOST%:%REMOTE_REDIS_PORT% ^
  %USER%@%HOST%

echo.
echo Tunnel closed.
pause
