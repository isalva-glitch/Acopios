@echo off
REM ========================================
REM Sistema Acopios - Fontela Cristales
REM Script de Inicio Automatico
REM ========================================

echo.
echo ========================================
echo  INICIANDO SISTEMA ACOPIOS
echo ========================================
echo.

REM Verificar que Docker Desktop este corriendo
echo [1/5] Verificando Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker no esta instalado o no esta en el PATH
    echo Por favor instale Docker Desktop desde https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

docker ps >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker Desktop no esta corriendo
    echo Por favor inicie Docker Desktop e intente nuevamente
    pause
    exit /b 1
)
echo Docker OK!
echo.

REM Verificar que existe el archivo .env
echo [2/5] Verificando configuracion...
if not exist ".env" (
    echo ADVERTENCIA: No existe archivo .env
    echo Creando .env desde .env.example...
    copy .env.example .env
    echo Archivo .env creado. Revise la configuracion si es necesario.
    echo.
)
echo Configuracion OK!
echo.

REM Detener contenedores previos si existen
echo [3/5] Limpiando contenedores previos...
docker-compose down >nul 2>&1
echo Limpieza completa!
echo.

REM Construir e iniciar los servicios
echo [4/5] Construyendo e iniciando servicios...
echo Esto puede tomar varios minutos la primera vez...
echo.
docker-compose up --build -d

if errorlevel 1 (
    echo.
    echo ERROR: Fallo al iniciar los servicios
    echo Revise los logs con: docker-compose logs
    pause
    exit /b 1
)
echo.

REM Esperar a que los servicios esten listos
echo [5/5] Esperando que los servicios esten listos...
timeout /t 15 /nobreak >nul

REM Verificar estado de los servicios
echo.
echo Estado de los servicios:
docker-compose ps
echo.

echo ========================================
echo  SISTEMA INICIADO EXITOSAMENTE
echo ========================================
echo.
echo Servicios disponibles:
echo  - Frontend:      http://localhost:5173
echo  - Backend API:   http://localhost:8000
echo  - API Docs:      http://localhost:8000/docs
echo  - PostgreSQL:    localhost:5432
echo.
echo Para ver logs:         docker-compose logs -f
echo Para detener:          docker-compose down
echo Para reiniciar:        docker-compose restart
echo.

REM Preguntar si desea abrir el navegador
set /p OPEN_BROWSER="Desea abrir el sistema en el navegador? (S/N): "
if /i "%OPEN_BROWSER%"=="S" (
    echo Abriendo navegador...
    start http://localhost:5173
)

echo.
echo Presione cualquier tecla para salir...
pause >nul
