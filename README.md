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
- ✅ Acopio x Paquete de Obras: agrupación de varios presupuestos SPF en un paquete consolidado, creando un acopio operativo individual por presupuesto
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

El `docker-compose.yml` fija límites locales para estabilizar el entorno de desarrollo: `db` corre con `mem_limit: 768m` y `cpus: 1.0`, y `backend` con `mem_limit: 768m` y `cpus: 1.5`.

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

### Acopio x Paquete de Obras
- `POST /acopio-paquetes/upload-pdf` - Subir PDF de presupuesto para usarlo como fuente de un acopio hijo del paquete
- `POST /acopio-paquetes/preview` - Previsualizar presupuestos SPF antes de crear el paquete
- `POST /acopio-paquetes` - Crear paquete y acopios hijos
- `GET /acopio-paquetes` - Listar paquetes con totales consolidados
- `GET /acopio-paquetes/{id}` - Detalle de paquete con acopios hijos
- `PATCH /acopio-paquetes/{id}` - Actualizar datos generales del paquete sin modificar acopios hijos
- `POST /acopio-paquetes/{id}/presupuestos-pdf` - Agregar un acopio desde PDF a un paquete existente


### Pedidos
- `POST /pedidos/upload-pdf` - Subir PDF de pedido
- `POST /pedidos/confirm` - Confirmar y crear pedido
- `GET /pedidos` - Listar pedidos (filtrable por obra)

### Imputaciones
- `POST /imputaciones` - Imputar consumo contra acopio
- `DELETE /imputaciones/{id}` - Anular imputación y restaurar saldos acopio

### Aprendizaje de Procesos
- `GET /aprendizaje-procesos/correcciones` - Listar correcciones manuales registradas sobre procesos de items
- `GET /aprendizaje-procesos/reglas` - Listar reglas candidatas generadas desde correcciones manuales
- `POST /aprendizaje-procesos/reglas/{id}/simular` - Simular el impacto de una regla sobre items existentes antes de aprobarla
- `POST /aprendizaje-procesos/reglas/{id}/aprobar` - Aprobar una regla para que participe en nuevas inferencias
- `POST /aprendizaje-procesos/reglas/{id}/desactivar` - Desactivar una regla aprobada o candidata

### Reportes / Informes
- `GET /reportes/acopios-activos` - Acopios con saldo (soporta `incluir_paquetes: bool`)
- `GET /reportes/excedentes` - Imputaciones excedentes (retorna metadatos de paquetes, motivo y tipo de excedente)
- `GET /reportes/vencimientos-precio` - Próximos vencimientos (soporta `incluir_paquetes: bool` y retorno de `dias_restantes`)

## UX: Informes Ejecutivos

La ruta `/reportes` se presenta como **Informes**, un tablero operativo con gráficos Recharts cargado de forma diferida desde el frontend. Reutiliza los endpoints existentes y conserva la exportación CSV por informe.

- Carga automáticamente el informe seleccionado.
- Permite alternar entre Acopios activos, Excedentes y Vencimientos.
- Incluye buscador por obra, cliente, acopio o pedido.
- Agrega filtros por obra, cliente, estado y rango de fechas, con botón para limpiar filtros activos.
- Muestra KPIs de importe analizado, registros, m², ml y alertas.
- Distingue origen mediante badges interactivos (`📦 Paquete` vs `📄 Individual`) en la tabla ejecutiva.
- Resalta días restantes de vencimiento con código de color (alertas para vencimientos en 15 días o menos).
- Grafica barras por obra, distribución por estado y línea temporal mensual del importe filtrado.
- Calcula una lectura rápida de concentración, promedio por registro, filtros aplicados y estado del tablero.
- Mantiene una tabla ejecutiva unificada para inspección operativa con cabeceras dinámicas según KPI.

## UX: Acopio x Paquete de Obras

La ruta `/paquetes` lista paquetes de obras y consolida los totales de sus acopios hijos. La ruta `/paquetes/nuevo` permite ingresar varios presupuestos SPF, cargar PDFs de presupuestos que no existan en SPF, previsualizar las fuentes y crear un paquete con un acopio individual por presupuesto. La ruta `/paquetes/:id` muestra el resumen general, permite agregar nuevos presupuestos (desde SPF o PDF) y entrar al detalle normal de cada acopio hijo.

