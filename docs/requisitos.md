# Requisitos y alcance

## Tareas

Crear contratos y grupos sin YAML; elegir tarifa fija, tres periodos o entidad;
estimar energía, potencia y conceptos habilitados; identificar datos ausentes;
conservar histórico y comparar con facturas reales.

## Versión de pruebas

- Contratos independientes, grupos sumados/restados e identidad estable.
- Sensores W/kW y contadores Wh/kWh directos, detección por unidad y grupos mixtos;
  integración temporal estimada con caducidad configurable y sin reconstruir paradas.
- Precios fijos, calendario 2.0TD y entidad dinámica/PVPC; márgenes y unidades.
- Revisiones de precio/descuento por instante y potencia/cuotas por fecha.
- Cargos, bases y perfil fiscal automático/manual con fuente y vigencia.
- Excedentes de mercado libre con precio fijo y compensación simplificada limitada.
- Ciclos mensuales/bimestrales, cierre, exportación, comparación y revisión auditable.
- Sensores por contrato/grupo, diagnósticos, Repairs y almacenamiento local.

## Criterios que no se rebajan

- unknown/unavailable nunca equivale a cero.
- Un precio ausente/caducado no se extrapola.
- Una aproximación temporal se autoriza y se marca parcial.
- No se distinguen reinicio y corrección sin metadatos suficientes; no se inventa consumo.
- Los importes del motor usan Decimal y los instantes comparables usan UTC.
- Se conservan configuración, parámetros fiscales y datos originales de los cierres.
- Las operaciones se limitan a un contrato y no modifican tablas de Recorder.
- La configuración anterior se migra sin borrar sus datos ni cambiar identidades.

La [matriz de cobertura](cobertura.md) es la referencia de funciones soportadas y
exclusiones. Las pruebas de API no acreditan una revisión visual ni equivalencia
universal con las facturas de todas las comercializadoras.
