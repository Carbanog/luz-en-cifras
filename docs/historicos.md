# Históricos y comparación con facturas reales

Los periodos cerrados conservan el resultado, consumos, precios, configuración,
revisiones y parámetros fiscales. Se guardan localmente en el mismo Store del
contrato. La integración no modifica las tablas de Recorder.

## Cierre automático

Al cambiar de ciclo se archiva la última estimación y se abre otro. El devengo se
marca provisionalmente como el último día del consumo: una estimación automática
no conoce la fecha real de exigibilidad de la factura. Si faltan precios o reglas,
se archivan los datos y el motivo del fallo, sin fabricar un total válido.

## Acciones desde Home Assistant

En **Herramientas para desarrolladores → Acciones**, busca las acciones de Luz en
Cifras. Selecciona el contrato con el selector nativo.

| Acción | Resultado |
| --- | --- |
| Exportar histórico | Respuesta con los periodos y sus identificadores |
| Cerrar un periodo pasado | Snapshot con inicio incluido, final exclusivo y devengo explícito |
| Comparar con factura real | Total y energía reales, diferencias y registro de cambios |
| Revisar un periodo cerrado | Nueva versión con referencia al original y motivo obligatorio |

Para consultar el histórico, ejecuta **Exportar histórico** con respuesta. Copia el
identificador del periodo en la acción de comparación o revisión. La comparación
admite un total negativo si la factura es un abono, pero la energía introducida debe
ser no negativa. No adjuntes la respuesta completa a una incidencia pública: puede
contener nombres de contratos y entidades.

## Cierre manual y lecturas en los límites

El final es **exclusivo**: del 1 al 31 de octubre incluido se introduce desde el 1 de
octubre hasta el 1 de noviembre. Solo se cierran días completos anteriores a hoy.
Indica la fecha de devengo; no tiene por qué coincidir con el final del consumo.

Si una lectura atraviesa el límite, por defecto se rechaza el cierre exacto. Puedes
autorizar un reparto temporal parcial. El snapshot conserva la advertencia y los
datos originales para que el cálculo se pueda revisar. No reconstruye información
que nunca se recogió ni importa automáticamente lecturas de Recorder.

## Revisión y recuperación

Una revisión no borra el resultado previo. Puedes mantener su fecha de devengo o
indicar la real. También puedes solicitar expresamente aplicar el perfil fiscal
actual a esa fecha; los precios históricos se conservan. El resultado nuevo contiene
`supersedes`, que identifica el original. Toda modificación de la comparación real
se añade a un registro `audit`.

No existe purga automática de históricos en esta versión. Eliminar el contrato desde
HA elimina su Store, incluidos sus históricos. Haz una copia de seguridad de HA y,
si lo necesitas, exporta los registros antes de eliminarlo.