- El paquete es una entidad agrupadora en `acopio_paquetes`.
- Cada presupuesto SPF genera un `Acopio` normal, con items, saldos, imputaciones operativas, pedidos y precios de referencia existentes.
- Cada PDF cargado en el alta de paquete o desde el detalle del paquete reutiliza el extractor de acopios tradicionales y genera un `Acopio` normal con `origen_datos = pdf_upload`.
- `acopios.paquete_id` es nullable: los acopios tradicionales siguen funcionando sin paquete.
- Los totales del paquete se calculan a partir de los acopios hijos.
- El preview valida presupuestos repetidos, inexistentes, duplicados entre SPF/PDF o ya cargados como acopio.
- Si el presupuesto madre no existe en SPF, el paquete puede crearse inicialmente solo desde el PDF.
- Los comprobantes y recibos se gestionan en Documentación del acopio; el paquete muestra su consolidado.
- Los comprobantes se aplican contra `acopio_id`, no contra `paquete_id`; el paquete consolida las aplicaciones de sus acopios hijos.

## UX: Fecha de Vencimiento del Acopio

El detalle `/acopios/:id` muestra en **Información General** un campo manual de tipo fecha para `fecha_vencimiento`.

- El campo se persiste en la tabla `acopios` mediante la migración `20260602_1000_c7a4d8e9f012_add_acopio_fecha_vencimiento`.
- La API devuelve `fecha_vencimiento` en listados y detalle, y permite actualizarla con `PATCH /acopios/{id}`.
- En la UI el ingreso es obligatorio: si la fecha queda vacía, se muestra un error y se bloquea el guardado de cambios.
- El guardado de `fecha_vencimiento` es independiente de la matriz de precios de referencia: si el usuario solo cambia la fecha, no se validan ni guardan precios faltantes.
- La columna de base de datos admite valores nulos para no inventar fechas en acopios existentes; la obligatoriedad se aplica al flujo manual del detalle.

## Control de Excedentes

Las imputaciones nuevas y los datos históricos comparten la misma regla monetaria:

- Los importes se comparan con `Decimal` cuantizado a 2 decimales para evitar falsos positivos por ruido binario, por ejemplo `1128417.9000000001` contra `1128417.90`.
- Un exceso monetario real de un centavo sigue siendo excedente: por ejemplo `1128417.91` contra `1128417.90` se conserva como excedente de item o acopio segun corresponda.
- Los cálculos SPF acumulan m², ml e importes con `Decimal` y convierten a `float` recién al borde JSON.
- Las marcas históricas de `imputaciones.es_excedente` se recalculan desde los totales contratados del acopio/item antes de responder `GET /acopios/{id}`, `GET /pedidos/{id}` y `GET /reportes/excedentes`.
- El reporte de excedentes no lista una imputación marcada por una regla vieja si el recálculo actual determina que no hay excedente real.
- `imputaciones.excedente_motivo` usa tipo `Text` desde la migración `20260706_1326_b9b2f03f1d9f_change_excedente_motivo_to_text` para preservar motivos largos de recálculo y auditoría.

## UX: Ancho de Acopios y Filtros Visuales

El listado `/acopios` y el detalle `/acopios/:id` usan contenedores específicos para evitar barras de desplazamiento innecesarias en escritorio sin afectar alta de acopios ni otras pantallas.

- `/acopios` usa un contenedor más ancho y columnas compactas para que los saldos y acciones entren en la vista principal.
- Reemplaza el selector desplegable tradicional por botones interactivos de filtrado rápido por estado (`Todos`, `Activo`, `Pendiente`, `Parcialmente Consumido`, `Consumido`, `Cancelado`).
- `/acopios/:id` usa todo el ancho disponible y cortes responsivos para items, totales y consumos.
- Las tablas conservan scroll horizontal solo como respaldo cuando el contenido no puede reducirse más.

## Testing

### Tests de Backend

```bash
cd backend
pytest tests/ -v
```

