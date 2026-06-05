# Sistema Acopios - Fontela Cristales

Sistema de gestión de acopios con procesamiento de PDFs asistido por IA para control de presupuestos, pedidos, entregas y contabilidad básica.

## Stack Tecnológico

- **Backend**: Python + FastAPI + SQLAlchemy + Alembic
- **Frontend**: React + TypeScript + Vite
- **Gráficos**: Recharts en la vista de Informes
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
- ✅ Panel de Procesos por Item (Templado, Laminado, Pulido, etc.) con guardado explícito
- ✅ Autodetección inicial de procesos por item al crear el acopio, con edición manual posterior
- ✅ Módulo de Compensación de Procesos: Cálculo automático de diferencias entre cantidades acopiadas e imputadas por tipo de proceso, con valorización económica basada en precios de referencia.
- ✅ Panel de Totales con métricas de m², ml y **Paños**: total contratado y saldo disponible visibles en todo momento
- ✅ Fecha de vencimiento obligatoria del acopio, editable manualmente desde Información General y persistida en base de datos
- ✅ Bloqueo de navegación ante cambios sin guardar: al intentar salir con cambios pendientes se solicita confirmación; los cambios se persisten en la base de datos únicamente al confirmar el guardado
- ✅ Interfaz de usuario optimizada (Alto contraste y scroll horizontal en tablas)
- ✅ Corrección de visibilidad de botones de acción en lista de acopios
- ✅ Contabilidad mínima (anticipos, facturas, notas de crédito)
- ✅ Vista Informes con KPIs, filtros avanzados, gráficos por obra/estado/tiempo, tabla ejecutiva y exportación CSV
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
- `PATCH /acopios/{id}` - Actualizar campos manuales obligatorios del acopio, incluyendo `fecha_vencimiento`
- `GET /acopios/{id}/resumen-compensacion` - Resumen de compensacion de composiciones

### Pedidos
- `POST /pedidos/upload-pdf` - Subir PDF de pedido
- `POST /pedidos/confirm` - Confirmar y crear pedido
- `GET /pedidos` - Listar pedidos (filtrable por obra)

### Imputaciones
- `POST /imputaciones` - Imputar consumo contra acopio
- `DELETE /imputaciones/{id}` - Anular imputación y restaurar saldos acopio

### Reportes / Informes
- `GET /reportes/acopios-activos` - Acopios con saldo
- `GET /reportes/excedentes` - Imputaciones excedentes
- `GET /reportes/vencimientos-precio` - Próximos vencimientos

## UX: Informes Ejecutivos

La ruta `/reportes` se presenta como **Informes**, un tablero operativo con gráficos Recharts cargado de forma diferida desde el frontend. Reutiliza los endpoints existentes y conserva la exportación CSV por informe.

- Carga automáticamente el informe seleccionado.
- Permite alternar entre Acopios activos, Excedentes y Vencimientos.
- Incluye buscador por obra, cliente, acopio o pedido.
- Agrega filtros por obra, cliente, estado y rango de fechas, con botón para limpiar filtros activos.
- Muestra KPIs de importe analizado, registros, m², ml y alertas.
- Grafica barras por obra, distribución por estado y línea temporal mensual del importe filtrado.
- Calcula una lectura rápida de concentración, promedio por registro, filtros aplicados y estado del tablero.
- Mantiene una tabla ejecutiva unificada para inspección operativa.

## UX: Fecha de Vencimiento del Acopio

El detalle `/acopios/:id` muestra en **Información General** un campo manual de tipo fecha para `fecha_vencimiento`.

- El campo se persiste en la tabla `acopios` mediante la migración `20260602_1000_c7a4d8e9f012_add_acopio_fecha_vencimiento`.
- La API devuelve `fecha_vencimiento` en listados y detalle, y permite actualizarla con `PATCH /acopios/{id}`.
- En la UI el ingreso es obligatorio: si la fecha queda vacía, se muestra un error y se bloquea el guardado de cambios.
- La columna de base de datos admite valores nulos para no inventar fechas en acopios existentes; la obligatoriedad se aplica al flujo manual del detalle.

## UX: Ancho de Acopios

El listado `/acopios` y el detalle `/acopios/:id` usan contenedores específicos para evitar barras de desplazamiento innecesarias en escritorio sin afectar alta de acopios ni otras pantallas.

- `/acopios` usa un contenedor más ancho y columnas compactas para que los saldos y acciones entren en la vista principal.
- `/acopios/:id` usa todo el ancho disponible y cortes responsivos para items, totales y consumos.
- Las tablas conservan scroll horizontal solo como respaldo cuando el contenido no puede reducirse más.

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
- Si un snapshot historico de pedido marca a la vez `camara_estructural` y `camara_offset` para una descripcion `Camara ... Estructural Offset`, el resumen lo trata como Camara Offset y no suma esos mismos ml a Camara Estructural.
- Los importes se muestran con formato argentino: `$ 1.234.567,89`.
- En la ventana de precios de referencia, los importes se editan aceptando `.` como separador decimal (ej. `1234.56`) y se muestran en formato argentino al salir del campo.
- En el detalle del acopio, el panel de resumen de compensacion queda al final de la pagina y contiene el acceso a precios de referencia en su encabezado.
- El panel de Totales y Saldos comparte seccion con Consumos Aplicados, para ver el total contratado, saldo disponible e imputaciones recientes sin perder el resumen de compensacion final.

## Normalizacion de Composiciones

La composicion del item es la clave para imputar pedidos contra el acopio. El numero de item del pedido no se toma como correspondencia confiable, porque puede cambiar entre presupuesto y pedido.

El sistema normaliza las descripciones de acopio y pedido antes de comparar:

