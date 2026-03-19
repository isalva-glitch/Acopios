# Guía de Instalación y Configuración

## ⚠️ IMPORTANTE: Docker es Requerido

El sistema Acopios está diseñado para ejecutarse con **Docker Desktop**.

## Opción 1: Instalar Docker Desktop (Recomendado)

### Pasos:

1. **Descargar Docker Desktop para Windows:**
   - Ir a: https://www.docker.com/products/docker-desktop
   - Descargar la versión para Windows
   - Tamaño: ~500 MB aprox

2. **Instalar Docker Desktop:**
   - Ejecutar el instalador descargado
   - Seguir el asistente de instalación
   - **IMPORTANTE**: Aceptar instalar WSL 2 si se solicita
   - Reiniciar el equipo si es necesario

3. **Iniciar Docker Desktop:**
   - Buscar "Docker Desktop" en el menú inicio
   - Ejecutar la aplicación
   - Esperar a que aparezca el ícono en la bandeja del sistema
   - Verificar que diga "Docker Desktop is running"

4. **Verificar instalación:**
   ```bash
   docker --version
   docker ps
   ```
   Ambos comandos deben funcionar sin errores

5. **Ejecutar el sistema:**
   - Doble clic en `iniciar_sistema.bat`
   - El sistema debería iniciar correctamente

## Opción 2: Ejecutar Sin Docker (Manual)

Si no deseas instalar Docker, puedes ejecutar los servicios manualmente:

### Requisitos:
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+

### Backend:

```bash
# 1. Instalar PostgreSQL y crear base de datos
createdb acopios

# 2. Instalar dependencias Python
cd backend
pip install -r requirements.txt

# 3. Configurar variables de entorno
# Editar .env con la URL de tu PostgreSQL local

# 4. Ejecutar migraciones
alembic upgrade head

# 5. Iniciar servidor
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend:

```bash
# 1. Instalar dependencias
cd frontend
npm install

# 2. Iniciar servidor de desarrollo
npm run dev
```

## Recomendación

**Opción 1 (Docker)** es la más simple y recomendada porque:
- ✅ No requiere instalar PostgreSQL, Python, Node.js manualmente
- ✅ Todo está preconfigurado
- ✅ Un solo comando para iniciar todo
- ✅ Entorno consistente y aislado

**Opción 2 (Manual)** requiere más configuración pero te da más control.

## Solución de Problemas

### Docker Desktop no inicia:
- Verificar que la virtualización esté habilitada en BIOS
- Verificar que WSL 2 esté instalado
- Reiniciar el equipo

### Error "WSL 2 installation is incomplete":
```bash
wsl --install
wsl --set-default-version 2
```

## ¿Necesitas ayuda?

Si tienes problemas con la instalación, avísame y te ayudo a resolverlos.
