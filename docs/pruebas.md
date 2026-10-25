# Pruebas y desarrollo

El producto se instala por HACS. Docker es una herramienta opcional de desarrollo;
los fixtures de `tests/`, `tests_ha/` y `lab/` son sintéticos y no se instalan como
sensores del usuario.

## Comprobaciones de 0.3.1

La versión pasa **79 pruebas del motor** y **45 pruebas de integración en cada una**
de las siguientes versiones de Home Assistant:

| Home Assistant | pytest-homeassistant-custom-component |
| --- | --- |
| 2026.10.2 | 0.13.373 |
| 2026.10.3 | 0.13.374 |
| 2026.10.4 | 0.13.375 |

También pasan Ruff (formato y análisis), mypy sobre el dominio, validación JSON,
importación del componente en HA, HACS y Hassfest. Los resultados se consultan por
commit en [CI](https://github.com/Carbanog/luz-en-cifras/actions/workflows/ci.yml) y
[validación HA/HACS](https://github.com/Carbanog/luz-en-cifras/actions/workflows/validate.yml).
Esto no acredita compatibilidad con versiones de HA que no figuren en la matriz.

## Ejecutar el motor

Con Python 3.14.2 o posterior, desde la raíz del repositorio:

```shell
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy
pytest tests
```

## Ejecutar las pruebas de Home Assistant

Utiliza un entorno virtual separado del motor, porque los fixtures de HA fijan sus
propias dependencias. Por ejemplo, para HA 2026.10.4:

```shell
python -m pip install pytest-homeassistant-custom-component==0.13.375 esios-api==4.4.0
python -m pytest -c tests_ha/pytest.ini tests_ha -q
```

Para las otras versiones usa el paquete correspondiente de la tabla. La matriz
exacta está en [ci.yml](../.github/workflows/ci.yml).

Como alternativa, [Dockerfile.test](../Dockerfile.test) permite seleccionar el
paquete con `--build-arg HA_TEST_VERSION=0.13.375`. Monta el repositorio de solo
lectura en `/workspace`; no necesita puertos, credenciales, datos del usuario ni
contenedores privilegiados. El [laboratorio completo](../lab/README.md) es opcional
para desarrollar o revisar la interfaz, no un requisito de instalación.

## Cobertura funcional

- Precio fijo, tres periodos 2.0TD y precios dinámicos por intervalo.
- W/kW y Wh/kWh, grupos sumados/restados, fuentes mixtas y precios independientes.
- Reinicios, huecos, caducidad, correcciones y estados restaurados, sin inventar consumo.
- Cambios de sensores, grupos y tarifas conservando el consumo y precio de cada tramo.
- Potencia, cuotas, descuentos, impuestos manuales y compensación limitada de excedentes.
- Configuración guiada, edición, migración, confirmación fiscal y aviso Repairs.
- Cierres mensuales/bimestrales, exportación y revisiones que conservan el original.
- Cambio de hora, fechas límite, redondeos y lecturas que requieren reparto estimado.
- Persistencia y recálculo después de descargar y volver a cargar la integración.

### Simulación de periodos completos

`tests_ha/test_accelerated_acceptance.py` ejecuta 61 días sintéticos en un HA
controlado por pytest: septiembre y octubre, la hora adicional de otoño, dos cierres
mensuales o uno bimestral y recarga del colector. Contrasta resultados analíticos:
864 kWh en septiembre, 894 kWh en octubre y 1758 kWh en el bimestre, con potencias
sintéticas constantes de 1 kW y 0,2 kW. Potencia, alquiler y cuotas se cuentan una
sola vez por factura según corresponda.

La suite también comprueba continuidad de impuestos manuales en noviembre,
diciembre y cambio de año. Los porcentajes futuros son valores de prueba, no
predicciones fiscales. No se modifica el reloj del HA del usuario.

### PVPC directo

`tests_ha/test_pvpc_direct.py` verifica precio horario, caché tras recarga sin red,
fallo inicial conservando mediciones, recuperación, día siguiente sin precios,
cambio a entidad y cancelación. El cliente valida calendarios de 23/24/25 horas;
los contratos fijos no crean un cliente de red. Las respuestas de red de las
pruebas son fixtures explícitos.

Separadamente, el 24 de octubre de 2026 se verificó una descarga real de REE con
24 precios horarios y `esios-api==4.4.0`. La integración mantiene su requisito mínimo
compatible con el de HA. [Fuente y comportamiento sin conexión](tarifas.md).

## Interfaz y comprobación con datos reales

Las [capturas de escritorio y móvil](dashboards.md) proceden de un HA con consumos
simulados identificados como PRUEBA. Las pruebas de flujos usan las APIs reales de
HA, pero no sustituyen una revisión visual ni una comparación con facturas.

Para revisar tu instalación usa la [guía de comprobación](validacion-en-ha.md).
No se afirma equivalencia universal con todas las comercializadoras. Las modalidades
soportadas y sus límites se detallan en la [matriz de cobertura](cobertura.md).
