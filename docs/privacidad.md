# Privacidad

Luz en Cifras funciona localmente en Home Assistant.

- No crea cuentas ni usa servidores propios.
- No incluye telemetría.
- No solicita CUPS, DNI, dirección ni datos bancarios.
- Guarda configuración, lecturas acumuladas e intervalos en `.storage` mediante la
  API pública de Home Assistant.
- No accede directamente a la base de datos de Recorder.
- Los diagnósticos futuros deberán ocultar identificadores de entidades cuando
  puedan revelar ubicaciones o hábitos.

Al eliminar una entrada de configuración, Home Assistant descarga sus listeners y
elimina el archivo de almacenamiento asociado mediante su API pública.
