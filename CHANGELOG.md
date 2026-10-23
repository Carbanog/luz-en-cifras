# Changelog

## Sin publicar

- Distingue horas locales repetidas al seleccionar precios durante el cambio de hora.
- Añade asignación de intervalos con rechazo de huecos y solapamientos y estimación
  uniforme opcional marcada como parcial (motor, aún sin configuración HA).
- Normaliza precios €/MWh y €/kWh y documenta la referencia de Domoticarte.

## 0.1.0 — en desarrollo

- Crea el motor de cálculo independiente con importes `Decimal`.
- Añade grupos de consumo con deducciones explícitas de subcontadores.
- Añade precios por grupo, periodos, potencia, cargos, descuentos e impuestos.
- Documenta y codifica solo los tramos fiscales peninsulares de 2026 ya resueltos.
- Añade configuración visual, persistencia local y sensores de contrato iniciales.
- Añade 26 pruebas unitarias de los escenarios matemáticos principales y límites.
- Prepara CI, validación Hassfest/HACS y documentación de instalación y seguridad.
