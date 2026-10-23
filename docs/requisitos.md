# Requisitos y alcance

## Personas y tareas

Usuario principal: residente en España con Home Assistant, capaz de identificar sus
sensores pero no necesariamente de editar YAML. Tareas prioritarias:

1. saber cuánto lleva acumulado en el periodo;
2. entender energía, potencia e impuestos;
3. separar vivienda, vehículo y otros consumos con precios propios;
4. detectar datos incompletos o doble contabilización;
5. comparar más adelante la estimación con la factura real.

## MVP actual

- varios contratos independientes;
- configuración visual de uno o más grupos;
- sensores acumulativos Wh/kWh;
- sumas y restas explícitas de fuentes;
- precio fijo por grupo;
- potencia P1/P2, alquiler diario e impuestos peninsulares verificados;
- sensores de total, desglose, consumo y calidad;
- almacenamiento local, sin PII ni telemetría.

## Fuera del MVP actual

- tarifa de tres periodos en la UI (el motor ya la admite);
- precio dinámico/PVPC, potencia instantánea y exportación;
- descuentos/cargos arbitrarios en la UI (el motor ya admite su estructura);
- cierre histórico, factura real, CSV/Datadis, Repairs y migraciones;
- edición visual de topología después de crear el contrato;
- tarjeta Lovelace propia.

Estas ausencias deben mostrarse como limitaciones, nunca como funciones simuladas.

## Criterios de calidad

- un `unknown`/`unavailable` nunca equivale a cero;
- una tarifa ausente invalida el resultado;
- el primer periodo es parcial;
- IDs de contrato y entidades no dependen del nombre visible;
- ningún dato económico usa `float` dentro del motor;
- cada preset fiscal tiene fuente y vigencia;
- la integración no modifica Recorder ni bases de datos internas.
