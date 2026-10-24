# Pruebas reproducibles

El producto se instala por HACS; **Docker solo se utiliza para desarrollo y pruebas**.
Los datos sintéticos están en `tests/` y `tests_ha/`, fuera del componente distribuido.

## Última comprobación del desarrollo

El 24 de octubre de 2026, la revisión de desarrollo `0.2.0.dev1` pasó **76 pruebas**
en el laboratorio aislado con HA 2026.10.2 y Python 3.14.2: 59 del motor y 17 del
adaptador HA. También se ejecutaron Ruff (formato y análisis), mypy sobre el dominio
y sus pruebas, y `git diff --check`. Los trabajos de GitHub Actions proporcionan la
evidencia por commit de las siguientes revisiones; esta nota no garantiza commits
posteriores ni compatibilidad con otras versiones de HA.

## Motor

Con Python 3.14.2 o posterior:

```shell
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy
pytest tests
```

## Home Assistant real

```shell
python -m pip install pytest-homeassistant-custom-component==0.13.373
python -m pytest -c tests_ha/pytest.ini tests_ha -q
```

El paquete fija HA 2026.10.2 y sus fixtures. Instálalo en un entorno separado del de
herramientas del motor porque utiliza una versión propia de pytest.

Alternativamente construye `Dockerfile.test` y monta este repositorio de solo lectura
en `/workspace`. Las pruebas no necesitan puertos, red, credenciales, volúmenes de
datos de usuario ni contenedores privilegiados.

La prueba en `docker-lab` se limita al proyecto `luz-en-cifras`, con 1 CPU y 1500 MiB
por ejecución. Conserva los registros en `results/`; no utiliza sudo ni modifica
servicios de otros proyectos. La imagen de pruebas se puede reutilizar.

## Qué se comprueba

- Precio fijo, tres periodos, cambios de precio, descuentos y fiscalidad.
- Dos horas repetidas de otoño y salto de primavera.
- Contadores, precios ausentes, correcciones, unidades y compensación limitada.
- Flujos nativos de configuración y opciones, eventos y persistencia real de HA.
- Migración del Store antiguo, cierre, exportación, comparación y revisión auditable.
- Consentimiento para repartir lecturas que cruzan fechas de factura y conservación
  de las mediciones originales; los descuentos de potencia no reducen el límite
  económico de la compensación de energía.
- Renombrado y reordenación de grupos sin reiniciar los consumos; cambiar la fuente
  de excedentes sí cambia la topología del seguimiento.
- Aviso Repairs cuando falta una regla fiscal y resolución mediante un perfil explícito.
- Detección W/kW/Wh/kWh, integración de potencia, grupos mixtos y casa/coche con
  precios distintos; caducidad, huecos, reinicios y estados restaurados.
- Ciclos mensuales/bimestrales, meses cortos, cambio de año y corte local de potencia.

Las pruebas de flujos se hacen a través de las APIs reales de Home Assistant. Eso
no equivale a una inspección visual de móvil/escritorio ni a contraste con una
factura real de cada comercializadora. Esas validaciones se documentan por separado
y no se dan por ejecutadas por pasar pytest.
