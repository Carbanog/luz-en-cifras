# Plan de desarrollo

## Fase A — investigación y definición

Estado: **en progreso**. Completados nombre provisional, mapa de producto,
arquitectura, fiscalidad peninsular hasta octubre de 2026 y comparación técnica y de
licencias de los proyectos de referencia.
Pendientes: peajes/cargos, bono social, territorios, PVPC operativo y búsqueda formal
de marca.

## Fase B — motor

Estado: **parcialmente implementado**.

- Hecho: grupos, precios fijos/periodos/cambios, potencia, cargos, descuentos,
  fiscalidad, calidad y 26 pruebas.
- Siguiente: normalizador formal de contadores, tarifas por calendario español,
  autoconsumo y snapshots cerrados.

## Fase C — Home Assistant

Estado: **esqueleto funcional no validado dentro de Home Assistant**.

- Hecho: manifest, flujo visual, varios contratos, grupos, persistencia y sensores.
- Siguiente: entorno de pruebas HA, pruebas de ConfigFlow/OptionsFlow, migraciones,
  diagnósticos, Repairs y recarga automática al editar opciones.

## Fase D — históricos

Pendiente: cierre/reapertura auditable, factura real, diferencias y retención. Antes
de implementarlo se verificará la API pública de estadísticas vigente, que cambió en
Home Assistant 2026.10.

## Fase E — experiencia

Pendiente: validar el flujo nativo en móvil (≈390 px) y escritorio (≈1440 px), temas
claro/oscuro, teclado, zoom y textos largos. Solo después decidir tarjeta Lovelace.

## Fase F — publicación

Repositorio público creado: https://github.com/Carbanog/luz-en-cifras. La CI,
Hassfest, HACS y la importación contra HA 2026.10.2 han pasado. La validación de
comportamiento en una instalación HA sigue pendiente. La versión es experimental.
El alcance completo y las prioridades están en [cobertura.md](cobertura.md).
Las releases estables y el alta en HACS predeterminado quedan para la fase final.
HACS exige una sola integración por
repositorio y todos los archivos de ejecución dentro de
`custom_components/luz_en_cifras`, según su
[documentación](https://www.hacs.xyz/docs/publish/integration/).
