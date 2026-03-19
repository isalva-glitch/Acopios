@echo off
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
