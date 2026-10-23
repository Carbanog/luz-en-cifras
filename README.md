<div align="center">

<img src="custom_components/luz_en_cifras/brand/icon.png" alt="Luz en Cifras" width="96">

# Luz en Cifras

**Entiende de qué está hecha tu factura eléctrica.**

Consumo, potencia e impuestos en Home Assistant, con cálculo local y desglose visible.

[![CI](https://github.com/Carbanog/luz-en-cifras/actions/workflows/ci.yml/badge.svg)](https://github.com/Carbanog/luz-en-cifras/actions/workflows/ci.yml)
[![HA y HACS](https://github.com/Carbanog/luz-en-cifras/actions/workflows/validate.yml/badge.svg)](https://github.com/Carbanog/luz-en-cifras/actions/workflows/validate.yml)
![Estado: experimental](https://img.shields.io/badge/estado-en_pruebas-e9a23b)
[![MIT](https://img.shields.io/badge/licencia-MIT-blue)](LICENSE)

[Instalar](#instalación) · [Configurar](#configuración) · [Dashboard](#dashboard) · [Limitaciones](#limitaciones) · [Incidencias](https://github.com/Carbanog/luz-en-cifras/issues)

</div>

> [!WARNING]
> **Experimental · 0.1.0 · Instalar primero en un HA de pruebas.**
> La fase final todavía no se ha lanzado. Los importes son estimaciones y necesitan
> contraste con facturas reales; no sustituyen la factura de tu comercializadora.

## Qué puedes probar

La integración convierte sensores de energía acumulada en una estimación de factura
eléctrica española. Funciona localmente, sin cuentas ni credenciales externas.

| Función | Disponible hoy |
| --- | --- |
| Contratos | Varias configuraciones independientes |
| Grupos de consumo | Suma de contadores y resta explícita de subcontadores |
| Energía | Precio fijo diferente por grupo, incluido precio negativo |
| Potencia | P1/P2 con precios en €/kW/día |
| Alquiler | Cargo diario configurable |
| Impuestos | IVA e impuesto eléctrico con reglas fechadas |
| Persistencia | Consumos guardados localmente entre reinicios |
| Desglose | Sensores de energía, potencia, impuestos y calidad de datos |

El motor también tiene soporte probado para cambios de precio fechados, cargos por
factura y descuentos. Su configuración completa desde la interfaz está pendiente.
Consulta el [plan de desarrollo](docs/plan-desarrollo.md).

## Instalación

**Referencia de compatibilidad: Home Assistant 2026.10.2**, Python 3.14.2 o posterior.
Otras versiones de HA requieren validación. Necesitas un sensor de energía
acumulada con clase `energy` y unidad **Wh o kWh**. Un sensor en W mide potencia
y no sirve directamente como contador.

### Con HACS · repositorio personalizado

1. En HACS abre **⋮ → Repositorios personalizados**.
2. Añade esta dirección con categoría **Integración**:

   ```text
   https://github.com/Carbanog/luz-en-cifras
   ```

3. Busca **Luz en Cifras**, descárgala y reinicia Home Assistant.
4. Ve a **Ajustes → Dispositivos y servicios → Añadir integración**.
5. Busca **Luz en Cifras** y crea tu contrato.

Todavía no pertenece al catálogo predeterminado de HACS. Durante las pruebas las
actualizaciones proceden de la rama `main`.

<details>
<summary><strong>Instalación manual</strong></summary>

1. [Descarga el código](https://github.com/Carbanog/luz-en-cifras/archive/refs/heads/main.zip) y descomprímelo.
2. Copia `custom_components/luz_en_cifras` dentro de tu directorio de configuración.
3. Comprueba la estructura y reinicia Home Assistant:

   ```text
   config/
   └── custom_components/
       └── luz_en_cifras/
           ├── manifest.json
           ├── __init__.py
           ├── config_flow.py
           └── …
   ```

4. Añade la integración desde **Ajustes → Dispositivos y servicios**.

Evita copiar el repositorio completo en `custom_components` o duplicar la carpeta.

</details>

## Configuración

Ten a mano tu contrato o factura e introduce **precios sin impuestos**.

| Campo | Qué introducir |
| --- | --- |
| Nombre | Un nombre reconocible: Casa, Garaje… |
| Día de inicio | Día del mes en que comienza el ciclo |
| Potencia P1/P2 | Potencia contratada en kW por periodo |
| Precio P1/P2 | Precio de potencia en **€/kW/día** |
| Alquiler | Importe diario del contador, sin IVA |
| Grupos | Contadores que suman o restan y precio en **€/kWh** |

Puedes añadir varios grupos antes de guardar. Encontrarás el dispositivo del
contrato y sus sensores en **Ajustes → Dispositivos y servicios**.

### Ejemplo: vivienda y vehículo eléctrico

Si el contador principal ya incluye el cargador:

| Grupo | Consumo | Precio ilustrativo |
| --- | --- | --- |
| Vivienda | Principal − cargador | 0,119 €/kWh |
| Vehículo | Cargador | 0,075 €/kWh |

Sustituye esos precios por los de tu contrato. Este reparto evita cobrar dos veces
el consumo del vehículo. La integración no deduce relaciones por nombres.

> [!TIP]
> La primera lectura establece el punto de partida. Espera nuevos cambios del
> contador para comprobar la acumulación. El periodo inicial será parcial.

## Dashboard

La [plantilla de dashboard](examples/dashboard.yaml) utiliza **tarjetas nativas**:
resumen del contrato, calidad de datos, desglose y evolución del importe.
No requiere tarjetas adicionales de HACS.

1. Copia los identificadores de las entidades desde el dispositivo del contrato.
2. Sustituye **todas** las entidades `sensor.mi_contrato_*` de la plantilla.
3. Incorpora la vista al dashboard YAML, dentro de su lista `views:`.

Los identificadores dependen del contrato y del registro de entidades de HA.
La plantilla requiere esa adaptación; **no se pega en `configuration.yaml`**.

## Limitaciones

| Situación | Comportamiento actual |
| --- | --- |
| Primer periodo | Parcial; sin consumo anterior a la instalación |
| Potencia y alquiler | Cubren el ciclo completo, aunque el consumo sea parcial |
| Editar precios | Recalcula el periodo abierto con los nuevos valores |
| Fiscalidad desde noviembre de 2026 | Sin regla verificada: importe indisponible |
| Cierre de ciclo | Nuevo periodo; sin archivo de facturas cerradas todavía |
| PVPC y precio dinámico desde entidades | Pendientes |
| Excedentes, batería virtual y bono social | Pendientes |
| Canarias, Ceuta y Melilla | Pendientes; solo fiscalidad de territorio IVA |
| Histórico Recorder y comparación con factura real | Pendientes |

Las reglas fiscales incluidas llegan **hasta el 31 de octubre de 2026**.
[Fuentes y criterios fiscales](docs/reglas-fiscales.md).

La edición de precios por grupo todavía muestra identificadores técnicos
`price_…`; su presentación se mejorará antes de la fase estable.

<details>
<summary><strong>Resolución de problemas</strong></summary>

- **No aparece:** comprueba la ruta de `manifest.json`, reinicia HA y revisa el registro.
- **No puedes elegir un contador:** debe medir energía acumulada en Wh o kWh.
- **El consumo no cambia:** espera nuevos cambios; no se reconstruye el pasado.
- **Importe indisponible:** consulta el sensor de calidad y atributos `error` y `warnings`.
- **No coincide con la factura:** revisa cobertura, unidades y precios sin impuestos.

Para [abrir una incidencia](https://github.com/Carbanog/luz-en-cifras/issues),
incluye versiones de HA e integración, pasos para reproducir, unidades y mensajes
anonimizados. Evita facturas completas o datos personales.

</details>

## Actualización y recuperación

Haz una copia de seguridad de HA antes de actualizar. Con HACS, descarga la
actualización y reinicia; manualmente, reemplaza la carpeta de la integración.
Conserva la versión anterior para restaurarla si es necesario.

No elimines la entrada para actualizar: eliminarla borra su almacenamiento asociado.
Conserva el respaldo de HA para recuperar también los datos.

## Desarrollo y transparencia

Desarrollado **con ayuda de OpenAI Codex**, bajo la dirección de **Carbanog**.
La asistencia de IA forma parte de la implementación y documentación. Las pruebas
automatizadas verifican parte del comportamiento; la validación real con HA y
facturas sigue siendo necesaria antes de considerar el producto estable.

El motor usa `Decimal` y está separado del adaptador HA. La CI comprueba formato,
análisis estático, tipos y pruebas, e importa la integración contra HA de referencia.
Otro flujo ejecuta Hassfest y HACS.

```shell
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy
pytest
```

[Contribuir](CONTRIBUTING.md) · [Arquitectura](docs/arquitectura.md) ·
[Referencias y licencias](docs/investigacion-mercado.md) · [Cambios](CHANGELOG.md) ·
[Seguridad](SECURITY.md)

## Privacidad

Sin CUPS, DNI, dirección, credenciales, telemetría ni servidor propio.
Los datos se guardan en Home Assistant. [Más información](docs/privacidad.md).

## Apoyar el proyecto

Si te resulta útil, puedes apoyar su mantenimiento con un café. Es opcional;
todas las funciones están disponibles sin aportaciones.

[☕ Invítame a un café en Buy Me a Coffee](https://buymeacoffee.com/Carbanog)

---

Hecho por **Carbanog**, con ayuda de **Codex** · [Licencia MIT](LICENSE)
