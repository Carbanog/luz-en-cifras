# Contribuir

Gracias por ayudar a mejorar Luz en Cifras. Antes de abrir un cambio, separa con
claridad un error de cálculo, un problema de integración con Home Assistant y una
petición de compatibilidad contractual.

## Organización del repositorio

`main` conserva los cambios integrados; las etiquetas y releases identifican las
versiones instalables. Crea una rama temporal para cada PR: GitHub la elimina al
fusionarla. No guardes copias de HA, credenciales ni datos personales en el
repositorio. Antes de confirmar, revisa el diff y usa el correo privado de GitHub
para la autoría de los commits.

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

Las pruebas contra Home Assistant requieren un entorno separado para evitar
mezclar las versiones de sus dependencias con las herramientas de desarrollo:

```shell
python -m pip install pytest-homeassistant-custom-component==0.13.373
python -m pytest -c tests_ha/pytest.ini tests_ha -q
```

Consulta [la guía de pruebas](docs/pruebas.md) para el laboratorio aislado y las
limitaciones de la comprobación visual. Los sensores de los tests son fixtures
sintéticos; no sustituyen una validación con facturas reales anonimizadas.

Toda nueva regla económica debe incluir casos de límite: comienzo y final del
periodo, cambio de precio o impuesto, datos ausentes, redondeo y valores negativos
cuando sean válidos. No se aceptan fórmulas fiscales sin una fuente oficial fechada.

## Cambios de datos

El identificador técnico `luz_en_cifras`, los `unique_id` y las claves persistidas
forman parte de la compatibilidad. Cualquier cambio requiere una migración explícita
y pruebas que demuestren que una instalación existente conserva su historial.

## Publicar una versión

Cada actualización instalable se publica como una release de GitHub; un push a
`main` o una etiqueta sin release no sustituyen este paso. La publicación requiere
autorización del mantenedor y los controles del commit deben haber terminado bien.

1. Incrementa la versión en `manifest.json`, `pyproject.toml` y `diagnostics.py`.
   Usa parches para correcciones compatibles y versiones menores para capacidades
   nuevas; registra cambios, límites, compatibilidad y recuperación en las notas.
2. Actualiza README, changelog y requisitos de `hacs.json` cuando corresponda.
3. Revisa la PR y espera calidad, pruebas con HA, Hassfest y HACS en verde. Integra
   y comprueba también los controles del commit final en `main`.
4. Crea la etiqueta y la release con **exactamente la versión del manifiesto** y el
   SHA validado como destino. Nunca muevas una etiqueta publicada ni sustituyas sus
   archivos: una corrección necesita otra versión.
5. Verifica que la release está publicada, apunta al SHA previsto y ofrece el código
   fuente. La estructura actual permite a HACS instalar desde la etiqueta sin un
   ZIP específico. Conserva las releases anteriores.

Las notas deben indicar reinicio de HA, copia de seguridad y migraciones necesarias.
Una release publicada no significa que se haya desplegado en el HA del usuario ni
que la aceptación con sus dispositivos se haya completado. No publiques para probar
un commit: utiliza CI o el laboratorio aislado durante el desarrollo.
