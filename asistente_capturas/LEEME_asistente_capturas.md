# Asistente de capturas de estudio

Programa que corre en segundo plano: presionas un atajo de teclado, recortas
una región de la pantalla, un modelo de visión local en **LM Studio** la
transcribe a Markdown, y el programa te pregunta en la terminal dónde
guardarla dentro del repo.

## 1. Requisitos previos

1. [LM Studio](https://lmstudio.ai/) instalado, con:
   - Un modelo con soporte de imágenes descargado y cargado (p. ej. `google/gemma-4-e2b`, o cualquier modelo Qwen-VL/LLaVA que tengas).
   - El servidor local activo (pestaña "Developer" → "Start Server", por defecto en `http://localhost:1234`).
2. Python 3.10+ instalado.

## 2. Instalación

Desde la raíz del repo:

```bash
pip install -r asistente_capturas/requirements.txt
```

## 3. Configuración

Edita `asistente_capturas/capturas_config.json` si necesitas cambiar algo:

- `lmstudio_model`: el nombre exacto del modelo tal como aparece en LM Studio (pestaña "Developer" o `http://localhost:1234/v1/models`). Debe soportar imágenes.
- `lmstudio_base_url`: cambia el puerto si configuraste otro en LM Studio.
- `hotkey`: el atajo de teclado global, por defecto `ctrl+shift+p`.
- `prompt`: la instrucción que se le da al modelo para transcribir la imagen; puedes ajustarla si el resultado no te convence.

## 4. Uso

Doble clic en **`start.bat`** (en la raíz del repo), o desde la raíz:

```bash
python asistente_capturas/asistente_capturas.py
```

Deja esa ventana de terminal abierta (puedes minimizarla). Cuando quieras capturar algo:

1. Presiona el atajo (`Ctrl+Shift+P` por defecto).
2. La pantalla se oscurece: arrastra el mouse para seleccionar la región que quieres capturar. `Esc` cancela.
3. El programa envía la imagen a LM Studio y espera la transcripción (puede tardar unos segundos según el modelo).
4. En la terminal eliges dónde guardarla (todo por menú numerado, nunca escribes una ruta a mano; `b` retrocede un paso, `0` cancela):
   - Si ya guardaste una captura antes (en esta sesión o en una anterior), primero te pregunta si esta va **en el mismo archivo de la última vez** — si dices que sí, salta directo a elegir la sección de ese archivo, sin repetir la navegación. Si dices que no, sigue con el punto siguiente.
   - Navegas el repo como un explorador de carpetas: en cada carpeta ves tanto sus subcarpetas como sus archivos `.md` sueltos — por ejemplo, dentro de un curso puedes entrar a "Unidad 1" **o** elegir directamente `curso.md`. Sigue hasta donde quieras guardar: área → curso/tema → unidad → `apuntes/`, `fuentes/` o `actividades/` (o quédate en un nivel más alto si el archivo que buscas está ahí).
   - Elige un `.md` existente (te muestra su título y fecha de edición) o **"Crear un archivo nuevo aquí"** (te pide un título).
   - Si el archivo elegido ya tiene secciones (`##`, `###`...), te pregunta en cuál insertar la captura — o "al final del archivo". Así puedes alimentar, por ejemplo, la sección "Notas" de un `curso.md` sin tocar el resto de su estructura.
5. Guarda la imagen en `<carpeta-del-archivo>/src/captura-<fecha>.png` y el texto transcrito dentro del `.md` elegido, en la sección que hayas indicado. Recuerda ese archivo como "el de la última vez" para el punto 4 en la próxima captura (se guarda en `capturas_state.json`, junto al script).

La captura (imagen + transcripción) siempre se inserta como **cita** (`>`), nunca como encabezado ni como texto corrido — así queda claro que es material de referencia/auxiliar y no se confunde con tus apuntes o la prosa del archivo:

```markdown
> **Captura de pantalla** — 2026-08-07 14:12
>
> ![Captura](src/captura-20260807-141230.png)
>
> (texto transcrito por el modelo de visión, tal cual)
```

Si más adelante quieres incorporar algo de ahí a tu texto "de verdad", cópialo fuera de la cita.

Para salir, `Ctrl+C` en la terminal.

## Notas y límites conocidos

- La selección de región solo cubre el monitor principal si usas varios monitores.
- El atajo es global: si otra aplicación ya usa `Ctrl+Shift+P`, cámbialo en `capturas_config.json`.
- Si LM Studio no responde (servidor apagado, modelo sin visión), el programa igual guarda la imagen y crea/añade el bloque con un aviso para que completes la transcripción a mano.
- La calidad de la transcripción depende completamente del modelo que tengas cargado en LM Studio. En mis pruebas, LM Studio a veces contesta con el modelo que ya está cargado en memoria en vez del que se pide por nombre en `lmstudio_model` — si la transcripción sale pobre o genérica, entra a la pestaña "Developer" de LM Studio y confirma cuál modelo está realmente activo (debe soportar imágenes).
- Algunos modelos "razonadores" (formato harmony/gpt-oss) filtran su cadena de pensamiento antes de la respuesta final aunque se les pida no hacerlo; el script ya intenta limpiar eso, pero si ves texto raro tipo `<|channel|>` en el resultado, es una señal de que el modelo activo no es el más adecuado para esta tarea.
