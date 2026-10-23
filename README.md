# Luz en Cifras

**Entiende de qué está hecha tu factura.**

Luz en Cifras es una integración local para Home Assistant que estima y desglosa
facturas eléctricas españolas a partir de sensores de energía. El nombre y la
identidad técnica `luz_en_cifras` son provisionales hasta completar una búsqueda
formal de marcas.

> Los resultados son estimaciones. No son facturas oficiales ni asesoramiento
> fiscal, contractual o jurídico.

## Estado

**EXPERIMENTAL · EN PRUEBAS.** Este proyecto se desarrolla con ayuda de OpenAI
Codex bajo la dirección de Carbanog. El código generado se revisa y se somete a
pruebas automatizadas; todavía necesita validación con instalaciones y facturas
reales antes de una versión estable. Se recomienda instalarlo primero en un HA de
pruebas. No se ha lanzado la fase final del producto.

Versión de desarrollo `0.1.0`. El núcleo probado admite:

- precios fijos distintos por grupo de consumo;
- contadores independientes y expresiones «contador principal − subcontador»;
- cambios de precio fechados y precios negativos;
- potencia P1/P2 normalizada en €/kW/día;
- cargos por factura o por día y descuentos porcentuales en el motor;
- IVA e Impuesto Especial sobre la Electricidad mediante reglas versionadas;
- periodos irregulares y fechas semiabiertas `[inicio, fin)`;
- calidad completa/parcial y fallo cerrado ante precios o lecturas ausentes.

La conexión inicial con Home Assistant ofrece un `ConfigFlow`, varios contratos,
grupos repetibles, acumulación local persistente y sensores de desglose. Empieza a
observar los contadores al instalarse; el primer periodo se marca como parcial.

No están implementados aún PVPC, tarifas dinámicas desde una entidad, histórico de
facturas cerradas, autoconsumo, bono social, territorios fiscales fuera de IVA
peninsular ni reconstrucción mediante Recorder. Consulta
[`docs/plan-desarrollo.md`](docs/plan-desarrollo.md).

La base apunta a Home Assistant 2026.10.2 o posterior (Python 3.14.2), la versión
estable contrastada durante este corte.

## Instalación manual

1. Descarga el código de una versión o clona el repositorio.
2. Copia la carpeta completa `custom_components/luz_en_cifras` en
   `/config/custom_components/luz_en_cifras` de Home Assistant.
3. Comprueba que `manifest.json` queda directamente dentro de esa carpeta; evita una
   carpeta duplicada como `luz_en_cifras/luz_en_cifras`.
4. Reinicia Home Assistant.
5. Ve a **Ajustes → Dispositivos y servicios → Añadir integración**.
6. Busca **Luz en Cifras** y crea un contrato.

Antes de actualizar, guarda una copia de `/config/.storage`. Para volver atrás,
restaura la carpeta de la versión anterior, reinicia Home Assistant y conserva el
almacenamiento; no borres la entrada de la integración si quieres mantener sus
identificadores.

## Instalación con HACS

Mientras no exista una versión publicada, HACS solo debe usarse con este repositorio
como repositorio personalizado:

1. En HACS abre **Integraciones → menú ⋮ → Repositorios personalizados**.
2. Añade la URL del repositorio y selecciona la categoría **Integración**.
3. Instala **Luz en Cifras**, reinicia Home Assistant y añádela desde
   **Ajustes → Dispositivos y servicios**.

El repositorio tiene la estructura exigida por HACS, pero todavía no se ha
validado como repositorio predeterminado. Añade como repositorio personalizado
[Carbanog/luz-en-cifras](https://github.com/Carbanog/luz-en-cifras).

## Dashboard

Incluimos una [plantilla con tarjetas nativas](examples/dashboard.yaml), sin
dependencias de frontend adicionales. Sustituye los identificadores de ejemplo por
los que aparecen en el dispositivo de tu contrato. La plantilla es una vista para
el editor YAML de un dashboard; no se pega en `configuration.yaml`.

## Límites de la versión de pruebas

- El adaptador actual admite precio fijo por grupo. Cambiar opciones recalcula el
  periodo abierto con esos precios; los cambios contractuales fechados todavía no
  están expuestos en la interfaz.
- Potencia y alquiler se calculan para el periodo contractual completo; el consumo
  corresponde a las lecturas recogidas. El total combina esas dos coberturas.
- Las reglas fiscales incluidas llegan hasta el 31 de octubre de 2026. Después de
  esa fecha la estimación quedará indisponible hasta incorporar reglas verificadas.
- No reconstruye consumos anteriores a la instalación. La primera factura es parcial.
- El cierre de históricos, la conciliación y los diagnósticos descargables están
  pendientes. Esta versión sirve para validar configuración y cálculo inicial.

Para comunicar un problema, indica versión de HA, versión de la integración,
unidades y tipo de contador, pasos para reproducirlo y mensajes anonimizados del
registro. Consulta también [SECURITY.md](SECURITY.md).

## Modelo de grupos

Un grupo suma sus contadores y puede restar subcontadores declarados por el usuario.
Ejemplo:

- Vivienda: `contador_principal - cargador_ev`, a 0,119 €/kWh.
- Vehículo: `cargador_ev`, a 0,075 €/kWh.

La suma económica usa 100 % del contador principal sin cobrar dos veces el vehículo.
La integración no deduce relaciones a partir de nombres de entidades.

## Desarrollo

El motor está dentro de `custom_components/luz_en_cifras/domain` y no importa Home
Assistant. Instala las herramientas con `python -m pip install -e ".[dev]"` y
ejecuta:

```shell
ruff format --check .
ruff check .
mypy
pytest
python -m compileall -q custom_components tests
```

GitHub Actions repetirá estas comprobaciones con Python 3.14 y ejecutará además los
validadores oficiales de Hassfest y HACS. Consulta [CONTRIBUTING.md](CONTRIBUTING.md)
para las reglas de compatibilidad y pruebas.

## Privacidad

No hay cuenta, telemetría ni servidor propio. No se solicita CUPS, DNI o dirección.
Los datos se guardan en el almacenamiento local de Home Assistant. Consulta
[`docs/privacidad.md`](docs/privacidad.md).

## Apoyo opcional

Si el proyecto te resulta útil, puedes apoyar su mantenimiento en
[Buy Me a Coffee](https://buymeacoffee.com/Carbanog). No desbloquea funciones ni
envía datos desde la integración.

## Licencia

[MIT](LICENSE)
