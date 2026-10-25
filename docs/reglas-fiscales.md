# Impuestos manuales

Desde **0.3.1**, los contratos nuevos usan los impuestos que introduces y confirmas.
Se calculan localmente, también con tarifa fija; no se consulta el INE ni ningún
servicio fiscal. PVPC es una función distinta: descarga precios de energía.

## Qué poner

| Campo | Dato de tu factura |
| --- | --- |
| Impuesto eléctrico (%) | Porcentaje, no euros; por ejemplo `5,11269632` |
| IVA / impuesto indirecto (%) | Porcentaje, por ejemplo `21`, no `0,21` |
| Mínimo de impuesto eléctrico (€/MWh) | Mínimo aplicable por energía; `1` equivale a 0,001 €/kWh |

Los ejemplos son orientativos. Debes revisar los tuyos y marcar la confirmación.
El cálculo eléctrico aplica el mayor entre el porcentaje sobre su base y el mínimo
por energía. IVA se aplica a las bases que contempla el motor, incluido el impuesto
eléctrico; configurar un porcentaje no implementa bases territoriales o exenciones
que la integración no admite.

No hay fecha de caducidad. Se mantienen hasta que los cambies en **Configurar →
Impuestos de la factura**. Las modificaciones recalculan la factura abierta;
los cierres guardados mantienen los impuestos y resultados originales. Si necesitas
revisar un cierre, utiliza la acción de recálculo, que conserva el original.
El historial identifica esta procedencia como `manual:contract`, sin atribuirla a
una validación oficial automática.

## Actualizar un contrato existente

Los antiguos contratos automáticos pasan a configuración manual **sin confirmar**.
La migración propone los valores que se aplicaban cuando están disponibles; si no,
propone valores orientativos que también debes comprobar. No los da por aceptados.

1. Abre Luz en Cifras → Configurar → Impuestos de la factura.
2. Revisa los tres valores, marca la confirmación y guarda el contrato.
3. Espera una lectura nueva y comprueba Calidad de los datos y el total estimado.

Mientras no confirmas se mantienen las mediciones e históricos y aparece un aviso
Repairs. El total queda pendiente; no se calculan impuestos cero por ausencia de
confirmación. Después no se vuelve a pedir confirmación cada mes.

Si utilizabas el antiguo perfil manual avanzado con fechas y fuente, se conserva
por compatibilidad. Guardar el formulario nuevo lo convierte a porcentajes sin
caducidad, conservando los consumos. No hay que borrar ni volver a crear el contrato.

## Histórico de reglas anteriores a 0.3.1

Las reglas siguientes permanecen únicamente para reproducir cálculos antiguos que
ya guardaron ese modo. No son el mecanismo de impuestos de los nuevos contratos y
no imponen un límite temporal al modo manual actual.


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
