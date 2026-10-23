# Cobertura funcional y módulos

El objetivo es una integración configurable para contratos españoles. Cada usuario
activará únicamente los módulos que necesite. Esta matriz describe la versión de
pruebas: contemplar un supuesto no significa haberlo implementado.

| Módulo | Situación real | Condición para considerarlo completo |
| --- | --- | --- |
| Precio fijo 24 h | Configurable | Validación en HA y con factura anonimizada |
| Tres periodos | Motor probado con periodos explícitos; sin calendario/UI | Calendario territorial, festivos y asignación de cada intervalo |
| PVPC horario | Pendiente | Serie PVPC oficial o entidad compatible, cobertura y precio por intervalo |
| Indexada mercado libre | Pendiente | Fórmula contractual, márgenes, costes incluidos e impuestos explícitos |
| Horarios personalizados/EV | Precio fijo por grupo disponible | Horarios y vigencias por grupo; promociones limitadas y caducidad |
| Cuota plana | Pendiente | Separar pago de cuota, coste devengado y regularización |
| Potencia | P1/P2 fijas en €/kW/día | Cambios fechados, conversión anual y otros periodos cuando proceda |
| Peajes/cargos | Sin desglose independiente | Evitar cobrarlos dos veces si ya están en el precio final |
| Descuentos y servicios | Estructuras parciales en motor | Importes fijos/porcentajes, bases, límites, fechas y edición visual |
| Autoconsumo | Pendiente | Importación/exportación separadas y compensación con límite documentado |
| Batería virtual | Pendiente | Saldo y reglas comerciales separados de compensación legal |
| Bono social | Pendiente | Elegibilidad explícita, descuentos, límites y vigencia verificables |
| Fiscalidad | Reglas parciales de 2026 | Condiciones por contrato, territorio, exenciones y distintas bases |
| Periodos | Ciclo mensual desplazado en UI | Bimestral, irregular y cierre con fechas reales |
| Históricos/conciliación | Pendiente | Snapshot de precios/impuestos, total real y reapertura auditable |
| Medición | Acumulados Wh/kWh | Normalización, reinicios, correcciones, huecos y pruebas HA |
| Configuración editable | Parcial | Edición de fuentes y grupos, migraciones y conservación de datos |

## Qué significa tarifa por horas

Hay tres casos diferentes que se deben configurar por separado:

1. **Tres precios por franjas**: punta, llano y valle, con el calendario aplicable.
2. **PVPC**: precio regulado publicado para cada hora; no equivale al precio OMIE.
3. **Indexada o dinámica de mercado libre**: precio por intervalo y fórmula propia
   del contrato, incluidos márgenes y conceptos adicionales.

La descripción oficial de [REE sobre PVPC](https://www.ree.es/es/operacion/sistema-electrico/pvpc)
confirma la publicación horaria y su composición. Consulta realizada el 23/10/2026.

El coste debe sumar consumo de cada intervalo × precio de ese mismo intervalo.
Un precio actual no permite reconstruir consumos antiguos. Se requieren historial
de precios, unidades €/kWh o €/MWh, indicación de impuestos incluidos y cobertura.
Los intervalos deben distinguir horas repetidas/ausentes en cambios de hora y
respetar la resolución realmente disponible. Cuando una lectura atraviese varios
precios sin desglose suficiente, debe declararse aproximación o dato insuficiente.

## Prioridad de desarrollo

1. Consolidar medición, vigencias y persistencia; cubrir eventos y reinicios con HA.
2. Configurar tres periodos y precio dinámico con trazabilidad por intervalo.
3. Integrar PVPC e indexadas y completar la edición de contratos sin revalorar el pasado.
4. Añadir cierre histórico, conciliación, conceptos opcionales y autoconsumo.
5. Ampliar reglas territoriales y supuestos especiales mediante fuentes y pruebas.

La versión final debe publicar una lista de compatibilidad verificable. No se
promete soporte universal para cualquier cláusula comercial: los casos sin reglas
o datos suficientes deberán identificarse expresamente como no soportados.