Los tests usan SQLite en `/tmp/test.db` para evitar ensuciar el árbol del repo con archivos de base temporales.

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
10. Un paquete de obras agrupa uno o varios acopios, pero no reemplaza al acopio como unidad operativa
11. Un acopio puede pertenecer a cero o un paquete
12. Los acopios hijos conservan estado operativo propio y se gestionan desde el detalle normal de acopio
13. El paquete tiene estado propio y datos generales editables
14. Los recibos de pago se aplican a acopios individuales para servir tanto a acopios tradicionales como a paquetes

### Imputacion desde SPF: ajuste comercial por item

Al imputar desde SPF, el porcentaje del presupuesto de origen se aplica con su
signo: negativo es descuento y positivo es incremento. Un porcentaje nulo o cero
no modifica el subtotal. Se utiliza el porcentaje del pedido de origen, aunque
el acopio destino corresponda a otro presupuesto.

- Subtotal del item = suma de `item_medidas.total_item` + adicionales
  (`total_complemento × cantidad`).
- Importe final del item = subtotal × (1 + `porcentaje_presupuesto` / 100).
- Se redondea cada item a centavos (ROUND_HALF_UP); el total del pedido es la
  suma de esos importes, los mismos que se guardan en `cantidad_pesos`.
- El ajuste se aplica una sola vez en el servicio SPF compartido por la vista
  previa y la confirmacion. Las cantidades fisicas y los procesos no cambian.
- La vista previa muestra subtotal, porcentaje con signo, ajuste e importe final.
  Los precios de referencia del acopio no reemplazan este calculo.
- Las imputaciones historicas no se recalculan automaticamente.

Caso de regresion: pedido 23790, origen 215040, destino 214948, porcentaje -17,36:
cada item se multiplica por 0,8264. La compensacion por procesos conserva su
regla independiente de valorizacion de cantidades con precios de referencia.

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
- La tabla detallada de pedidos de produccion muestra tambien las unidades imputadas, ademas de m2, ml e importe.
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

Cuando un usuario corrige manualmente los procesos de un item, el sistema registra la evidencia en `correcciones_proceso` y genera reglas candidatas en `reglas_proceso`. Las reglas se pueden simular antes de aprobarlas. Solo las reglas con estado `aprobada` se aplican en nuevas inferencias de procesos para altas de acopios y snapshots SPF; las reglas propuestas quedan como auditoría hasta aprobación manual.

Reglas interpretativas principales:

- `DVH`, `doble vidriado` o `doble vidrio` marcan Vidrio Exterior, Vidrio Interior y Cámara Normal.
- `Cámara` sin especificar Normal, Estructural u Offset se interpreta como Cámara Normal.
- `Cámara Normal` explícita puede convivir con Cámara Estructural u Offset si también aparecen en el detalle.
- `Cámara ... Estructural Offset` se interpreta como Cámara Offset. No se marca también como Cámara Estructural, porque es una variante Offset y no dos procesos de cámara acumulables.
- Un vidrio simple sin DVH, sin cámara, sin laminado y sin marca explícita de vidrio exterior se interpreta como Vidrio Interior para que sus m² entren en el resumen de procesos.
- Cuando en la descripción del ítem aparece primero la palabra `Templado` (o `Templada`, `Temp`) seguida del tipo de vidrio o espesor (ej. `Templado Opacid 8mm`, `Templado Float 6mm`, `Templado 8mm`), dicho ítem ya tiene incluido el proceso de templado en el precio de referencia/costo base; por lo tanto, no se computa como proceso separado de Fasón Templado Exterior (computa como vidrio monolítico asignando Vidrio Interior).
- Cuando `Templado` aparece luego del signo `+` o posterior al tipo de vidrio (ej. `Float 4mm + Templado + Pulido`, `Float 4mm Templado`, `Vidrio Exterior templado`), se computa como un proceso separado en costo y precio, marcando Fasón Templado Exterior.
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

## Diferenciación de Excedentes

Al imputar consumos contra un acopio, el sistema valida el consumo tanto contra el saldo global del acopio como contra el saldo individual del ítem asignado. Para dar mayor claridad al usuario sobre el origen del sobreconsumo, la plataforma diferencia tres estados a nivel de base de datos y UI:
- `ACOPIO`: Cuando el pedido supera el saldo total disponible del acopio. Visualizado como `⚠ Excedente acopio`.
- `ITEM`: Cuando el pedido entra dentro del presupuesto global del acopio, pero consume más de lo contratado para esa línea particular. Visualizado como `⚠ Excedente ítem`.
- `COMPOSICION`: Usado para advertencias de fallas en el matching de tipologías.

