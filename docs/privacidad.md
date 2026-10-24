# Privacidad

Luz en Cifras funciona localmente en Home Assistant.

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

Las entidades de precio externas, como PVPC, son gestionadas por sus propias
integraciones. Luz en Cifras solo lee sus estados locales. El enlace opcional de
apoyo abre una web externa únicamente cuando lo pulsas; no incorpora widgets.

Al eliminar una entrada de configuración, Home Assistant descarga sus listeners y
elimina el archivo de almacenamiento asociado mediante su API pública.
