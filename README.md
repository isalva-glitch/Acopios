# Sistema Acopios - Fontela Cristales

Sistema de gestión de acopios con procesamiento de PDFs asistido por IA para control de presupuestos, pedidos, entregas y contabilidad básica.

## Stack Tecnológico

- **Backend**: Python + FastAPI + SQLAlchemy + Alembic
- **Frontend**: React + TypeScript + Vite
- **Base de datos**: PostgreSQL
- **PDF Processing**: pdfplumber (con fallback a camelot/tabula)
- **Validación**: jsonschema (draft 2020-12)
- **Testing**: pytest
- **Deployment**: Docker + docker-compose

## Características Principales

- ✅ Alta de acopios desde PDF estándar con extracción automática de datos
- ✅ Control de consumo por m², ml y pesos (separando datos físicos de económicos)
- ✅ Gestión de pedidos y remitos (integración directa con base de datos SPF)
- ✅ Imputación de consumos con control de excedentes
- ✅ Anulación de imputaciones con recálculo automático de saldos
- ✅ Contabilidad mínima (anticipos, facturas, notas de crédito)
- ✅ Reportes de acopios activos, excedentes y vencimientos
- ✅ Validación automática con warnings

## Setup Rápido

### 1. Clonar el repositorio

```bash
git clone <repo-url>
cd Acopios
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus valores
```

### 3. Levantar el sistema con Docker

```bash
docker-compose up --build
```

El sistema estará disponible en:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Documentación API**: http://localhost:8000/docs

## Estructura del Proyecto

```
Acopios/
├── backend/
│   ├── models/           # Modelos SQLAlchemy
│   ├── routers/          # Endpoints FastAPI
│   ├── services/         # Lógica de negocio
│   ├── extraction/       # Motor de extracción de PDFs
│   ├── schemas/          # JSON Schemas de validación
│   ├── alembic/          # Migraciones de base de datos
│   ├── tests/            # Tests con pytest
│   └── main.py           # Aplicación principal
├── frontend/
│   ├── src/
│   │   ├── pages/        # Pantallas principales
│   │   ├── components/   # Componentes reutilizables
│   │   ├── api/          # Cliente HTTP
│   │   └── types/        # TypeScript types
│   └── package.json
└── docker-compose.yml
```

## API Endpoints

### Acopios
- `POST /acopios/upload-pdf` - Subir PDF de presupuesto
- `POST /acopios/confirm` - Confirmar y crear acopio
- `GET /acopios` - Listar acopios
- `GET /acopios/{id}` - Detalle de acopio

### Pedidos
- `POST /pedidos/upload-pdf` - Subir PDF de pedido
- `POST /pedidos/confirm` - Confirmar y crear pedido
- `GET /pedidos` - Listar pedidos (filtrable por obra)

### Imputaciones
- `POST /imputaciones` - Imputar consumo contra acopio
- `DELETE /imputaciones/{id}` - Anular imputación y restaurar saldos acopio

### Reportes
- `GET /reportes/acopios-activos` - Acopios con saldo
- `GET /reportes/excedentes` - Imputaciones excedentes
- `GET /reportes/vencimientos-precio` - Próximos vencimientos

## Testing

### Tests de Backend

```bash
cd backend
pytest tests/ -v
```

### Tests de Extracción con PDFs Fixture

```bash
pytest tests/test_extraction.py -v
```

## Desarrollo Local (sin Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Reglas de Negocio

1. Un acopio se crea desde uno o más presupuestos (PDF obligatorio)
2. Un acopio puede consumirse por múltiples pedidos
3. Control de consumo contra contratado (m², ml, $)
4. Política de excedentes configurable: BLOCK | WARN | ALLOW
5. Cambios de medidas son normales
6. Cambios de material/tipología se registran explícitamente

## JSON Schema

El sistema usa JSON Schema draft 2020-12 para validar la salida del extractor de PDFs antes de persistir en base de datos.

Schema location: `backend/schemas/acopio_package_schema.json`

## Licencia

Propiedad de Fontela Cristales