Las políticas de negocio (`BLOCK`, `WARN`) se aplican uniformemente tanto para excedentes globales como de ítem, pero la división visual permite al usuario de negocio identificar si el desvío requiere renegociar el acopio entero o si es un simple desplazamiento de material entre ítems.

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

## Documentación del acopio

El detalle de cada acopio incluye una sección independiente de los Informes Ejecutivos para registrar órdenes de compra, facturas de anticipo y recibos. No extrae información del PDF: número, emisor, fecha e importes se completan manualmente; el número abre el archivo adjunto. Se admiten PDF de hasta 20 MB y se puede guardar primero el comprobante para adjuntar su archivo después.

- El reparto Facturado / Viviana se guarda por acopio y admite porcentajes de 0 a 100 con dos decimales, incluidos 50/50. Los históricos quedan por definir. El importe de Viviana se obtiene como diferencia respecto del neto total para conservar los centavos.
- «Agregar comprobante» y «Asociar existente» abren sus formularios aunque el reparto esté por definir. Antes de confirmar se indica cómo definir y guardar el reparto; puede completarse con el formulario abierto sin perder datos. Un reparto modificado debe guardarse antes de confirmar el comprobante.
- Todos los importes aplicados y conciliados son netos en pesos, sin IVA. El IVA del comprobante es un dato informativo opcional.
- La OC puede cubrir solo Facturado, solo Viviana o ambas partes. En una OC total se conserva el original y se distribuye el importe aplicado; la factura se compara contra la parte Facturado de la OC vinculada. Se admiten varias facturas contra una misma OC.
- El control muestra pendiente de OC/factura, coincidencia o diferencia. La falta del PDF se informa por separado. La suma de las OC no incrementa lo facturado ni lo cobrado; las facturas tampoco se consideran cobros.
- “Asociar existente” permite distribuir un comprobante entre varios acopios. La suma de sus aplicaciones activas no puede superar su neto original. Los datos originales de un comprobante compartido se conservan al editar cada aplicación.
- Los recibos se aplican a Facturado o Viviana; los de Facturado pueden vincularse a una factura. Los cobros que superan esa factura o la parte acordada se señalan para revisión.
- “Anular vínculo” excluye una aplicación de los totales y permite restaurarla desde el historial. Primero deben desvincularse o anularse sus documentos dependientes.
- Los paquetes muestran únicamente el consolidado de las aplicaciones a sus acopios hijos. No tienen aplicaciones financieras propias y no repiten el importe original de los comprobantes compartidos.
- Las facturas y remitos de pedidos existentes en Consumos aplicados siguen consultándose desde SPF; no se importan como anticipos ni cobros. El saldo operativo se calcula una sola vez a partir de las imputaciones. La documentación inicial, su PDF y sus recibos no modifican saldos, imputaciones de pedidos ni compensaciones operativas.

La migración `d7e8f9a0b123` amplía las tablas existentes sin asignar reparto a registros históricos. Las pruebas de negocio están en `backend/tests/test_documentacion.py`.

### Saldos disponibles y control de desacopios

El resumen muestra pesos, m², ml y unidades disponibles desde los mismos saldos operativos del detalle, incluyendo todos los ítems. Las cantidades de procesos pueden superponerse (por ejemplo, vidrio y pulido), por lo que no se suman para reconstruir el stock físico.

El resumen termina con el control de cantidades y desacopios; se retiró el bloque final redundante de valorización por composiciones, sus advertencias y el filtro «Ver todo». La edición de precios por ítem continúa disponible como herramienta de control. El control de cantidades y desacopios lista todos los ítems, incluso sin conceptos ni precios, con cantidades y pesos contratados, imputados y disponibles, y el detalle de pedidos. Se calcula directamente desde las imputaciones, sin inferir ni cambiar procesos. Los desacopios sin ítem asignado tienen su propia fila: reducen el disponible total una sola vez, sin inventar una distribución entre ítems.

