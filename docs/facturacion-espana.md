# Facturación eléctrica española

Conceptos que modela la integración. Consulta la [matriz de cobertura](cobertura.md)
para conocer las modalidades disponibles y sus límites, y la
[guía de impuestos manuales](reglas-fiscales.md) para configurar los de tu factura.

## Estructura comprobada

La [CNMC](https://www.cnmc.es/en/node/406175) distingue el término fijo de potencia
y el término variable de energía; peajes y cargos se trasladan mediante ambos y
deben aparecer desglosados. La factura incluye además impuesto eléctrico, alquiler
del contador cuando corresponda e IVA. En mercado libre pueden existir cuotas,
servicios, descuentos y fórmulas contractuales propias.

La integración representa:

1. energía por grupo e intervalo;
2. potencia P1/P2 en €/kW/día o €/kW/año;
3. cargos fijos diarios o por factura;
4. descuentos antes de impuestos;
5. impuesto eléctrico e IVA manuales, conservados en las facturas cerradas.

Introduce precios contractuales completos sin impuestos. No vuelvas a sumar los
peajes, cargos o márgenes que ya estén incluidos en esos precios.

## PVPC

El [Real Decreto 446/2023](https://www.boe.es/eli/es/rd/2023/06/13/446) introdujo
la cesta de productos a plazo en el PVPC. En 2026 el coste de producción combina
mercados diario/intradiario, ajuste a plazo, servicios de ajuste y otros costes. No
es correcto multiplicar el consumo mensual por el precio de la última hora.
Luz en Cifras obtiene la serie horaria directamente de REE o utiliza una entidad de
precio existente. [Fuente, caché y límites](tarifas.md).

## Autoconsumo

El artículo 14 del [Real Decreto 244/2019](https://boe.es/buscar/act.php?id=BOE-A-2019-5089&p=20260321&tn=1)
define la compensación simplificada como saldo económico y limita el valor de los
excedentes al valor económico de la energía consumida de red en el periodo. Las
baterías virtuales son productos comerciales adicionales, no una regla legal
general. La compensación disponible utiliza un contador de exportación separado y
un precio fijo acordado; no incluye batería virtual ni cálculo de TCUh.

## Medición y periodos

- Periodos internos semiabiertos: inicio incluido, fin excluido.
- Días de potencia: días naturales exactos, sin convertir horas DST en fracciones.
- Energía dinámica: se valora el intervalo con el precio vigente en ese intervalo.
- Potencia instantánea: Home Assistant recomienda convertirla a energía mediante
  [integración de suma de Riemann](https://www.home-assistant.io/docs/energy/individual-devices/);
  no se tratará W como kWh.
- Los datos purgados por Recorder no se prometerán reconstruibles.

## Casos que requieren configuración o desarrollo adicional

- fórmulas comerciales y compensación PVPC con TCUh;
- bono social, financiación y límites vigentes;
- peajes/cargos cuando el contrato no los incorpore al precio;
- territorios con IGIC/IPSI y exenciones;
- redondeo contractual por comercializadora;
- refacturaciones, mora y cambios contractuales complejos.
