# Home Assistant completo de laboratorio

Solo para desarrollo y validación. **El producto se instala con HACS**, no con este
contenedor. Los sensores `LAB` son fixtures sintéticos, ajustables manualmente, y
no representan consumos reales ni forman parte del componente distribuido.

Si ya dispones de un HA de pruebas, úsalo instalando la integración por HACS:
**no es necesario crear otro HA**. Esta configuración es opcional para desarrolladores
que necesiten un entorno aislado.

La imagen oficial de HA 2026.10.2 está fijada por digest. El servicio no usa modo
privilegiado ni red del host. El puerto se liga únicamente a `127.0.0.1:18123`.
Cambiarlo para permitir acceso LAN requiere autorización explícita.

## Directorios en la VM

```text
/srv/docker-lab/projects/luz-en-cifras/
├── source/custom_components/   # Código probado, montaje de solo lectura
└── full-ha/
    ├── compose.yaml
    └── config/
        └── configuration.yaml
```

Se copia `configuration.yaml` a la carpeta nueva de configuración, sin sustituir
la de un HA existente. Se usa el UID/GID 1000 del propietario del laboratorio;
comprueba `id -u` e `id -g` en otros equipos y adapta el usuario antes de arrancar.
El proceso Python se ejecuta sin root y sin capacidades Linux adicionales.

```shell
docker compose -p luz-en-cifras-ui -f full-ha/compose.yaml up -d
docker logs --tail 50 luz-en-cifras-ha-lab
```

Config contiene los datos persistentes, usuarios, credenciales y Recorder del HA de
pruebas: no lo subas al repositorio ni compartas sus archivos `.storage`. No hay
variables secretas en el Compose ni en los fixtures. No se necesita sudo.

## Parar y recuperar

```shell
docker compose -p luz-en-cifras-ui -f full-ha/compose.yaml stop
```

Parar no borra datos. Para una copia consistente, detén primero este servicio y
copia únicamente `full-ha/config` a una ubicación privada. Una recuperación usa la
misma imagen/digest y la copia de config junto al código de la integración del
commit correspondiente. No uses `down -v` ni `prune`; no alteres otros proyectos.

El arranque correcto no acredita que el asistente o el dashboard se hayan revisado.
Consulta el estado real de las comprobaciones en `docs/pruebas.md`.
