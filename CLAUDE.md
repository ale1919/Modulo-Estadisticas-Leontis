# CLAUDE.md — Módulo de Estadísticas

<!-- MINIHUB:INICIO -->
## ⚠️ Antes de tocar esta app: leé `ACTUALIZACIONES.md`

Esta app forma parte del sistema de actualización automática de **MINIhub**
(`../MINIhub/`, o donde esté relativo a acá: `PROYECTOS 8-10/MINIhub`).

**[`ACTUALIZACIONES.md`](ACTUALIZACIONES.md)** de esta carpeta explica qué hay que
hacer para sumarla al sistema, qué hay que resolver **en esta app en particular**
antes de empezar, y en qué orden trabajar (auditoría → commit checkpoint →
integración → compilar y publicar → commit final). Leelo completo antes de empezar.

Puntos que importan aunque vengas a hacer otra cosa:

- Si en esta carpeta existen `Recursos/Modulos/nucleo.py`, `ftp_config.py` o
  `ui_updater.py`, **son copias y no se editan acá**. Se editan en
  `MINIhub/RECURSOS/MODULOS/` y se reparten con `python sincronizar_nucleo.py
  --app ModuloEstadisticasLeontis --aplicar`.
- El `.exe` de esta app tiene que llamarse `ModuloEstadisticasLeontis.exe` y el build tiene que ser
  **onedir**, nunca onefile.
- `Recursos/Config` es la carpeta que el updater no toca nunca. Todo lo que sea de cada
  instalación va ahí; nada que tenga que actualizarse puede estar ahí.
- Publicar se hace desde MINIhub (`python publicar_app.py --app ModuloEstadisticasLeontis`), no desde
  este repo.

Contexto completo del sistema: `MINIhub/CLAUDE.md`. El razonamiento detrás de cada
decisión: `UTILIDADES/AGENDA RUST/ACTUALIZACIONES.md`.
<!-- MINIHUB:FIN -->

## Qué es

Estadísticas de Leontis para el usuario final, con gráficos y exportación a PDF.

- **Entrada:** `main.py`
- **Interfaz:** PySide6
- **Repo:** https://github.com/ale1919/Modulo-Estadisticas-Leontis

## Cómo correr

```bash
python main.py
```

## Estado

Funcional. Usa matplotlib para los gráficos y exporta a PDF.

**Build:** **No tiene `.spec` ni `.bat`.** Hay que crear la configuración de build desde cero.

> Este CLAUDE.md es el mínimo para no trabajar a ciegas: lo generó
> `MINIhub/generar_guias.py` y no describe la arquitectura interna de la app.
> Cuando hagas la auditoría completa, ampliá esta sección con los módulos, el flujo
> y lo que haya que saber para no romper nada. Lo de arriba, entre los marcadores
> `MINIHUB:`, lo pisa el generador: escribí abajo.