En la API, `saldos_disponibles` conserva las cuatro magnitudes operativas; `totals.saldo_valorizado` es `null` mientras la valorización sea incompleta. Los agregados numéricos anteriores se conservan como subtotales por compatibilidad y deben interpretarse junto con `valorizacion_completa` y `tiene_valorizacion`. Un precio cero ingresado manualmente sigue siendo un precio válido.

## Datos de Tango mediante Access

El detalle del acopio incluye el botón **Consultar Tango** en la sección Documentación del acopio, con una sola lista y sin modificar Consumos aplicados. Consulta las empresas Fontela y Viviana a través de la interfaz Access ya conectada a SQL Server. Carga facturas candidatas, sus recibos, notas de crédito y referencias a pedidos u órdenes de compra informadas en Tango. La coincidencia de cliente e importe propone una relación: no confirma por sí sola que el documento pertenezca a esa obra.

Los resultados quedan **Por revisar**. Cada registro permite **Conservar para control** o **Descartar coincidencia**, y los descartados pueden recuperarse desde el historial. Consultar otra vez no duplica resultados idénticos ni restaura descartados. Si el origen cambia, se presenta una nueva versión para revisar y se mantiene la versión conservada anterior hasta aceptar el cambio. También se detectan cambios de anulación; el estado CAN de Tango significa deuda cancelada, no comprobante anulado.

La consulta respeta el reparto Facturado/Viviana si está definido y funciona también en históricos sin reparto. **Ampliar búsqueda por cliente** incluye otras facturas del mismo cliente y requiere revisar especialmente la obra. La búsqueda inicial está limitada a dos años antes del alta del acopio y hasta seis facturas candidatas por empresa; se muestran advertencias de límites y de coincidencias ambiguas.

Los importes de Fontela se controlan sin IVA. El recibo conserva su total bruto original, pero muestra por separado las aplicaciones a los anticipos encontrados y su neto equivalente. Las notas de crédito son ajustes, no cobros; para una factura completamente cancelada, los recibos distribuyen el neto restante después de esos ajustes, conservando los centavos. Los cobros parciales indican que el neto es proporcional. Viviana utiliza el importe interno aplicado. Los documentos en moneda extranjera o con aplicaciones anuladas requieren revisar su conversión o aplicación antes de usar un neto equivalente.

**Conservar para control no crea ni modifica comprobantes manuales, saldos o imputaciones de desacopio.** Los resultados persisten en la tabla independiente tango_registros. Se conserva la información original consultada; la migración e8f901a2b345 crea esa tabla sin transformar los documentos existentes.

### Iniciar el conector en el equipo de Access

1. Abrir la interfaz Access que ya tiene acceso a Tango: C:\Users\windows\Desktop\Interfaz TANGO FONTELA Version2 SEPARACION FAC REM.mdb.
2. Desde Windows PowerShell o PowerShell 7, en la carpeta del repositorio, ejecutar:
   ~~~powershell
   .\scripts\Start-TangoAccessBridge.ps1
   ~~~
3. Mantener abierta esa sesión de Access mientras se realizan consultas. Los archivos iniciar_sistema.bat y reiniciar_sistema.bat también inician el conector, sin duplicarlo si ya está activo. Abrir Access por sí solo no inicia este proceso. El panel indica si falta Access o el conector. El proceso queda oculto; el inicio con Windows es opcional y se configura mediante el instalador documentado más abajo.

El iniciador utiliza PowerShell 7 si está disponible y Windows PowerShell en caso contrario, sin cambiar políticas permanentes. Para usar otra copia de la misma interfaz puede indicarse el parámetro -AccessFile con su ruta, siempre que contenga los vínculos esperados GVA14 y B_GVA14 a las bases configuradas.

El conector expone únicamente consultas SELECT fijas y de solo lectura, reutiliza la conexión autenticada de Access y no guarda contraseñas ni abre puertos. Verifica la empresa de cada vínculo y consulta las tablas reales de Tango, evitando las copias temporales de Access. No ejecuta SQL enviado desde la pantalla. La comunicación local usa backend/.tango_access_bridge/, excluida de Git; para detener el proceso, crear allí un archivo llamado stop. El próximo inicio lo elimina.

**Abrir PDF de Tango** está disponible cuando existe un archivo accesible en la carpeta de recibos autorizada \\srvfontela\SYSGESTION\RECIBOS. Se recupera el PDF por la identidad del comprobante, sin leerlo para extraer datos. Si Tango no tiene una copia accesible, se informa y continúa disponible la carga manual de PDF.

