# Tarifas y precisión de las lecturas

## Qué se configura por grupo

- Fija: un precio de energía sin impuestos en €/kWh.
- Tres periodos: P1/P2/P3 en €/kWh. Calendario 2.0TD de Península y Baleares.
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

Instala la integración nativa **Spain electricity hourly pricing (PVPC)** y selecciona
su entidad FEU. Según la [documentación de HA](https://www.home-assistant.io/integrations/pvpc_hourly_pricing/),
ese precio incluye producción, peajes y cargos de energía, sin impuestos. No añadas
estos componentes de nuevo como margen o servicio.

Los precios se guardan desde que comienza el seguimiento. Un reinicio no autoriza a
suponer cuál fue el precio durante la parada: los huecos se conservan como tales.
La caducidad predeterminada de una cotización sin actualizar es de 65 minutos y se
puede ajustar entre 1 y 1440. No hay descarga obligatoria de precios desde esta
integración; si usas PVPC, la integración nativa es quien consulta su proveedor.

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
