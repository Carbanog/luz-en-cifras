# Validación antes del uso habitual

El objetivo es una versión estable con alcance definido, no dejar una versión de
desarrollo indefinidamente. Durante la aceptación se congela el alcance: solo se
corrigen defectos y documentación; nuevas modalidades se desarrollan por separado.

## Antes de instalar

1. Haz una copia de seguridad de tu HA de pruebas y conserva el commit instalado.
2. Anota versión de HA, unidades y frecuencia de actualización de cada sensor.
3. Ten los precios sin impuestos y las fechas de tu contrato. Comprueba si los
   sensores de las filas incluyen ya al coche para no duplicar consumo.
4. Verifica la cobertura fiscal para las fechas de devengo de tus pruebas. No
   extrapoles una regla caducada ni introduzcas porcentajes sin fuente.

## Configuración representativa

Crea un contrato con dos grupos:

- Casa: fila 1 + fila 2, con la tarifa de la vivienda.
- Coche: cargador, con su tarifa. Si está incluido en las filas, réstalo de Casa.

Puedes elegir W/kW o Wh/kWh y mezclarlos. Si tienes contador de energía del mismo
circuito, úsalo como referencia separada para contrastar la estimación desde W;
no lo selecciones junto a su potencia dentro del consumo facturado.

## Prueba durante varios días

| Comprobación | Resultado esperado |
| --- | --- |
| Configurar sin YAML | Completar el asistente, editar y volver a abrir opciones |
| Consumo y precios separados | Casa y coche acumulan sus kWh y costes con los precios elegidos |
| Reiniciar HA | Se conserva la energía previa; no se inventa potencia durante la parada |
| Fuente indisponible/caducada | Advertencia visible; no sustituye la lectura por cero ni prolonga indefinidamente la potencia |
| Cambiar un precio | El consumo anterior conserva su precio |
| Renombrar un grupo | Conserva identidad y consumos |
| Cierre y exportación | Fechas correctas; el original sigue disponible tras una revisión |
| Dashboard | Entidades reales, textos legibles y sin errores en móvil/escritorio |

Registra al inicio y al final: hora, lectura de referencia, kWh por grupo, coste de
energía y calidad/advertencias. Comprueba que ΔkWh y Δcoste concuerdan con las
lecturas y tarifas del mismo intervalo. En W/kW, documenta la frecuencia real de
reporte y cualquier hueco; no exijas igualdad exacta con un contador físico.

No adelantes el reloj de tu HA ni reinicies contadores físicos para forzar un cierre.
El cierre por rango de fechas permite probar el histórico sin esas operaciones.

## Contraste con una factura

Compara energía, potencia, alquiler, descuentos, compensación y cada impuesto por
separado. El periodo y el devengo deben coincidir, igual que precios, bases y
redondeos. El primer ciclo sin histórico anterior no equivale a una factura completa.
Para investigar diferencias comparte solo lecturas/condiciones anonimizadas, sin
CUPS, dirección, DNI, datos bancarios ni respuestas completas del histórico.

## Criterio de promoción

Una versión se considera apta para tu uso habitual después de:

- instalación y configuración verificadas en HA con interfaz real;
- varios días sin pérdidas de datos, duplicidades ni errores de esta integración;
- reinicio/recarga y recuperación comprobados con el respaldo disponible;
- diferencias de cálculo explicadas y sin defectos pendientes que afecten a tu caso;
- reglas fiscales vigentes verificadas para el periodo de uso;
- aprobación del resultado de las pruebas antes de publicar la versión estable.

Los tests automatizados son necesarios, pero no sustituyen estos pasos. Esta guía
no declara que se hayan ejecutado. Las evidencias y su estado se registran en
[pruebas](pruebas.md).