Las regresiones de consulta, revisión, versiones, distribución y aislamiento están en backend/tests/test_tango_access.py.

### Asociar existente desde Tango

Al abrir **Asociar existente**, el formulario consulta Tango automáticamente y muestra las coincidencias de Fontela y Viviana, junto con la búsqueda de comprobantes ya guardados en Acopios. **Usar estos datos** completa el formulario; recién **Guardar comprobante** crea la asociación comercial. Se puede descartar una coincidencia y recuperarla desde el historial de Documentación del acopio. Con Access desconectado se conservan los resultados anteriores y continúa disponible la búsqueda local.

Las facturas de anticipo y de mercadería de Fontela y los recibos de ambas empresas pueden incorporarse directamente. Los recibos de Viviana a cuenta no necesitan una factura. Las notas de crédito y los anticipos internos de Viviana permanecen como información de control, sin convertirlos en facturas fiscales o cobros. La búsqueda conserva los límites y criterios de coincidencia explicados arriba.

Para los recibos de Fontela se consulta también su distribución completa, incluidas otras facturas, para conservar el bruto original y calcular el neto de control completo. La aplicación sugerida al acopio incluye solo los anticipos candidatos relacionados. Si no se puede determinar el neto completo, hay moneda extranjera o aplicaciones anuladas, se explica por qué no se habilita la incorporación automática. El usuario puede revisar y reducir el importe sugerido.

Una identidad única por empresa, tipo e identificador de Tango evita duplicar el original al utilizarlo en varios acopios. Se controla el disponible global sin IVA, la parte Fontela/Viviana y la referencia a la factura; los datos originales importados se conservan. Si ya hay un documento manual con la misma identidad comercial, se pide seleccionarlo entre los guardados en Acopios. El PDF se copia al almacenamiento de Acopios si está disponible; una falla de copia se informa y permite adjuntarlo después.

La asociación guarda el resultado en Documentación del acopio y marca la coincidencia de Tango como conservada. Los saldos operativos y los consumos no cambian. La migración f901a2b3c456 agrega únicamente la tabla de identidades tango_comprobantes.

### Coincidencias en el campo Número de Agregar comprobante

El mismo campo Número del formulario existente consulta automáticamente, tras una breve pausa al escribir, facturas y recibos de Acopios y de las dos empresas de Tango. No agrega otro campo. Acepta números cortos como 11794 y formatos completos como A0007-00011794, con letra y punto de venta para resolver ambigüedades. La búsqueda por número en Tango no depende del importe, reparto, nombre del cliente ni de la ventana de fechas de la búsqueda general.

Las coincidencias se presentan sin completar ni sobrescribir los datos automáticamente. **Usar existente** reutiliza un comprobante local; **Usar datos de Tango** completa el mismo formulario y utiliza la asociación de origen al confirmar, evitando crear otra copia manual. Se mantienen el control de disponibles, la copia del PDF y los datos originales. **Ingresar otro número** permite volver a la carga manual. Las facturas de mercadería se identifican y no se proponen como anticipos.

Cada resultado de Tango muestra la razón social y advierte si el nombre difiere del cliente del acopio, porque los nombres locales pueden ser abreviaturas o nombres comerciales. El usuario revisa la coincidencia antes de usarla. Las consultas son limitadas y los resultados no se asocian hasta guardar. Si Access no responde, la búsqueda local sigue disponible y la pantalla informa qué fuente no pudo comprobarse.

La normalización y las consultas de ambos orígenes tienen regresiones en backend/tests/test_comprobante_numero.py.


### Facturas de mercadería en Documentación del acopio

El selector Tipo admite Factura de mercadería, además de Orden de compra, Factura de anticipo y Recibo. Se puede cargar manualmente con PDF, buscar por número en Acopios y Tango o usar Asociar existente. Se clasifica en la parte Facturado, puede vincularse a una OC y admite recibos vinculados. Los importes y disponibles se controlan sin IVA.

Tango propone anticipo o mercadería según los artículos del comprobante. Antes de incorporar por primera vez una factura de Fontela puede elegirse la clasificación; al utilizar los datos desde el campo Número se conserva el tipo de factura elegido en el formulario. Una vez incorporado un original compartido, su clasificación se conserva para todas las asociaciones, evitando crear otra copia del mismo comprobante.

