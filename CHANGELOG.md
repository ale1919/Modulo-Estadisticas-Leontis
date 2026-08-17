# Changelog — Módulo de Estadísticas

Qué cambió en cada versión. Lo lee el técnico desde el botón **Changelog** de la
tarjeta de esta app en MINIhub: `publicar_app.py` se lleva este archivo entero
dentro del manifiesto firmado, en cada publicación.

**Al publicar una versión nueva, agregale su sección acá arriba.** Escribí para el
que usa el programa, no para el que lo programó: qué cambia en la pantalla, qué
error deja de aparecer, qué hay que hacer distinto.

---

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
