# Matriz de cobertura

Versión en validación 0.2.0.dev2. Contemplar un caso no significa implementarlo.

| Módulo | Disponible y verificable | Límite actual |
| --- | --- | --- |
| Fija 24 h | Configuración por grupo, precio negativo, revisiones | Sin promociones de duración arbitraria |
| Tres periodos | Calendario 2.0TD y configuración P1/P2/P3 | Península/Baleares, calendario 2026 |
| PVPC | Captura de entidad FEU nativa, sin impuestos | Sin reconstrucción de precios durante paradas |
| Indexada | Entidad con precio contractual y margen adicional | No construye fórmulas comerciales arbitrarias |
| Vivienda/EV | Varios precios y expresiones explícitas sin duplicar energía | Sin cupos promocionales automáticos |
| Potencia | P1/P2, unidad diaria/anual y cambios por fecha | Sin seis periodos ni prorrateo intradía |
| Cargos | Alquiler, cuota diaria y servicio por factura | Sin un catálogo ilimitado de conceptos con bases distintas |
| Descuento | Porcentaje energético con vigencia en el precio | Sin elegibilidad/consumo protegido de bono social |
| Autoconsumo | Contador exportación, precio fijo acordado, límite a energía | No calcula TCUh ni fórmulas PVPC de compensación, sin batería virtual |
| Fiscalidad | Reglas automáticas acotadas, condiciones de potencia y perfil manual documentado | Sin perfiles territoriales/exenciones automáticos |
| Periodos | Mes desplazado/bimestral y cierre manual con fechas reales | Las lecturas en límites pueden requerir aproximación explícita |
| Históricos | Snapshots, exportación, comparación y revisión conservando el original | Sin importación de Recorder/Datadis/CSV |
| Medición | W/kW y Wh/kWh directos, grupos mixtos, huecos, correcciones y persistencia | Potencia estimada, caducidad configurable; no reconstruye paradas ni infiere circuitos duplicados |
| Configuración | Edición de grupos y fuentes, IDs estables, copia anterior | Cambiar fuentes abre un segmento parcial |
| Privacidad | Sin cuentas ni telemetría propias, diagnóstico sin lecturas/nombres | Exportar históricos sí contiene configuración y entidades |

## Qué es precio por horas

Tres precios fijos por franjas, PVPC horario e indexación comercial son modalidades
diferentes. El coste debe usar consumo y precio del mismo intervalo. Un precio
actual no permite reconstruir el pasado. El motor admite reparto temporal solo con
autorización expresa y lo identifica como parcial.

La [descripción oficial de REE](https://www.ree.es/es/operacion/sistema-electrico/pvpc)
y la [integración PVPC de HA](https://www.home-assistant.io/integrations/pvpc_hourly_pricing/)
documentan el precio regulado completo. No equivale al precio OMIE.

## Sin anunciar como terminados

Bono social automático, batería virtual, cuota plana con regularización, fórmulas
especiales de cada comercializadora, peajes 3.0/6.x y fiscalidad territorial automática.
El perfil manual permite aportar una regla explícita; no sustituye la investigación
de bases, condiciones y excepciones que exige cada supuesto.
