# Arquitectura

## Capas

```text
ConfigFlow / OptionsFlow
        │
        ▼
Adaptador Home Assistant ── eventos de estado ── almacenamiento versionado
        │                          │
        ▼                          ▼
normalización W/kW/Wh/kWh ── intervalos EnergySample
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
El esquema interno 3 conserva un ledger de mediciones, precios y revisiones de
contrato, además de snapshots cerrados. La migración conserva íntegro el payload 0.1.
Las revisiones históricas crean nuevos snapshots con referencia al anterior.

Los intervalos consecutivos dentro de una hora se compactan cuando no hay cambio de
precio ni revisión entre ellos. Así se evita almacenar cada segundo de un contador de alta
frecuencia sin perder fronteras de tarifa. El cálculo sigue siendo proporcional al
ledger del ciclo abierto; no se recorre todo el histórico de facturas cerradas.

El colector mantiene una copia de su configuración hasta terminar la recarga: una
edición de opciones no cambia las fuentes del colector antiguo. Al recargar se guardan
mediciones, fronteras de revisión y contadores pendientes de referencia nueva.
El cálculo aplica cada expresión de fuentes a su ventana temporal, con identidades
internas por tramo y un ID lógico estable por grupo. Las ventanas sin cambios
energéticos se unen para no exigir repartos por un simple renombrado. Un único paso
del motor aplica cargos, límite de compensación e impuestos a toda la factura.

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
a `Decimal`; se detectan unidades W/kW/Wh/kWh. Potencia se integra por regla izquierda
con caducidad desde `last_reported`, nunca renovada por los ticks internos. Las
lecturas restauradas sin confirmación del dispositivo no se integran. Reiniciar
conserva energía anterior pero elimina la continuidad de potencia durante la parada.
Los campos nuevos del ledger son aditivos; los intervalos antiguos mantienen su
tratamiento como mediciones. Lecturas inválidas generan un
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

El asistente sigue el orden mental de leer una factura: modalidad de energía,
periodo, sensores y precios del grupo, unidad y potencias contratadas. Cada pantalla
tiene una decisión principal; los ajustes técnicos se separan en Avanzado. El mes
de referencia solo aparece tras elegir bimestral. P1/P2 de potencia se explican al
lado de sus campos para no confundirlos con P1/P2/P3 de energía. Las ayudas no
dependen de consultar el README. No se cambia el esquema persistente ni los IDs:
las opciones actualizan únicamente los campos del paso editado.
