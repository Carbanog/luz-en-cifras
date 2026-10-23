# Reglas fiscales

Última verificación: 23 de octubre de 2026. Ámbito implementado: suministros
domésticos sujetos a IVA en territorio peninsular/Baleares, sin exenciones.

## Principio de diseño

Cada regla tiene identificador, vigencia semiabierta, fuente y tipos. La selección se
hace por **fecha de devengo**. La [nota informativa 09/2026 de la AEAT](https://sede.agenciatributaria.gob.es/static_files/Sede/Tema/Aduanas/Notas_info/NI_2026/ni_9_26.pdf)
explica que, habitualmente, el impuesto eléctrico se devenga cuando resulta exigible
el precio/fecha de factura, aunque el suministro cubra días anteriores. Por ello no
se fracciona automáticamente el impuesto por días de consumo.

## Reglas verificadas incluidas

| Devengo | IEE | IVA | Evidencia |
|---|---:|---:|---|
| 01/01–21/03/2026 | 5,11269632 % | 21 % | régimen ordinario |
| 22/03–31/05/2026 | 0,5 % | 10 % | RDL 7/2026; condición de junio desactivada |
| 01/06–31/10/2026 | 5,11269632 % | 21 % | AEAT confirma restitución desde junio |

Fuentes: [tipo del impuesto eléctrico, AEAT](https://sede.agenciatributaria.gob.es/Sede/impuestos-especiales-medioambientales/impuesto-especial-sobre-electricidad/liquidacion-pago-impuesto/tipo-impositivo.html),
[IVA 2026, AEAT](https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-iva-2026/capitulo-01-novedades-destacar-2026/tipos-impositivos.html)
y [RDL 25/2026](https://www.boe.es/buscar/act.php?id=BOE-A-2026-20265&lang=es&p=20260930&tn=1).

Para uso doméstico el mínimo del IEE es 1 €/MWh. El motor aplica el mayor entre el
porcentaje de la base configurada y el mínimo por energía.

## Periodos no codificados

Noviembre y diciembre de 2026 dependen de condiciones mensuales del IPC establecidas
por el RDL 25/2026. Aunque el INE ya publicó el IPC general de septiembre, el
resultado oficial específico para el tipo aplicable no estaba localizado en la
página de AEAT consultada. El registro termina el 1 de noviembre y falla de forma
explícita en vez de adivinar. Diciembre tampoco puede resolverse aún en la fecha de
consulta.

Canarias, Ceuta y Melilla, bono social, exenciones y usos industriales no están
implementados. La interfaz no debe ofrecerlos hasta disponer de reglas y pruebas.