- elimina diferencias de mayusculas, acentos, signos y separadores;
- ordena componentes para tolerar descripciones equivalentes con distinta ubicacion;
- unifica sinonimos y errores habituales como `extructural`, `bastidos`, `BP`, `TEM`, `Lam 3+3`;
- extrae procesos canonicos como vidrio exterior, vidrio interior, camara, pulido, templado, pegado y opacificados;
- registra cambios de material como eventos de `cambio_composicion`: ayudan a asignar el item correcto, pero no convierten materiales en equivalencias globales;
- calcula un score de similitud por composicion y procesos.

Al imputar un pedido SPF, cada item del pedido se asigna al item de acopio mas compatible por composicion. Si la composicion es equivalente, se imputa sin advertencia. Si hay diferencias de procesos, cambios de material o no se encuentra una composicion compatible, la imputacion queda marcada con advertencia para control comercial.

Cada imputacion persiste un snapshot de los metadatos de composicion del momento del alta:

| Campo | Descripcion |
|---|---|
| `pedido_item_descripcion` | Descripcion original del item en el pedido SPF |
| `composicion_normalizada` | Texto normalizado resultante del proceso de canonizacion |
| `composicion_match_estado` | Resultado del matching: `exacta`, `equivalente`, `cambio_composicion`, `sin_correspondencia` |
| `composicion_match_score` | Score Jaccard ponderado (0–1) entre composicion del pedido y del acopio |
| `composicion_advertencia` | Mensaje de advertencia si hubo diferencia de procesos o sin correspondencia |

Migration: `20260518_1100_2b6d8f4c1a90_add_imputacion_composicion_fields`

### Desviación de Proporciones en Imputaciones

Cuando un acopio se carga (vía PDF o sincronización), el saldo total de m² se calcula respecto a la cantidad de paños presupuestados, generando una proporción promedio (ej. 1.24 m² por paño). 
Al imputar un pedido de SPF, la aplicación descuenta directamente el consumo físico real que figura en las medidas del pedido. 

Si los pedidos fabricados incluyen paños con superficies **superiores al promedio original** del acopio (ej. paños de 1.80 m²), el consumo de m² será mucho más acelerado que el consumo de paños. Esto puede resultar en un saldo de m² negativo (excedente) aun cuando quede saldo positivo en la cantidad de paños. Este comportamiento no es un error de sumatoria ni de matching, sino el reflejo fiel de un mayor consumo de superficie respecto a la proyección comercial original.

## UX: Panel de Totales y Consumos Aplicados

El detalle del acopio combina **Totales y Saldos** con un resumen lateral de **Consumos Aplicados**:

- Totales muestra cantidad, m2, ml y pesos contratados contra saldo disponible.
- Consumos Aplicados lista cada imputacion con numero de pedido, importe, fecha del pedido y marca de excedente cuando corresponde.
- El total consumido se calcula desde las imputaciones visibles y el disponible reutiliza el saldo del acopio.
- Los remitos y facturas relacionados quedan en un bloque colapsable para control documental sin ocupar espacio permanente.
- La API de detalle expone `imputaciones[].fecha` desde la fecha del pedido SPF para mantener la cronologia visible en la UI.

## UX: Panel de Totales y Métricas de Paños

El panel **Total Items** en el detalle del acopio muestra, para cada ítem:

- **m²** y **ml**: total contratado con el saldo disponible entre paréntesis — ej. `150,00 m² (80,50)`.
- **Paños (N)**: cantidad total contratada de paños con el saldo entre paréntesis — ej. `Paños (12) → 8`.

El formato unifica la lectura de todas las magnitudes físicas en un mismo esquema visual.

## UX: Bloqueo de Navegación ante Cambios Pendientes

Cualquier pantalla que permita modificar datos del acopio (fecha de vencimiento, procesos por ítem, precios de referencia) utiliza un mecanismo de guardado explícito:

1. Los cambios se aplican localmente de forma optimista sin tocar la base de datos.
2. Un banner de **"Cambios sin guardar"** aparece en la parte superior indicando que hay modificaciones pendientes.
3. Si el usuario intenta navegar a otra página, se muestra un diálogo de confirmación.
4. Solo al confirmar el guardado los cambios se persisten en la base de datos vía API.
5. Al descartar, se restaura el estado original del acopio.

Esto evita pérdidas de datos accidentales y permite revisar cambios antes de confirmarlos.

## Procesos por Item

Durante el alta desde PDF o SPF, el sistema interpreta el detalle de cada item usando descripción, material, tipología, denominación de paños y adicionales. Con esa lectura inicial marca los procesos detectados en el panel del item.

La detección inicial no bloquea la operación manual: cualquier check puede marcarse o desmarcarse desde el detalle del acopio y ese valor queda persistido. Al volver a abrir el acopio no se reinterpreta el texto del item, para evitar que una decisión manual sea sobrescrita.

Reglas interpretativas principales:

- `DVH`, `doble vidriado` o `doble vidrio` marcan Vidrio Exterior, Vidrio Interior y Cámara Normal.
- `Cámara` sin especificar Normal, Estructural u Offset se interpreta como Cámara Normal.
- `Cámara Normal` explícita puede convivir con Cámara Estructural u Offset si también aparecen en el detalle.
- `Cámara ... Estructural Offset` se interpreta como Cámara Offset. No se marca también como Cámara Estructural, porque es una variante Offset y no dos procesos de cámara acumulables.
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

La cabecera del PDF se recupera desde tabla o desde texto compacto. Cuando la tabla omite la columna Empresa, el parser interpreta filas como `Empresa / Obra Contacto Estado Cotizado por Fecha` y separa cliente, obra y contacto sin confundir el contacto con el cliente. El estado `Ejecutado` también se reconoce como delimitador de cabecera.

## Licencia

Propiedad de Ivan Salva
