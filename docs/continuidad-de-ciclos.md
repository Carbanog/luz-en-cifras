# Continuidad del consumo entre ciclos

## Cambiar el calendario contractual

Editar el día, duración o mes de referencia no cierra anticipadamente una factura.
El periodo abierto conserva sus fechas hasta su fin. Entonces se aplica el nuevo
calendario, usando un periodo de transición si hace falta, sin cobrar dos veces
los días anteriores. Los cambios de precio y fuente mantienen sus revisiones
efectivas desde el guardado, independientemente del calendario.

## Lecturas que atraviesan la frontera

Los contadores Wh/kWh mantienen su referencia al cambiar de ciclo. Si reportan a
las 23:59 y las 00:01, el incremento completo se conserva con ambas fechas:
no se vuelve a tomar la segunda lectura como una referencia que descarte energía.

Sin permiso de estimación, ese incremento queda **pendiente de reparto**, con un
aviso y su cantidad en kWh. La parte con cobertura conocida sigue calculándose;
si todavía no existe ninguna medición asignable, el importe permanece desconocido.
No se presupone consumo cero. El intervalo está guardado en el ledger y se conserva
en una revisión del cierre anterior, para poder revisarlo o exportarlo.

Si activaste **Permitir reparto temporal estimado**, el incremento se reparte
por duración real a ambos lados de la frontera. Se marca parcial. También se
respeta el cambio de hora: no se supone que todos los días tienen 24 horas.

Cuando una lectura tardía aporta información a una factura cerrada automáticamente,
se añade una revisión con `reason: late_meter_reading` y `supersedes` apuntando al
registro anterior. El original sigue intacto. Al exportar, usa la revisión más
reciente de esa cadena; no sumes el original y sus revisiones como facturas distintas.
Autorizar estimación más tarde no reescribe cierres antiguos: usa la acción de
revisión o el cierre por fechas con su consentimiento explícito, según corresponda.

Las lecturas ya omitidas por versiones anteriores no se reconstruyen automáticamente:
la corrección conserva los incrementos recogidos desde su instalación.

## Casa menos Coche con frecuencias distintas

El residual usa únicamente cobertura común de sus contadores. El consumo posterior
al horizonte común queda pendiente; no se compara el cargador más reciente con
un contador general atrasado para declarar una instalación físicamente imposible.
Los grupos independientes pueden seguir mostrando sus propias mediciones.

Sin autorización para estimar, un intervalo acumulativo que atraviesa ese horizonte
tampoco se divide artificialmente. Puede ser necesario esperar nuevos reportes
compatibles. Si no hay ningún tramo común medido, el residual queda desconocido.
Una diferencia negativa con cobertura comparable sigue siendo un error y debe
revisarse: la protección contra doble conteo y topologías incorrectas se mantiene.

## Calidad y datos conservados

El aviso inicial de falta de histórico pertenece al primer ciclo medido. Mantener
la referencia en los ciclos posteriores evita volver a crear ese aviso cada mes.
Los huecos reales, la energía estimada desde W/kW y los incrementos pendientes
siguen marcando el resultado como parcial. Un cierre automático conserva su aviso
de devengo provisional hasta revisarlo con la fecha real.

Se mantiene el formato de configuración y almacenamiento existente. No elimines
contratos para aplicar la corrección. Conserva un respaldo antes de actualizar y
consulta [migración y recuperación](migracion.md).

## Calendario 2027

Se han verificado las fechas fijas nacionales y el 6 de enero conforme al
[artículo 7 de la Circular 3/2020](https://www.boe.es/buscar/act.php?id=BOE-A-2020-1066#a7)
y al [calendario oficial de 2027](https://www.boe.es/eli/es/res/2026/10/08/(1)).
No se convierten en valle los festivos móviles, autonómicos o trasladados.
Los años sin calendario verificado se rechazan explícitamente.
