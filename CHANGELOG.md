# Changelog — Módulo de Estadísticas

Qué cambió en cada versión. Lo lee el técnico desde el botón **Changelog** de la
tarjeta de esta app en MINIhub: `publicar_app.py` se lleva este archivo entero
dentro del manifiesto firmado, en cada publicación.

**Al publicar una versión nueva, agregale su sección acá arriba.** Escribí para el
que usa el programa, no para el que lo programó: qué cambia en la pantalla, qué
error deja de aparecer, qué hay que hacer distinto.

---

## Sin publicar

**Modo Usuario y Modo Avanzado, como en Leontis.** Si su empresa tiene activados
los **roles de acceso** en Leontis, el programa abre en Modo Usuario: se ven el
análisis de stock y las exportaciones de clientes y artículos. El botón
**🔒 Modo Avanzado** del encabezado pide la **contraseña de administrador de
Leontis** (la misma que usa Leontis) y habilita todos los informes y el Panel de
Control; el mismo botón vuelve al Modo Usuario. Si su empresa no usa roles, el
programa abre con todo habilitado, como siempre.

Además, en Modo Usuario los informes ocultos ya no salen en las exportaciones:
antes quedaban tildados y el Excel o el PDF los incluían igual.

**Las ventas ahora cierran con las de Leontis.** Hasta esta versión la app:

- **dejaba afuera toda la venta en comprobante X**, que en muchos comercios es
  la mayor parte de la facturación;
- **contaba los presupuestos como si fueran ventas**;
- no restaba las notas de crédito X.

Ahora facturas, notas de débito y comprobantes X suman; todas las notas de
crédito restan; presupuestos y anulados no cuentan. Los totales de todos los
informes van a cambiar, y es lo esperado: los de antes estaban mal.

**Medios de pago como en la Caja Diaria de Leontis.** Se usa el medio que se
eligió al facturar. Aparecen **Mercado Pago** y **Cuenta Corriente** como
líneas propias. Antes casi todo figuraba como "Efectivo", "Tarjeta" daba cero y
lo que decía "Otros" era en realidad la cuenta corriente. Si su Leontis no pide
el medio de pago al facturar, lo cobrado en el momento figura como Efectivo.

**"Últimos 30 días" son 30 días**, contando hoy. Antes traían uno de más: la
opción "Últimas 24 horas" mostraba ayer y hoy (ahora se llama **Hoy**) y el
sugerido de compra calculaba una venta diaria algo más alta que la real.

**Segmentación de clientes (RFM) confiable.** Dos clientes con las mismas
compras ahora reciben siempre el mismo puntaje (antes podía salir distinto por
el orden en que venían). Cada cliente cae en un solo segmento, así que el
gráfico suma exactamente la cantidad de clientes, y el Excel trae una columna
**Segmento** coloreada en lugar de ocho columnas Verdadero/Falso. Las notas de
crédito ya no cuentan como una compra más.

**El Excel sale con el formato correcto en cada columna.** El DNI ya no aparece
con signo `$`, las fechas no salen como moneda y los saldos llevan su formato.

**El Panel de Control abre más rápido.** Las cotizaciones del dólar y el IPC se
guardan por un día como estaba previsto; antes se volvían a pedir a internet en
cada arranque.

**"Todos (sin gráfico)" en Margen Bruto ya no intenta dibujar** un gráfico con
miles de barras.

## 0.1.2 — 2026-08-14

**El aviso de actualización ya no parpadea al abrir.** Al arrancar, la app chequea
si hay una versión nueva. Ese chequeo tarda menos de un segundo, pero el cartel
que lo anunciaba salía antes y alcanzaba a verse: un recuadro que aparecía y se
iba solo. Ahora solo aparece si de verdad hay algo que bajar, o si la consulta se
demora.


**La app se anota en `C:\MainSolution`.** Cada vez que abrís deja constancia de
dónde está instalada y en qué versión, para que MINIhub la actualice en su lugar
en vez de poner una segunda copia al lado. Eso antes se guardaba en una carpeta
oculta del perfil de Windows; ahora va a `C:\MainSolution\MINIhub\usuarios\<tu
usuario>`, junto con lo demás del hub y con un `LEEME.txt` que explica qué es cada
archivo. Lo que había en la ubicación vieja **se copia, no se mueve**.

Esa carpeta se crea cerrada a tu usuario: de ahí sale la ruta que MINIhub después
abre, así que si otro usuario de la misma PC pudiera escribirla, podría hacer que
el acceso directo abra un programa suyo.


Tu configuración y tus datos no se tocan: siguen donde estaban y las
actualizaciones nunca los pisan.
