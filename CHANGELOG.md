# Changelog

## Sin publicar como nueva versión

- Sustituye la antigua vista de ejemplo por dos dashboards completos: nativo y
  Mushroom, con Resumen y Desglose, avisos de calidad y estados sin datos explícitos.
- Añade capturas del HA de pruebas en escritorio y móvil, guía de instalación y
  adaptación de entidades, y explicaciones visuales de modalidad y potencia P1/P2.
- Explica la fiscalidad automática sin ampliar la vigencia de las reglas incluidas.
- Clasifica la integración como Energía en sus metadatos. No cambia cálculos ni datos.
- Las plantillas se copian por separado; no requieren actualizar o reiniciar la integración.

## 0.3.0 — 24 de octubre de 2026

- Añade PVPC directo desde REE/ESIOS, sin otra integración de HA ni sensor externo,
  para Península/Baleares. Mantiene la selección de una entidad existente.
- Valida calendarios completos de 23/24/25 horas, conserva precios publicados por
  hora, muestra el precio actual por grupo y rechaza huecos sin extrapolar ni poner cero.
- Limita las consultas, conserva caché, recupera mediciones pendientes del día y
  cancela descargas al descargar la entrada. Precio fijo no crea cliente de red.
- Añade simulaciones de 61 días para cierres mensuales/bimestrales, cambio de hora,
  recarga y recálculo. No se cambia la hora del HA del usuario ni se instalan fixtures.
- Declara `esios-api>=4.4.0`, probada con 4.4.0 como HA de referencia; actualiza
  privacidad, cobertura, actualización y evidencias de pruebas.
- Mantiene el esquema de datos 3. La fiscalidad automática de noviembre sigue
  pendiente: las pruebas aceleradas no se presentan como resolución fiscal.

## 0.2.1 — 24 de octubre de 2026

- Corrige un hueco de microsegundos entre precios y mediciones de potencia al arrancar
  o cambiar de ciclo, detectado en el HA de pruebas con dos filas y un coche simulados.
- Usa el precio fijo de cada revisión contractual para calcular sus mediciones; permite
  recuperar el cálculo de datos ya recogidos sin borrarlos ni modificar cotizaciones.
  Las tarifas dinámicas siguen rechazando huecos reales de precio.
- Añade regresiones con un reloj que avanza durante el arranque; los tests congelados
  no reproducían este fallo. Corrige la ruta del logo para el README mostrado en HACS.
- Conserva esquema de almacenamiento e identificadores. Requiere actualizar y reiniciar
  HA; la actualización en la instalación del usuario sigue siendo manual.

## 0.2.0 — 24 de octubre de 2026

Primera release versionada para actualizar mediante HACS. Incluye las mejoras de
desarrollo detalladas a continuación. Sigue en validación: la aceptación con sensores
y facturas reales está pendiente. Requiere Home Assistant 2026.10.2 o posterior;
se han probado 2026.10.2 y 2026.10.3.

- Unifica manifiesto, paquete y diagnósticos en 0.2.0.
- Documenta cómo pasar de `main` a releases, actualizar y recuperar una versión.
- No introduce cambios funcionales respecto a 0.2.0.dev3 ni cambia datos al publicar.

### 0.2.0.dev3 — continuidad al cambiar sensores y tarifas

- Mantiene una sola factura al sustituir sensores, añadir o retirar grupos y cambiar
  entre tarifa fija, tres periodos y precio de entidad; conserva las revisiones previas.
- Calcula cargos fijos e impuestos una vez y conserva la compensación de los tramos
  anteriores aunque se desactive o cambie su sensor después.
- Evita sumar consumos de un contador mientras está retirado y espera un reporte real
  para establecer la referencia de un contador recién seleccionado.
- Conserva cantidades conocidas mientras un grupo espera mediciones; un grupo sin
  datos queda desconocido. Los cruces ambiguos requieren estimación autorizada.
- Guarda fronteras y referencias pendientes en el esquema aditivo 3, preservando
  históricos, cierre y recálculo reproducible. Documenta actualización y reversión.

### 0.2.0.dev2 — asistente guiado y ayudas de factura

- Modalidad de energía antes del resto de datos; cada grupo mantiene sus precios.
- Separa periodo, sensores/tarifa, unidad de potencia y potencias contratadas.
- Explica P1/P2, kW frente a W/kWh, precios unitarios y alquiler junto a los campos.
- Mes de referencia solo en bimestrales; opciones técnicas dentro de Avanzado.
- Elimina el cero automático en potencias/costes desconocidos y corrige enteros
  devueltos como `1.0` por los selectores, que impedían recargar un contrato editado.
- Añade regresiones del recorrido y compatibilidad, y CI para HA 2026.10.3.

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
