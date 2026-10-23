# Registro de cambios

## 2026-10-23

Se incorpora el trabajo acumulado desde el commit 8c577b9 (24/09/2026).

### Documentación económica del acopio

- Se incorpora documentación y conciliación dentro del detalle individual del acopio, con reparto explícito Facturado/Viviana, PDFs y asociaciones de documentos existentes.
- Se distinguen órdenes de compra, anticipos, facturas de mercadería y recibos. Los importes fiscales se comparan sin IVA; las facturas no se suman como cobros ni descuentan nuevamente consumos.
- El panel unifica comprobantes manuales, importados y coincidencias de Tango, con versiones, revisión e historial. Los paquetes muestran su consolidado documental.

### Tango mediante Access

- Se agrega un conector Windows de consultas de solo lectura para Fontela y Viviana, con heartbeat, cola local excluida de Git e iniciadores del sistema.
- Se incorporan consultas por cliente y número, recibos y notas aplicadas, copia de PDF disponible y asociación de originales con identidad compartida y control del disponible.
- Las facturas asociadas permiten consultar aplicaciones aunque el titular fiscal difiera del cliente de la obra. Las coincidencias requieren revisión; consultar no genera cobros ni modifica saldos.
- Se incluye un instalador opcional de inicio con Windows y su desinstalación mediante -Remove. No se cambia la política permanente de PowerShell.

### Alta desde Glassware

- Se incorpora una extensión Chrome y el alta desde presupuestos Aceptados. El estado Parcial exige verificar explícitamente la aprobación por el total.
- Se validan cabecera, lista completa de ítems, materiales, medidas, cantidades, complementos e importes. Los ajustes se distribuyen conservando los centavos.
- Se guardan vistas previas con vencimiento de dos horas, auditoría, confirmación idempotente y protección contra duplicados concurrentes en PostgreSQL. El borrado del acopio conserva el registro de importación.
- El ZIP descargable se entrega en frontend/public/glassware-connector.zip. La extensión se carga desde extensions/glassware; las instrucciones operativas están en README.md.

### Compensación y control de desacopios

- Se agrega control por ítem de cantidades contratadas, imputadas y disponibles en pesos, m², ml y unidades, incluido el detalle de pedidos.
- Las imputaciones sin ítem se muestran aparte y reducen el total una sola vez. Los ítems sin composición también integran el control físico.
- Se distingue valorización parcial de completa y se expone saldo_valorizado nulo cuando faltan precios; un precio manual cero sigue siendo válido.
- Se simplifica el resumen del detalle manteniendo la edición de precios por ítem.

### Migraciones y puesta en marcha

Aplicar las migraciones con `docker compose exec -T backend alembic upgrade head` en el entorno de destino, con el respaldo habitual de su base de datos:

1. d7e8f9a0b123: documentación de acopios.
2. e8f901a2b345: registros de consulta Tango.
3. f901a2b3c456: identidades de comprobantes Tango.
4. a012b3c4d567: importaciones Glassware.
5. b123c4d5e678: ciclo de vida y auditoría Glassware.

Consultar README.md para cargar la extensión y ejecutar el puente Access. El puente requiere acceso a la interfaz Access autenticada; Glassware requiere una pestaña autenticada en el mismo perfil de Chrome.

### Validación de esta entrega

- Backend: 115 pruebas aprobadas en test_compensacion_service.py, test_documentacion.py, test_documentacion_panel.py, test_comprobante_numero.py, test_tango_access.py y test_glassware.py.
- PostgreSQL: 3 pruebas aprobadas en test_glassware_postgres.py, con GLASSWARE_POSTGRES_TESTS=1; incluyen migraciones y confirmaciones concurrentes en bases temporales.
- Extensión Glassware: 12 pruebas aprobadas mediante npm test. Se incorpora package-lock.json para reproducir sus dependencias de desarrollo.
- Frontend: npm run build completó TypeScript y la compilación de producción.
- Puente Tango: Test-TangoDiscovery.ps1 aprobado para titular diferente, búsqueda por número, recibos, referencias e identidad.
- Se observaron advertencias de deprecación de SQLAlchemy/Pydantic y del atributo version de Docker Compose; no fallaron las validaciones.

Alcance: se validaron los módulos modificados y los contratos automatizados. Estas comprobaciones no reemplazan una consulta manual autenticada en Access/Glassware ni aplican migraciones a la base operativa.
