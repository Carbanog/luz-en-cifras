# Actualizar desde 0.1

1. Crea una copia de seguridad completa de Home Assistant antes de actualizar.
2. Actualiza la integración mediante HACS y reinicia HA. No elimines sus contratos.
3. Comprueba las fuentes, precios y calidad de datos en cada contrato.

Se conservan dominio, identificadores de contrato y `unique_id` de entidades. La
configuración añade valores predeterminados sin borrar los anteriores. El payload
interno del Store pasa al esquema 2; la versión externa del Store sigue siendo 1
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
