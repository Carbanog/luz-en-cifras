# Referencia: cálculo con plantillas de Domoticarte

Revisado el 23 de octubre de 2026:
[Calcula tu Factura de Luz con Home Assistant](https://domoticarte.com/blog/calcula-factura-luz-home-assistant/),
de Daniel Martín, publicado el 29 de agosto de 2024.

## Aportaciones

La guía muestra cómo enlazar sensores de energía, precios y costes fijos con el
panel Energía, y cómo separar el coste de dispositivos o líneas. Ayuda a comprobar
las necesidades reales de una integración configurable sin plantillas manuales.
Se registra como referencia de producto; no se incorpora su código.

La recomendación aprovechable es usar la integración nativa PVPC de HA como fuente
opcional, consultando sus entidades públicas. La
[documentación oficial](https://www.home-assistant.io/integrations/pvpc_hourly_pricing/)
indica que el sensor publica FEU en €/kWh, incluyendo peajes, cargos y producción,
sin impuestos. Evitar cobrar estos componentes dos veces.

## Aspectos que requieren adaptación

- Los porcentajes fiscales ilustrativos de 2024 no se trasladan a reglas de 2026.
- El ejemplo llamado indexado asigna tres precios fijos por periodo; no cubre todas
  las fórmulas comerciales de indexación.
- Convertir una lectura desconocida en cero oculta falta de datos.
- Crear energía ficticia para mostrar cargos fijos no forma parte de nuestro modelo.
- La calidad de una estimación depende de la cobertura temporal y de precios.

## Avance técnico derivado

El motor ahora compara vigencias en UTC para distinguir las dos horas locales
repetidas de otoño. Se añade un normalizador de precios €/MWh y €/kWh y un
asignador de intervalos medidos que detecta huecos y solapamientos. Si una lectura
atraviesa varios precios sin desglose, el comportamiento predeterminado es rechazar
el cálculo; el reparto uniforme solo se permite explícitamente y se marca parcial.
Este módulo todavía no está conectado al asistente ni al coordinador de HA.
