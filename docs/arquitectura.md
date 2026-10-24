# Arquitectura

## Capas

```text
ConfigFlow / OptionsFlow
        │
        ▼
Adaptador Home Assistant ── eventos de estado ── almacenamiento versionado
        │                          │
        ▼                          ▼
normalización Wh/kWh ─────── intervalos EnergySample
        │
        ▼
motor de dominio puro ── tarifas ── fiscalidad ── InvoiceResult
        │
        ▼
sensores de contrato + diagnóstico de calidad
```

`domain/` no importa Home Assistant. Recibe datos completos e inmutables y devuelve
líneas trazables. El adaptador es responsable de unidades, estados y persistencia.

## Persistencia

Un `Store` por `ConfigEntry` conserva versión, periodo, últimas lecturas, intervalos
y advertencias. Las escrituras se agrupan con retraso de 10 segundos y se vacían antes
de recargar o descargar la entrada. No se consulta Recorder ni se accede a sus tablas.
El esquema interno 2 conserva un ledger de mediciones, precios y revisiones de
contrato, además de snapshots cerrados. La migración conserva íntegro el payload 0.1.
Las revisiones históricas crean nuevos snapshots con referencia al anterior.

Los intervalos consecutivos dentro de una hora se compactan cuando no hay cambio de
precio entre ellos. Así se evita almacenar cada segundo de un contador de alta
frecuencia sin perder fronteras de tarifa. El cálculo sigue siendo proporcional al
ledger del ciclo abierto; no se recorre todo el histórico de facturas cerradas.

## Identidad y compatibilidad

- dominio: `luz_en_cifras`;
- contrato: UUID persistente;
- entidad: `{contract_uuid}_{sensor_key}`;
- renombrar el contrato no cambia `unique_id`;
- esquema de configuración y almacenamiento versionados desde 1.

## Modelo de fuentes

Cada grupo es una combinación lineal de contadores añadidos y subcontadores
restados. Se rechaza un coeficiente final superior a uno (posible cobro doble) y un
resultado negativo (relación físicamente imposible con esas lecturas). No se infiere
la topología por nombres.

## Seguridad y fallos

No hay red, credenciales ni evaluación de fórmulas. Entradas numéricas se convierten
a `Decimal`; entidades se limitan a energía Wh/kWh. Lecturas inválidas generan un
estado explícito. Las reglas fiscales condicionales desconocidas fallan cerradas.

## Decisión UX

Tesis visual: **la estimación debe leerse como una factura anotada, donde cada euro
puede rastrearse hasta consumo, regla y nivel de confianza**.

Se estudiaron tres direcciones:

1. factura anotada, orden vertical y desglose progresivo;
2. línea temporal del periodo, centrada en evolución diaria;
3. tablero modular de grupos, centrado en comparación técnica.

Se elige la primera para la vista principal por comprensión y accesibilidad. La
línea temporal será secundaria y el tablero de grupos quedará para opciones
avanzadas. Se evita una cuadrícula genérica de KPI. En el MVP se usan entidades y
formularios nativos; una tarjeta propia solo se justificará tras validar límites
reales de Lovelace.
