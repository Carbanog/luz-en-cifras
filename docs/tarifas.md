# Tarifas y precisión de las lecturas

## Qué se configura por grupo

- Fija: un precio de energía sin impuestos en €/kWh.
- Tres periodos: P1/P2/P3 en €/kWh. Calendario 2.0TD de Península y Baleares.
- PVPC directo: FEU horario publicado por Red Eléctrica, sin impuestos y sin otra
  integración de HA. Alcance de esta modalidad: Península/Baleares.
- Entidad: precio completo sin impuestos en €/kWh o €/MWh. Puede ser el FEU de la
  integración nativa PVPC o una entidad calculada con tu contrato indexado.

El margen adicional se expresa en €/kWh y se suma después de normalizar las unidades.
Los precios negativos son válidos. La aplicación no convierte un precio OMIE en una
factura indexada completa: debes aportar una entidad que incluya la fórmula pactada.

El calendario eléctrico no equivale al laboral de cada comunidad. Aplica fines de
semana, 6 de enero y festivos nacionales fijos no sustituibles, excluyendo los
festivos móviles. La verificación incluida se limita a 2026. Fuentes:
[Circular 3/2020, artículo 7](https://www.boe.es/buscar/act.php?id=BOE-A-2020-1066) y
[calendario oficial 2026](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-21667).

La tarifa 2.0TD tiene tres periodos de energía y dos potencias. P1/P2 de potencia no
deben confundirse con los tres precios de energía. Una potencia en €/kW/año se divide
entre 365 cuando eliges esa unidad; verifica que ese es el divisor de tu contrato.

## Fuente PVPC

Puedes elegir **PVPC directo de Red Eléctrica** o mantener una entidad de la integración
nativa. Ambas opciones deben usar el FEU: incluye producción, peajes y cargos de
energía, sin impuestos. No añadas estos componentes de nuevo como margen o servicio.
[Fuente oficial](https://www.esios.ree.es/es/pvpc) y
[documentación de HA](https://www.home-assistant.io/integrations/pvpc_hourly_pricing/).

El modo directo usa `esios-api>=4.4.0`, probada con 4.4.0, la misma biblioteca de HA
2026.10.2/2026.10.3. Consulta el recurso público de precios diarios de REE sin token,
al iniciar y cada 30 minutos; la biblioteca evita repetir descargas ya disponibles.
No requiere tener instalada ni configurada `pvpc_hourly_pricing`. No obtiene OMIE
para construir una fórmula PVPC propia. No añade márgenes comerciales al FEU.

Se validan calendarios completos de 23, 24 o 25 horas, conservando horas en UTC.
Cada precio vale solo en su hora publicada; las horas descargadas, incluso las
futuras cuando están publicadas, se guardan en el ledger. El sensor de precio de
cada grupo muestra el FEU vigente, antes de descuentos e impuestos. Si falta su hora,
queda indisponible. Una corrección publicada de un precio ya guardado genera aviso
y conserva la cotización original; no revaloriza el pasado silenciosamente.

El límite de red es 20 segundos por actualización, sin reintentos inmediatos. Ante
una caída se conserva el calendario válido: solo se calcula lo que sus horas cubren.
Si faltan precios, se guardan las mediciones y se muestra el error; no se factura
a cero ni se extrapola. Una descarga posterior puede completar las horas pendientes
del día disponible. No se importan automáticamente calendarios antiguos de días
que nunca se descargaron, ni consumo de Recorder o durante una parada de HA.

En el modo **entidad**, se guardan las cotizaciones observadas y se mantiene la
caducidad configurable de 65 minutos por defecto (1–1440). Un reinicio no permite
suponer sus precios durante la parada. Esta caducidad no se aplica a un calendario
oficial: sus precios tienen horas de validez explícitas.

## Lecturas que cruzan precios

Un contador que pasa de 100 a 102 kWh entre las 09:58 y las 10:03 no indica cuántos
kWh corresponden a cada precio. La opción predeterminada rechaza un reparto exacto.
Puedes activar el **reparto uniforme por tiempo**, que conserva el total medido pero
marca la estimación como parcial. Un hueco real de precios no se rellena con cero ni
se extrapola: el resultado queda indisponible.

Los cambios de hora se comparan en UTC, conservando el calendario local para cada
periodo. Las dos horas repetidas de otoño tienen identificadores distintos.

## Cambios de contrato

Las revisiones de precio y descuento energético se guardan con su instante de
vigencia. Potencia y cuotas diarias se modifican desde la fecha local de edición;
el día de edición utiliza los nuevos valores. El servicio por factura se aplica una
sola vez con el valor configurado al calcularla. No se admiten todavía modificaciones
retroactivas arbitrarias de cláusulas comerciales.

Cambiar sensores, grupos o modalidad conserva una sola factura y sus mediciones.
Cada revisión usa sus fuentes, precios y descuentos desde el instante de edición;
el consumo anterior no se vuelve a valorar con la tarifa nueva. Los cargos diarios
y la potencia se prorratean por sus fechas y el servicio por factura se cobra una
sola vez. Renombrar un grupo o editar cargos diarios no introduce por sí mismo una
frontera de reparto energético.

Un contador recién seleccionado espera una lectura real de referencia. Si se retira
y luego se vuelve a seleccionar, no suma el consumo ocurrido mientras estaba fuera
del contrato. Una lectura acumulada que cruza una revisión requiere reparto temporal
autorizado o deja el cálculo indisponible; no se atribuye entera al precio nuevo.
Los contadores que se reinician o se corrigen también establecen una nueva línea
base: el intervalo dudoso no se convierte en consumo inventado.
