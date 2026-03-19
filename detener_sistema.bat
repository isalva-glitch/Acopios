@echo off
REM ========================================
REM Sistema Acopios - Fontela Cristales
REM Script de Detencion
REM ========================================

echo.
echo ========================================
echo  DETENIENDO SISTEMA ACOPIOS
echo ========================================
echo.

echo Deteniendo contenedores...
docker-compose down

if errorlevel 1 (
    echo.
    echo ERROR: Fallo al detener los servicios
    pause
    exit /b 1
)

echo.
echo ========================================
echo  SISTEMA DETENIDO EXITOSAMENTE
echo ========================================
echo.

echo Para volver a iniciar: ejecute iniciar_sistema.bat
echo.
pause
