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
- ✅ Motor de extracción híbrido (Tablas + Texto) para máxima fidelidad en documentos complejos
- ✅ Control de consumo por m², ml y pesos (separando datos físicos de económicos)
- ✅ Gestión de pedidos y remitos (integración directa con base de datos SPF)
- ✅ Seguimiento detallado por Obra y Cliente
- ✅ Imputación de consumos con control de excedentes
- ✅ Anulación de imputaciones con recálculo automático de saldos
- ✅ Gestión de Precios de Referencia (Base y Actual) para control de rentabilidad
- ✅ Panel de Procesos por Item (Templado, Laminado, Pulido, etc.) con guardado automático
- ✅ Autodetección inicial de procesos por item al crear el acopio, con edición manual posterior
- ✅ Módulo de Compensación de Procesos: Cálculo automático de diferencias entre cantidades acopiadas e imputadas por tipo de proceso, con valorización económica basada en precios de referencia.
- ✅ Interfaz de usuario optimizada (Alto contraste y scroll horizontal en tablas)
- ✅ Corrección de visibilidad de botones de acción en lista de acopios
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
- `GET /acopios/{id}/resumen-compensacion` - Resumen de compensacion de composiciones

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
7. Los procesos asociados a precios de referencia se interpretan solo durante el alta del acopio
8. Una vez creado el acopio, abrirlo o modificarlo no vuelve a reinterpretar procesos; los checks quedan bajo control manual
9. **Compensacion**: Se calculan las diferencias entre el total acopiado y el total imputado en pedidos para cada composicion. Las diferencias positivas y negativas se valorizan con precios de referencia y se totalizan por separado para obtener el saldo final.

## Resumen de Compensacion

El detalle del acopio incluye una tabla de compensacion por composicion. El calculo compara solo los pedidos efectivamente imputados al acopio contra las cantidades contratadas del acopio principal.

- `diferencia = cantidad_acopio - cantidad_pedidos_imputados`
- Las diferencias positivas suman al total positivo.
- Las diferencias negativas suman al total negativo.
- El saldo final es `total_positivo + total_negativo`.
- Las imputaciones nuevas guardan un snapshot de cantidades por composicion para mantener trazabilidad. Si una imputacion anterior no tiene snapshot, el sistema intenta reconstruir el desglose desde SPF.
- Los importes se muestran con formato argentino: `$ 1.234.567,89`.

## Procesos por Item

Durante el alta desde PDF o SPF, el sistema interpreta el detalle de cada item usando descripción, material, tipología, denominación de paños y adicionales. Con esa lectura inicial marca los procesos detectados en el panel del item.

La detección inicial no bloquea la operación manual: cualquier check puede marcarse o desmarcarse desde el detalle del acopio y ese valor queda persistido. Al volver a abrir el acopio no se reinterpreta el texto del item, para evitar que una decisión manual sea sobrescrita.

Reglas interpretativas principales:

- `DVH`, `doble vidriado` o `doble vidrio` marcan Vidrio Exterior, Vidrio Interior y Cámara Normal.
- `Cámara` sin especificar Normal, Estructural u Offset se interpreta como Cámara Normal.
- `Cámara Normal` explícita puede convivir con Cámara Estructural u Offset si también aparecen en el detalle.
- `Templado`, `Templada`, `Templados`, `Templadas` o `Temp` marcan Fasón Templado Exterior.
- El signo `+` separa partes del detalle, pero no crea procesos por sí mismo: solo se marcan procesos con palabras clave conocidas.
- Medidas o composiciones como `4+4` no marcan procesos si no incluyen una palabra clave de proceso.

Cada proceso toma la cantidad física correspondiente del item:

- Vidrio Exterior: m2
- Vidrio Interior: m2
- Cámara Estructural: ml
- Pulido: ml
- Fasón Templado Exterior: m2
- Pegado a Bastidor: ml
- Cámara Normal: ml
- Opacificado Perimetral: ml
- Opacificado Total: m2
- Cámara Offset: ml

## JSON Schema

El sistema usa JSON Schema draft 2020-12 para validar la salida del extractor de PDFs antes de persistir en base de datos.

Schema location: `backend/schemas/acopio_package_schema.json`

## Extracción Híbrida (V2)

El sistema implementa un motor de extracción de segunda generación que combina:
1. **Detección de Tablas**: Identifica la estructura visual del presupuesto.
2. **Parsing de Texto**: Recupera líneas que la detección de tablas puede omitir en documentos extensos o con formato irregular.
3. **Deduplicación Inteligente**: Utiliza algoritmos de conteo para asegurar que no se dupliquen filas ni se pierdan ítems, manteniendo la integridad de los totales.

## Licencia

Propiedad de Ivan Salva
