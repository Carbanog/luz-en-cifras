# Privacidad

Luz en Cifras calcula y guarda las facturas localmente en Home Assistant.

- No crea cuentas ni usa servidores propios.
- No incluye telemetría.
- No solicita CUPS, DNI, dirección ni datos bancarios.
- Guarda configuración, lecturas, precios, revisiones y facturas cerradas en
  `.storage` mediante la API pública de Home Assistant. Las copias de seguridad
  de HA pueden incluir estos datos de consumo.
- No accede directamente a la base de datos de Recorder.
- Los diagnósticos solo incluyen recuentos y estados de disponibilidad; no incluyen
  lecturas, nombres de contratos ni identificadores de entidades.
- La acción `export_history` sí devuelve el historial detallado y la configuración:
  revisa nombres, entidades, horarios e importes antes de compartir su respuesta.
- No se borra automáticamente el historial cerrado. Protege el acceso a HA y sus
  copias de seguridad; los hábitos de consumo también son información privada.

En precio fijo, tres periodos y precio desde entidad, lee estados locales y no
consulta servicios de precios. En **PVPC directo**, consulta el servicio público
de REE/ESIOS por HTTPS para las fechas del calendario. REE recibe la petición y la
dirección IP de salida; no se envían consumos, nombres, entidades ni datos del
contrato. No se requiere token ni cuenta. Los precios descargados se guardan con
las mediciones para conservar su trazabilidad y las horas de validez.

Las entidades externas que elijas siguen siendo gestionadas por sus integraciones.
El enlace opcional de apoyo abre una web externa únicamente cuando lo pulsas; no
incorpora widgets. La instalación inicial puede descargar dependencias de Python
mediante Home Assistant, como cualquier integración con requisitos declarados.

Al eliminar una entrada de configuración, Home Assistant descarga sus listeners y
elimina el archivo de almacenamiento asociado mediante su API pública.