El importe aplicado aparece separado en Mercadería documentada, tanto en el acopio como en el consolidado de paquetes. No se suma a Anticipos facturados ni se considera un cobro. Si la misma OC tiene anticipos y mercadería, el control pide revisar la aplicación de anticipos antes de consolidar esos documentos. La falta del PDF se informa por separado.

La asociación es documental: no crea imputaciones, no vuelve a descontar las facturas o remitos ya presentes en Consumos aplicados y no modifica saldos físicos ni monetarios del acopio. No necesita migración: FAC_MERCADERIA ya formaba parte del modelo de comprobantes.


### Lista unificada de Documentación del acopio

La pantalla presenta una sola sección Documentación del acopio para órdenes de compra, facturas, recibos y datos consultados en Tango. Agregar comprobante, Asociar existente y Consultar Tango comparten la misma lista. Cada fila indica el origen, el estado y el importe aplicado. No se mantiene un segundo panel Datos de Tango.

Un comprobante incorporado desde Tango aparece una sola vez: sus observaciones e historial se integran a la fila de su asociación. Para cargas manuales se reúnen también las coincidencias exactas del número fiscal completo y un emisor conocido, sin fusionar datos ni crear vínculos. Un número corto o una coincidencia de otro emisor no se utiliza como identidad para ocultar filas.

Las coincidencias sin asociación se muestran como Por revisar o Conservado sin asociar. Revisar y asociar abre el formulario de confirmación; Conservar para control no modifica los totales económicos. Las notas de crédito y los registros internos pueden conservarse como información de control. Los importes asociados mantienen sus reglas de conciliación y no se descuentan otra vez de los saldos operativos.

Una actualización de Tango en un documento ya asociado aparece dentro de la misma fila, con su detalle y controles de revisión. Se conservan el original financiero, las versiones anteriores y el historial de descartados o vínculos anulados. La consulta al proveedor no sobrescribe un reparto que el usuario esté editando. Sin Access se siguen mostrando los comprobantes y consultas guardadas.

La vista de lectura GET /acopios/{id}/documentacion/panel no transforma tablas ni migra información. Las regresiones de agrupación, origen, importes, versiones e independencia de Access están en backend/tests/test_documentacion_panel.py.


## Importación directa desde Glassware

En **Nuevo Acopio → Origen Glassware**, pegar el enlace de un presupuesto Aceptado.
El conector consulta cabecera e ítems con GET en la sesión abierta de Chrome; no
lee ni exporta cookies o contraseñas y no registra operaciones en Glassware.

### Activación en el equipo

1. Aplicar la migración: `docker compose exec backend alembic upgrade head`.
2. En el perfil de Chrome donde está Glassware, abrir `chrome://extensions`,
   habilitar Modo de desarrollador y cargar descomprimida la carpeta
   `C:\Users\windows\Desktop\Proyectos\Acopios\extensions\glassware`.
   También se puede descargar el ZIP desde la ayuda de Origen Glassware.
3. Recargar Acopios en `http://localhost:5173/acopios/alta` y mantener abierta una
   pestaña autenticada de Glassware en ese perfil. La versión inicial solo admite
   Acopios en localhost o 127.0.0.1, puerto 5173.
4. Consultar, revisar cantidades, medidas, cliente, obra y total; confirmar el alta.

La extensión es específica de Acopios, independiente de la extensión de ChatGPT.
Solo declara acceso a Glassware y un puente en las páginas locales de Acopios.
No requiere CDP, un proceso Windows, puertos adicionales ni claves compartidas.

La vista previa se valida y guarda en `glassware_imports`. Solo se confirma por su
identificador, vence a las dos horas y la confirmación repetida es idempotente.
En PostgreSQL se serializan confirmaciones del mismo presupuesto y se rechazan
duplicados, incluso contra acopios de PDF/SPF con ceros iniciales diferentes.

