Conector Glassware para Acopios

1. Abrir chrome://extensions en el perfil Trabajo.
2. Activar Modo de desarrollador y elegir Cargar descomprimida.
3. Seleccionar esta carpeta (la que contiene manifest.json).
4. Mantener una pestaña de Glassware abierta e iniciar sesión allí.
5. Abrir http://localhost:5173/acopios/alta en el mismo perfil y recargar.
6. Elegir Origen Glassware, pegar el enlace del presupuesto aprobado y consultar.
7. Revisar los datos. Solo Confirmar y crear acopio registra el alta en Acopios.

El conector usa GET sobre presupuestos e ítems del dominio Glassware. No lee,
exporta ni guarda contraseñas o cookies. No paga, acepta ni modifica presupuestos.
Solo atiende a Acopios en localhost o 127.0.0.1, puerto 5173. No requiere acceso
completo a CDP ni la extensión de ChatGPT para operar.

Los importes finales se toman de Glassware. El ajuste global se distribuye
entre ítems con redondeo a centavos y conciliación exacta. Los valores fuente
de componentes, medidas e importes anteriores al ajuste quedan en el registro
de importación del servidor. No se inventan precios individuales de paños.
Se admite Aceptado. Parcial requiere verificar su aprobación por el total en Acopios.
No se eligen ni eliminan ítems por su descripción.
Las vistas previas vencen a las dos horas. Consultar de nuevo si hubo cambios.
