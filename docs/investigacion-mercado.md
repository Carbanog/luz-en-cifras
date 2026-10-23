# Investigación de mercado y nombre

Consulta realizada el 23 de octubre de 2026.

## Nombre

Se descarta **DesglosaLuz** como nombre principal por preferencia del propietario.
La recomendación provisional es **Luz en Cifras**:

- explica que convierte consumo y contrato en información cuantificada;
- evita prometer una factura exacta u oficial;
- se pronuncia y recuerda con facilidad en español;
- permite el dominio estable `luz_en_cifras`.

Las búsquedas exactas en web y repositorios de GitHub no devolvieron coincidencias
relevantes para «Luz en Cifras», «DesglosaLuz» o «CuadraLuz». «CuentaLuz» sí aparece
en otros contextos y se descarta. No aparecieron coincidencias indexadas en búsquedas
dirigidas a OEPM, EUIPO, TMview o WIPO, pero eso **no demuestra disponibilidad
registral**. Antes de publicar se debe hacer una búsqueda profesional por clases y
signos similares, y reservar repositorio y dominio.

## Integraciones próximas

Se revisaron README, manifiestos, estructura de componentes y licencias en las ramas
predeterminadas que cada repositorio exponía el 23 de octubre de 2026. La tabla
distingue ideas reutilizables de dependencias que no conviene introducir.

| Proyecto | Licencia | Patrón aprovechable | Límite para este producto |
|---|---|---|---|
| [Utility Meter](https://www.home-assistant.io/integrations/utility_meter/) | Apache-2.0 (HA Core) | Ciclos, tarifas y advertencia de primer ciclo incompleto | No modela factura contractual española ni fiscalidad |
| [Powercalc](https://github.com/bramstroker/homeassistant-powercalc) | MIT | Entidades virtuales agrupadas, configuración por UI y diagnósticos | Estima energía/potencia de dispositivos, no concilia una factura |
| [Edata](https://github.com/uvejota/homeassistant-edata) | GPL-3.0 | Separación coordinador/entidades, histórico y validación visible de cobertura | Depende de Datadis y su código no se incorpora al proyecto MIT |
| [Dynamic Energy Cost](https://github.com/martinarva/dynamic_energy_cost) | MIT | Cálculo incremental desde sensores de energía o potencia y precio dinámico | No incluye por sí solo todos los términos e impuestos de factura |
| [Dynamic Energy Contract Calculator](https://github.com/bvweerd/dynamic_energy_contract_calculator) | Apache-2.0 | Fuentes repetibles, ajustes contractuales y deltas persistentes | Sus presets y reglas se orientan a otros mercados |

### Decisión

No se ha copiado ni adaptado código de estos proyectos. Luz en Cifras acepta las
entidades que publiquen mediante las APIs públicas de Home Assistant y mantiene un
motor de dominio propio y probado. Utility Meter confirma una expectativa
importante: el primer ciclo tras activar un contador es incompleto; el producto debe
decirlo expresamente. Edata documenta además el riesgo de sumar un contador de red y
sus subconsumos dos veces, que aquí se modela con expresiones explícitas. Los
proyectos de coste dinámico refuerzan la decisión de guardar deltas con el precio
vigente, en vez de revalorizar todo un periodo con el último precio conocido.

Las licencias se registran para trazabilidad; esta comparación no concede ni exige
compatibilidad de código porque la implementación es independiente.
