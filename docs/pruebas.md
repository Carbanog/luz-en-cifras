# Pruebas reproducibles

El producto se instala por HACS; **Docker solo se utiliza para desarrollo y pruebas**.
Los datos sintéticos están en `tests/` y `tests_ha/`, fuera del componente distribuido.

## Última comprobación del desarrollo

El 24 de octubre de 2026, la revisión `0.2.1` pasó **104 pruebas
en cada versión de HA 2026.10.2 y 2026.10.3**, con Python 3.14.2: 72 del motor y 32
del adaptador HA. También se ejecutaron Ruff (formato y análisis), mypy sobre el dominio
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

Para HA 2026.10.3 utiliza `pytest-homeassistant-custom-component==0.13.374` en otro
entorno. La CI mantiene ambas combinaciones. En `Dockerfile.test` se selecciona con
`--build-arg HA_TEST_VERSION=0.13.374`; no se actualizan dependencias del HA del usuario.

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
- Renombrado y reordenación de grupos sin reiniciar consumos; sustitución y reselección
  de contadores, grupos añadidos/eliminados y cambios fijo/tres periodos/dinámico.
- Una factura conserva el consumo previo, cargos fijos sin duplicación, compensación
  histórica, cierre y recálculo después de cambiar sensores y reiniciar el colector.
- Un contador nuevo con estado antiguo espera un reporte real, incluso tras recargar;
  no suma consumo mientras está retirado. Un grupo pendiente queda desconocido.
- Un cambio de tarifa sin lectura en la frontera exige consentimiento para estimar;
  activarlo después conserva los precios históricos. Renombrar o editar cuotas diarias
  no exige repartir la energía por sí solo.
- Aviso Repairs cuando falta una regla fiscal y resolución mediante un perfil explícito.
- Detección W/kW/Wh/kWh, integración de potencia, grupos mixtos y casa/coche con
  precios distintos; caducidad, huecos, reinicios y estados restaurados.
- Ciclos mensuales/bimestrales, meses cortos, cambio de año y corte local de potencia.
- Un mes de reportes por minuto conserva energía con almacenamiento acotado; la
  potencia también respeta el tiempo real de la hora repetida de otoño.
- Recorrido guiado desde modalidad, campos según tarifa, mes solo en bimestrales,
  ayuda de unidad de potencia y edición que conserva consumos y opciones.
- Guardado correcto de números enteros devueltos por los selectores, migración de
  días antiguos con formato `1.0` y rechazo de días/meses fraccionarios sin truncarlos.

## HA completo: preparación de la aceptación

### Revisión de 0.2.0 instalada en el HA del usuario

Se confirmó HACS 2.0.5, Core 2026.10.3 y release descargada 0.2.0. El asistente abrió
modalidad antes de periodo, pidió mes solo al elegir bimestral y mostró la ayuda de
P1/P2. Tras autorización se crearon tres sensores Template **PRUEBA LEC … simulada**,
con potencias sintéticas que cambian cada minuto, y un contrato identificado como
simulado: dos filas a 0,20 €/kWh y coche a 0,10 €/kWh. Son fixtures de aceptación,
no mediciones reales ni valores del contrato del usuario.

La revisión encontró `Missing or overlapping prices in measured interval` tras el
arranque. Dos regresiones con el reloj avanzando reprodujeron el error tanto con
precio fijo como dinámico; las pruebas previas congelaban el reloj. La corrección
0.2.1 se verifica en el laboratorio y CI, sin instalarla ni reiniciar el HA del usuario.
La comprobación visual de los importes en esa instalación queda pendiente de que el
usuario actualice y reinicie.

También se observó el logo relativo roto en HACS y se cambió a URL absoluta. Los
selectores numéricos de HA muestran cero al abrir campos sin valor predeterminado:
la ausencia de un default en el schema no garantiza un campo visual vacío. Sus ayudas
indican copiar los valores de la factura; no debe darse por validado ese aspecto de UX.

### Laboratorio completo anterior

El 24 de octubre se arrancó también la imagen oficial completa de HA 2026.10.2,
fijada por digest, con usuario sin privilegios y datos sintéticos identificados.
`check_config` terminó correctamente y `/onboarding.html` respondió HTTP 200.
Configuración reproducible: [laboratorio](../lab/README.md).

**Acceso LAN verificado:** tras autorización explícita, el 24 de octubre se enlazó
el puerto exclusivamente a `192.168.1.118:18123`. El navegador abrió la interfaz real
y llegó a «Crear usuario». El enlace predeterminado del Compose sigue siendo local;
el acceso LAN se utilizó solo para esta comprobación. No se han cambiado SSH, firewall,
proxy ni router. El túnel SSH no está disponible y se cerró tras comprobarlo.

**Instancia retirada:** por petición del usuario, se eliminó el contenedor, su red
Compose y la imagen descargada para ese HA nuevo. Se verificó el cierre del puerto
18123 y se conservó la configuración en una carpeta privada recuperable del proyecto.
No se tocaron otros servicios ni el entorno de pruebas automatizadas.

**Pendiente:** la revisión visual continuará en el HA de pruebas que ya tiene el
usuario, tras instalar por HACS y acceder mediante su sesión. No se ha completado
visualmente el asistente de la integración ni revisado los dashboards. No se crearon
credenciales ni se desactivó la autenticación. La prueba de varios días sigue el
[plan de aceptación](validacion-en-ha.md).

El formulario anterior sí se inspeccionó en el HA del usuario con Core 2026.10.3:
se confirmó su exceso de campos iniciales, las ayudas insuficientes y los ceros
predeterminados. El usuario ha elegido actualizar y reiniciar personalmente. Por
ello, el nuevo recorrido aún requiere comprobación visual tras esa actualización;
los tests de flujo no se presentan como revisión visual del formulario nuevo.

Las pruebas de flujos se hacen a través de las APIs reales de Home Assistant. Eso
no equivale a una inspección visual de móvil/escritorio ni a contraste con una
factura real de cada comercializadora. Esas validaciones se documentan por separado
y no se dan por ejecutadas por pasar pytest.
