# Changelog

## Sin publicar

### 0.2.0.dev1 — sensores de potencia directos

- Añade sensores directos W/kW junto a Wh/kWh, grupos mixtos y detección de unidad.
- Integra potencia con regla izquierda, caducidad configurable y persistencia sin
  extrapolar paradas; valida filas de casa y coche con tarifas independientes.
- Mantiene intervalos estimados identificados al cerrar y restaurar históricos.

### 0.2.0.dev0 — experimental

- Conecta tarifas fijas, tres periodos 2.0TD y entidades dinámicas/PVPC a HA.
- Conserva precios y descuentos históricos, añade potencia/cuotas fechadas y perfil fiscal manual.
- Añade compensación básica de excedentes con límite, cargos y tributación por concepto.
- Añade cierre, exportación, comparación real y revisión auditable mediante acciones nativas.
- Añade grupos editables, sensores por grupo, diagnósticos, Repairs y migración que conserva 0.1.
- Corrige pasos numéricos del asistente, clase monetaria y zona horaria del ciclo.
- Añade pruebas funcionales con Home Assistant real en docker-lab y CI.

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