Se incluyen todos los ítems del presupuesto Aceptado; no se descartan alternativas
por palabras en la descripción. Se validan lista completa, cantidades, dimensiones
y totales. Un cambio durante la lectura o un dato faltante impide importar.
El ajuste comercial se distribuye proporcionalmente en los ítems con conciliación
exacta a centavos. No se recalcula el total desde el porcentaje redondeado visible.
Se conservan los importes y medidas fuente y los componentes con sus descuentos en
la instantánea de auditoría, sin guardar HTML ni credenciales. Los precios de paños
no disponibles quedan sin valor; no se inventan. La fecha de aprobación tampoco se
deduce de la fecha de creación.

Pruebas: `docker compose exec backend pytest -q tests/test_glassware.py`.
Para las pruebas aisladas de la extensión, instalar las dependencias de desarrollo
en `extensions/glassware` y ejecutar `npm test` allí. No se usan en producción.


Un estado Parcial no implica que el acuerdo sea parcial: Glassware puede mostrarlo
para un presupuesto aprobado por el total. El conector permite consultar ese estado,
conserva todas las cantidades originales y exige una verificación explícita de
aprobación antes del alta. No crea ni deduce consumos a partir del estado; quedan
registrados el estado fuente y la verificación. Enviado, Borrador y los demás estados
siguen rechazados. La ruta GET de vista previa permite reabrir una consulta pendiente.


### Validaciones finales del conector Glassware

La extracción exige todos los ítems, sus materiales y precios, y verifica que la
cantidad de complementos coincida con Glassware. Se rechazan medidas, cantidades
o importes fuera del rango de almacenamiento y respuestas incompletas. Un importe
total diferente de la suma de ítems debe estar explicado por un ajuste general;
la tolerancia del porcentaje solo contempla los dos decimales visibles del origen.
El reparto usa restos mayores para conservar los centavos sin valores negativos.

La confirmación guarda cabecera, ítems, paños, complementos y auditoría en una sola
transacción. Una misma vista previa es idempotente y dos vistas del mismo presupuesto
no pueden crear dos acopios simultáneamente desde el conector. Si se elimina el
acopio con el flujo existente, queda la auditoría con fecha de confirmación; su
identificador de vista previa no puede volver a utilizarse para crear otro.

Pruebas PostgreSQL con bases temporales, creadas y eliminadas automáticamente:
`docker compose exec -e GLASSWARE_POSTGRES_TESTS=1 backend pytest -q tests/test_glassware_postgres.py`.
Incluyen migraciones desde cero, confirmaciones concurrentes, saldos iniciales,
relaciones guardadas y borrado con conservación de auditoría. No usan la base real.

### Inicio del conector Tango en Windows

El conector se ejecuta fuera de Docker y debe iniciarse en cada sesion de Windows.
Para habilitar el inicio automatico del usuario actual, ejecutar:
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Install-TangoAccessStartup.ps1`.
El acceso directo inicia solamente el conector, de forma oculta; no abre Access ni
Docker. Si Access se abre despues, el conector lo detecta automaticamente.
Para desactivarlo, ejecutar el mismo instalador con `-Remove`.
Los iniciadores usan Windows PowerShell y el puente admite tambien PowerShell 7,
sin depender de que `pwsh` este instalado en el PATH del usuario.

### Busqueda Tango con titular fiscal diferente del cliente de obra

Una factura manual o importada, asociada y activa en un acopio, aporta su identidad
completa (empresa, letra, punto de venta y numero) a las siguientes consultas de ese
acopio. Se recuperan sus recibos y notas aplicadas desde Tango incluso cuando el
cliente de la obra es un profesional y el titular fiscal es otra razon social.
No se generaliza esa identidad a otras obras ni se crean cobros automaticamente.
Anular la asociacion retira esa evidencia de las consultas siguientes.

Para la primera consulta, si no coincide nombre/CUIT, se proponen candidatos solo
cuando coinciden el neto exacto y palabras significativas de la obra con la razon
social fiscal. La diferencia de titular se informa para revision. La busqueda por
numero tambien recupera las aplicaciones; la factura manual existente no se duplica
y los recibos pueden referenciarla sin fabricar un vinculo externo de origen.

Regresiones: `docker compose exec -T backend pytest -q tests/test_tango_access.py` y
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/tests/Test-TangoDiscovery.ps1`.

## Registro de cambios

La entrega del 23/10/2026, sus migraciones y validaciones se detallan en [CHANGELOG.md](CHANGELOG.md).
