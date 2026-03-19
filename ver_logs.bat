@echo off
REM ========================================
REM Sistema Acopios - Fontela Cristales
REM Ver Logs de los Servicios
REM ========================================

echo.
echo ========================================
echo  LOGS DEL SISTEMA ACOPIOS
echo ========================================
echo.
echo Mostrando logs en tiempo real...
echo Presione Ctrl+C para salir
echo.

docker-compose logs -f
