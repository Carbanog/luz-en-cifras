# Actualización y recuperación

## PVPC directo en 0.3.0

Actualiza desde HACS y reinicia HA. Se conservan contratos, grupos, IDs y esquema 3.
Ninguna modalidad cambia automáticamente: los contratos fijos y los que ya usan un
sensor de precio mantienen su configuración. Para usar la fuente directa, edita el
grupo, elige **PVPC directo de Red Eléctrica** y guarda. No requiere otra integración
ni introducir un sensor de precio. Guarda un respaldo completo antes de actualizar.

HACS/HA instalarán la dependencia declarada `esios-api`; solo el modo directo inicia
peticiones de precios. Si vuelves a 0.2.x después de guardar un grupo PVPC directo,
restaura conjuntamente código y datos del respaldo: esa versión no reconoce la
modalidad nueva. Las releases anteriores se conservan para recuperación.

## Pasar de main a releases

La primera release es **0.2.0** e incluye las mejoras de 0.2.0.dev3, sin cambios
funcionales adicionales. Si instalaste `main`, abre el menú del repositorio en HACS,
elige **Volver a descargar** y selecciona **0.2.0**. Reinicia HA y comprueba la versión
en los diagnósticos. No elimines los contratos. A partir de ahí utiliza las versiones
de [Releases](https://github.com/Carbanog/luz-en-cifras/releases) para actualizar.

Antes de actualizar guarda un respaldo completo de HA. HACS permite seleccionar
releases anteriores, pero una bajada con cambios de almacenamiento requiere restaurar
también sus datos. Las notas de cada release indicarán cualquier migración necesaria.

## Corrección de arranque en 0.2.1

Actualiza desde HACS y reinicia HA. No elimines el contrato ni sus datos. Esta versión
no cambia el esquema 3: sincroniza el instante de precios y mediciones y utiliza la
tarifa fija de cada revisión para calcular los datos ya recogidos. Un contrato 0.2.0
afectado por el hueco inicial puede recuperar su cálculo después de actualizar.
No se extrapolan precios de entidades para rellenar huecos dinámicos auténticos.

## Actualizar desde 0.1

1. Crea una copia de seguridad completa de Home Assistant antes de actualizar.
2. Actualiza la integración mediante HACS y reinicia HA. No elimines sus contratos.
3. Comprueba las fuentes, precios y calidad de datos en cada contrato.

Se conservan dominio, identificadores de contrato y `unique_id` de entidades. La
configuración añade valores predeterminados sin borrar los anteriores. El payload
interno del Store pasa al esquema 3; la versión externa del Store sigue siendo 1
para poder leer de forma controlada las instalaciones anteriores.

El almacenamiento de 0.1 se guarda íntegro en `legacy_v1`. Sus muestras puntuales
carecen de duración: se importan conservando cantidades y con advertencia de
precisión temporal desconocida. No se inventan intervalos históricos detallados.

**Volver a 0.1 requiere restaurar código y almacenamiento del respaldo**, no solo
reemplazar archivos Python: esa versión no entiende el nuevo ledger. La copia
`legacy_v1` no sustituye una copia de seguridad de HA.

La eliminación de un contrato es independiente del resto y utiliza la API pública
Store. No se han modificado datos de HA, Recorder ni otras integraciones.

## Asistente de 0.2.0.dev2

La versión menor de configuración pasa a 3. Conserva los campos del contrato y sus
opciones; normaliza días/meses enteros antiguos que los selectores habían guardado
como cadenas `1.0`. No trunca valores fraccionarios ni borra mediciones. Los pasos
nuevos no requieren eliminar ni volver a crear un contrato.

Si tenías un alta sin guardar abierta al actualizar, ciérrala y vuelve a abrirla
después del reinicio. Los contratos ya guardados se editan desde sus opciones.

## Continuidad de factura en 0.2.0.dev3

Los cambios de sensores, grupos y tarifas realizados desde esta versión conservan
el ledger del ciclo abierto. El esquema 3 añade fronteras de revisión y referencias
pendientes de contadores, sin borrar mediciones, históricos ni campos anteriores.
El lector admite el esquema 2 sin esos campos y mantiene los IDs existentes.

Los segmentos `configuration_change` que ya cerraron versiones anteriores se conservan
como estaban: no se unen automáticamente a una factura, porque hacerlo podría duplicar
cargos o consumos. Esta actualización no reconstruye lecturas que nunca se recogieron.

Antes de actualizar, guarda una copia completa de HA. Para volver a una versión sin
continuidad, restaura **su código y su almacenamiento del mismo respaldo**: sustituir
solo Python no garantiza interpretar correctamente las nuevas revisiones de fuentes.
