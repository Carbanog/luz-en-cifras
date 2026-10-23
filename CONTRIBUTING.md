# Contribuir

Gracias por ayudar a mejorar Luz en Cifras. Antes de abrir un cambio, separa con
claridad un error de cálculo, un problema de integración con Home Assistant y una
petición de compatibilidad contractual.

## Entorno

Se requiere Python 3.14.2 o posterior, igual que la versión de Home Assistant usada
como referencia.

```shell
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

En Windows, el intérprete creado está en `.venv\Scripts\python.exe`.

## Comprobaciones

```shell
ruff format --check .
ruff check .
mypy
pytest
python -m compileall -q custom_components tests
```

Toda nueva regla económica debe incluir casos de límite: comienzo y final del
periodo, cambio de precio o impuesto, datos ausentes, redondeo y valores negativos
cuando sean válidos. No se aceptan fórmulas fiscales sin una fuente oficial fechada.

## Cambios de datos

El identificador técnico `luz_en_cifras`, los `unique_id` y las claves persistidas
forman parte de la compatibilidad. Cualquier cambio requiere una migración explícita
y pruebas que demuestren que una instalación existente conserva su historial.
