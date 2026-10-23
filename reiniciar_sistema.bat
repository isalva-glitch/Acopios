@echo off
cd /d "%~dp0"
REM ========================================
REM Sistema Acopios - Fontela Cristales
REM Script de Reinicio
REM ========================================

echo.
echo ========================================
echo  REINICIANDO SISTEMA ACOPIOS
echo ========================================
echo.

echo Reiniciando servicios...
docker-compose restart

if errorlevel 1 (
    echo.
    echo ERROR: Fallo al reiniciar los servicios
    pause
    exit /b 1
)

REM El conector se ejecuta en Windows, fuera de los contenedores.
echo Iniciando conexion con Access de Tango...
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0scripts\Start-TangoAccessBridge.ps1"
if errorlevel 1 (
    echo ADVERTENCIA: No se pudo iniciar el conector de Tango.
    echo Los comprobantes guardados siguen disponibles. Revise el registro de inicio del conector.
)
echo.

echo.
echo ========================================
echo  SISTEMA REINICIADO EXITOSAMENTE
echo ========================================
echo.
echo Servicios disponibles:
echo  - Frontend:      http://localhost:5173
echo  - Backend API:   http://localhost:8000
echo  - API Docs:      http://localhost:8000/docs
echo.
pause
