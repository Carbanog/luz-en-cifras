# Sensores: potencia, energía y grupos

Puedes seleccionar directamente uno o varios sensores por grupo. La unidad de cada
entidad determina cómo se procesa; no se intenta deducir por su nombre ni se obliga
a crear ayudantes externos. Es posible combinar ambas clases dentro de un grupo.

| Unidad | Tratamiento |
| --- | --- |
| W | Potencia dividida por 1000 e integrada en el tiempo |
| kW | Potencia integrada en el tiempo |
| Wh | Contador acumulado normalizado a kWh; se usan sus incrementos |
| kWh | Contador acumulado; se usan sus incrementos |

V, A, VA, porcentajes, unidades ausentes y valores no numéricos no sirven como
consumo. La configuración rechaza unidades incompatibles y, si cambian durante el
uso, registra una advertencia. No se convierte una lectura ausente en cero. Los
valores negativos no representan consumo importado; para excedentes usa un sensor
independiente de exportación positiva, no un sensor neto con ambos signos.

## Dos filas de automáticos y coche

- **Casa:** fila 1 + fila 2, con precio fijo, tres periodos o precio de entidad.
- **Coche:** cargador, con su propia modalidad y precios.
- Si el cargador ya está incluido en las filas, réstalo del grupo Casa y súmalo al
  grupo Coche. No se deducen conexiones físicas automáticamente.
- No elijas simultáneamente la potencia y el contador de energía derivado del
  mismo circuito. Son entidades distintas pero representan el mismo consumo;
  esa duplicidad física no se puede detectar solo por los identificadores.

## Precisión y caducidad de la potencia

La conversión usa la **regla izquierda**: mantiene la última potencia reportada
hasta la siguiente lectura, actualizando también cada minuto. Al seleccionar W/kW
aceptas esta estimación, que se marca como parcial. Los precios se aplican a cada
intervalo; si cruza una frontera tarifaria, el reparto de esa potencia estimada
también se hace por tiempo. Para contadores Wh/kWh permanece la opción separada de
autorizar o rechazar ese reparto cuando no hay medición por intervalo.

En Contrato puedes configurar **Tiempo máximo sin reporte de potencia**: por
defecto son 5 minutos. Una lectura constante solo conserva su frescura si el sensor
sigue reportando a HA; el temporizador de la integración no renueva esa frescura.
Adáptalo a la frecuencia real del dispositivo. Un plazo mayor permite acumular más
tiempo con el último valor, pero aumenta el riesgo de estimación incorrecta si el
dispositivo deja de informar sin pasar a indisponible.

Si pasa a `unknown`/`unavailable`, deja de acumular en ese instante. Si caduca,
acumula como máximo hasta el vencimiento. Tras reiniciar HA conserva la energía
anterior, pero no reconstruye la potencia durante la parada. Los contadores de
energía acumulada sí pueden aportar incrementos posteriores porque contienen una
medición, sujeta a las comprobaciones de precios y del periodo.

Un cambio de W a kW conserva la magnitud normalizada. Cambiar entre potencia y
contador establece una referencia nueva, sin interpretar W como kWh ni borrar el
consumo anterior. La primera lectura no es consumo: hay que esperar un intervalo
válido para obtener un importe.

## Periodos de factura

El contador físico no tiene que reiniciarse al comenzar la factura: se acumulan sus
incrementos dentro del ciclo mensual o bimestral elegido. Para fechas distintas se
puede cerrar un rango manual con final exclusivo y devengo explícito. Consulta
[históricos](historicos.md). Al cambiar de ciclo, la energía del anterior queda en
su snapshot y no se arrastra como consumo nuevo.

El cierre temporal no garantiza disponer de una lectura exacta en su frontera:
se conserva la condición parcial y no se reconstruye el pasado. Tampoco hay
importación anterior a la instalación.

Referencia del método y sus límites: [documentación oficial de Integral de Home
Assistant](https://www.home-assistant.io/integrations/integration/). La integración
implementa su recogida local; no crea ni modifica ayudantes de HA.
