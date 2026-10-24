# Plan de desarrollo y estado verificable

Corte: 24 de octubre de 2026. Versión en validación 0.3.0.

## A — Investigación

Hecho: referencias de producto/licencias, fiscalidad ordinaria verificada hasta
octubre de 2026, calendario 2.0TD de 2026, integración PVPC nativa y compensación
simplificada básica. Las medidas condicionadas no se presentan como resueltas.

Pendiente: perfiles territoriales automáticos, bono social y fórmulas comerciales
especiales. La disponibilidad del nombre no equivale a exclusividad registral.

## B — Motor

Implementados y probados: fuentes y grupos, precios fijos y por intervalos, calendario
tres periodos, vigencias en UTC, potencia fechada, cargos y sus bases, descuentos,
perfil fiscal versionado/manual, compensación limitada y snapshots auditables.

El cálculo del consumo medido se separa del reparto temporal estimado. Huecos,
solapamientos y datos no finitos producen errores explícitos.

## C — Home Assistant

Implementados: asistente por módulos, precios según modalidad, edición/eliminación
de grupos con IDs estables, ledger persistente, migración, descarga con guardado,
sensores por contrato/grupo, diagnósticos y aviso Repairs.

PVPC directo consulta precios públicos de REE sin otra integración, conserva horas
publicadas y expone el precio actual. Las fuentes por entidad siguen disponibles.
La aceptación acelerada cubre 61 días sintéticos y cierre mensual/bimestral; no
sustituye la comprobación de dispositivos reales ni la resolución fiscal pendiente.

Cambiar sensores, grupos o modalidades mantiene una factura continua con las fuentes
y precios de cada revisión. Los cargos se calculan una vez; un contador nuevo espera
una referencia real. Los cruces ambiguos requieren consentimiento para estimar.

La selección acepta W/kW y Wh/kWh directamente, con grupos mixtos y conversión
estimada de potencia. Se conserva la energía y se corta la continuidad en paradas,
lecturas inválidas y caducidad; no se reconstruye consumo no medido.

Las pruebas funcionales usan HA 2026.10.2 y 2026.10.3 en contenedores aislados de desarrollo
en docker-lab y se repiten en CI. HACS continúa siendo el método de instalación.

## D — Histórico y conciliación

Implementados: cierre automático, cierre manual con fechas y devengo explícitos,
exportación mediante acciones nativas, comparación de importes/energía, auditoría y
revisión con enlace al original. Un cierre sin datos suficientes conserva el error
y los datos, sin asignarle un resultado válido.

No se importa aún Recorder/CSV/Datadis. Los datos cerrados no se recalculan al editar
precios. No hay purga automática. La retención requiere una decisión explícita futura.

## E — Experiencia

Hecho: formularios nativos con selección de tarifa y campos progresivos; plantillas
Lovelace con tarjetas nativas y README con instalación, límites y recuperación.

Pendiente: inspección visual del flujo renderizado en 390/1440 px, temas, teclado y
contraste con facturas reales anonimizadas. Las pruebas de API de flujos no se
presentan como una revisión visual. No hay tarjeta propia obligatoria.

## F — Distribución

Repositorio público y CI disponibles, con validación HACS/Hassfest y marca local.
La primera release, 0.2.0, permite instalar y actualizar por versión desde HACS.
Sigue en validación y no está incluida en el catálogo predeterminado de HACS.
Las releases posteriores conservan las anteriores; toda actualización debe disponer
de un respaldo para poder recuperar código y datos. `main` queda para desarrollo.

## Criterio para la fase final

No se dará por completo el alcance nacional o cualquier contrato comercial mientras
la matriz de cobertura mantenga excepciones. Las siguientes ampliaciones requieren
sus reglas documentadas y casos de prueba: bono social con límites, batería virtual,
cuota plana/regularización, peajes de otros tipos de acceso y perfiles territoriales.
