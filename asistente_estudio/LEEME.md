# Asistente de estudio

Cuatro programas que comparten la misma configuración de LM Studio:

- **`capturas.py`** — captura pantallazos con un atajo de teclado.
- **`transcriptor_documentos.py`** — convierte documentos (.txt, .pdf, .docx, .pptx, .doc) enteros a Markdown.
- **`solucionador_actividades.py`** — genera un primer borrador resuelto de una actividad, punto por punto, usando `fuentes/` como material de referencia (RAG) y con una auditoría crítica final.
- **`nueva_unidad.py`** — crea el esqueleto de carpetas y archivos base de una unidad o tema nuevo, para no armarlo a mano cada vez.

(`nucleo.py` no se corre directo — funciones y configuración compartidas por
los cuatro programas. `rag_fuentes.py` tampoco — es la lógica de
vectorización/búsqueda que usa el solucionador de actividades, pensada para
reutilizarse en más herramientas más adelante.)

Todo esto también se puede usar desde **`start.bat`** (en la raíz del repo):
un menú que cubre los cuatro programas sin tener que escribir comandos.

## 1. Requisitos previos

1. [LM Studio](https://lmstudio.ai/) instalado, con:
   - Un modelo con soporte de imágenes descargado y cargado (p. ej. `google/gemma-4-e2b`, o cualquier modelo Qwen-VL/LLaVA que tengas) — lo usan las capturas y el transcriptor.
   - Un modelo de texto/razonamiento cargado para `solucionador_actividades.py` (por defecto `qwen/qwen3.5-9b` en la config; puede ser el mismo que el de visión si tu modelo lo soporta todo).
   - El servidor local activo (pestaña "Developer" → "Start Server", por defecto en `http://localhost:1234`).
2. Python 3.10+ instalado.
3. [Pandoc](https://pandoc.org/installing.html) instalado y en el PATH — lo necesitan `transcriptor_documentos.py` y `solucionador_actividades.py` (para transcribir la actividad si no es .md) para leer `.docx`/`.pptx`.

## 2. Instalación

Desde la raíz del repo (o la opción 5 de `start.bat`):

```bash
pip install -r asistente_estudio/requirements.txt
```

## 3. Configuración

Edita `asistente_estudio/config.json` si necesitas cambiar algo:

- `lmstudio_model`: el nombre exacto del modelo tal como aparece en LM Studio (pestaña "Developer" o `http://localhost:1234/v1/models`). Debe soportar imágenes. Lo usan las capturas y el transcriptor.
- `lmstudio_model_texto`: el modelo de texto que usa `solucionador_actividades.py` para redactar (no necesita soportar imágenes). Por defecto `qwen/qwen3.5-9b`.
- `lmstudio_model_embeddings`: el modelo de embeddings para el RAG del solucionador de actividades. Por defecto `text-embedding-nomic-embed-text-v1.5`.
- `lmstudio_base_url`: cambia el puerto si configuraste otro en LM Studio.
- `hotkey`: el atajo de teclado global, por defecto `ctrl+shift+p`.
- `prompt`: la instrucción que se le da al modelo para transcribir la imagen; puedes ajustarla si el resultado no te convence.
- `prompt_descripcion_imagen`: la instrucción para describir imágenes dentro de documentos (transcriptor).

## 4. Uso: capturas de pantalla (`capturas.py`)

Opción 1 de **`start.bat`** (en la raíz del repo), o desde la raíz:

```bash
python asistente_estudio/capturas.py
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
5. Guarda la imagen en `<carpeta-del-archivo>/src/captura-<fecha>.png` y el texto transcrito dentro del `.md` elegido, en la sección que hayas indicado. Recuerda ese archivo como "el de la última vez" para el punto 4 en la próxima captura (se guarda en `estado.json`, junto al script).

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

### Notas y límites (capturas de pantalla)

- La selección de región solo cubre el monitor principal si usas varios monitores.
- El atajo es global: si otra aplicación ya usa `Ctrl+Shift+P`, cámbialo en `config.json`.
- Si LM Studio no responde (servidor apagado, modelo sin visión), el programa igual guarda la imagen y crea/añade el bloque con un aviso para que completes la transcripción a mano.

## 5. Uso: transcriptor de documentos (`transcriptor_documentos.py`)

Convierte documentos completos a Markdown: el texto se extrae **tal cual**
(pandoc para .docx/.pptx, PyMuPDF para .pdf, copia directa para .txt — nada
de esto pasa por una IA, así que es fiel al original) y cada imagen o
diagrama que encuentra se la muestra al modelo de visión de LM Studio para
que la describa; esa descripción se inserta como cita justo junto a la
imagen, igual que las capturas de pantalla, para que tanto una persona como
un modelo que solo lea texto entiendan también qué muestran las
ilustraciones sin perder de vista que es una descripción generada, no el
texto original.

Opción 2 de `start.bat`, o desde la raíz:

```bash
python asistente_estudio/transcriptor_documentos.py "<archivo>"
python asistente_estudio/transcriptor_documentos.py "<carpeta>"           # convierte todo lo soportado ahí
python asistente_estudio/transcriptor_documentos.py "<carpeta>" --forzar  # re-convierte aunque ya exista el .md
```

Formatos soportados: `.txt`, `.pdf`, `.docx`, `.pptx`, `.doc`. Genera `<nombre>.md`
junto al original, con el mismo frontmatter (`tipo`, `curso`, `periodo`,
`unidad`, `tema`...) que usa el resto del repo — si lo corres dentro de una
carpeta `fuentes/`, el `.md` sale marcado como `tipo: fuente`. Las imágenes
extraídas van a `src/<nombre-del-documento>/` (cada documento en su propia
subcarpeta, para que dos documentos en la misma carpeta no se pisen las
imágenes entre sí).

### Notas y límites (transcriptor de documentos)

- Salta archivos que ya tienen un `.md` con el mismo nombre, para no
  pisar ediciones tuyas por accidente — usa `--forzar` si de verdad quieres
  re-convertir.
- Las imágenes en formatos que el modelo de visión no puede leer (p. ej.
  `.emf`/`.wmf`, típicos de gráficos vectoriales dibujados directo en
  PowerPoint/Word) se dejan sin describir, con un aviso en la terminal —
  revísalas a mano si son importantes.
- Si el mismo documento repite una imagen (p. ej. un fondo decorativo detrás
  de cada cuadro de texto de una diapositiva), solo se describe una vez y esa
  descripción se reutiliza — no se vuelve a llamar a LM Studio por cada
  repetición.
- La detección de encabezados en PDF es un heurístico por tamaño de letra
  (texto notablemente más grande → `##`, algo más grande o en negrita →
  `###`); en documentos con tipografía muy uniforme puede no marcar ningún
  encabezado, o marcar de más.
- El orden de texto e imágenes en cada página del PDF se aproxima por
  posición vertical — en diseños con columnas o cajas de texto superpuestas
  el orden de lectura puede no coincidir exactamente con el original.
- `.doc` (el formato binario antiguo de Word, previo a `.docx`) también se
  soporta, pero pandoc no lo lee directamente: si tienes Microsoft Word
  instalado (y `pip install pywin32`), el script lo abre por COM, lo guarda
  como `.docx` temporal, y sigue el mismo camino normal. Si no tienes Word,
  falla con un mensaje claro — ábrelo tú a mano y usa "Guardar como" → `.docx`.
- Aplican las mismas notas sobre la calidad/enrutamiento del modelo de LM
  Studio que las capturas de pantalla (ver abajo).

## 6. Uso: solucionador de actividades (`solucionador_actividades.py`)

Genera un primer borrador resuelto de una actividad, **punto por punto**,
priorizando el material de `fuentes/` de la misma unidad sobre el
conocimiento general del modelo, y termina con una **auditoría crítica**
del resultado completo. No es interactivo — se corre una vez y espera:

Opción 3 de `start.bat`, o desde la raíz:

```bash
python asistente_estudio/solucionador_actividades.py "<archivo de actividad>"
python asistente_estudio/solucionador_actividades.py "<archivo de actividad>" --fuentes "<otra carpeta>"
```

Flujo:

1. Si la actividad no es `.md` todavía (p. ej. `.doc`/`.docx`/`.pdf`), la transcribe primero (mismo camino que `transcriptor_documentos.py`).
2. **Vectoriza `fuentes/`** una sola vez (embeddings de LM Studio + similitud de coseno, ver `rag_fuentes.py`) — se cachea en `fuentes/.rag_cache.json`, así que las siguientes actividades de la misma unidad no vuelven a vectorizar.
3. **Divide la actividad en sus puntos individuales** (p. ej. "1. Definir el problema", "2. Diseñar el árbol de objetivos"...).
4. **Resuelve cada punto por separado**: para cada uno, busca solo los fragmentos de `fuentes/` más relevantes para ESE punto (no el documento completo) y lo redacta con atención completa — evitando tanto desbordar el contexto del modelo como que las respuestas queden a medias por competir entre sí en un solo prompt gigante. Cada punto recibe además un resumen de lo ya resuelto en los puntos anteriores, para mantener coherencia (mismo caso/empresa/datos en todo el documento).
5. **Audita el borrador completo** con un último paso crítico: busca puntos faltantes o a medias, errores de terminología, afirmaciones sin sustento, inconsistencias entre puntos, falta de referencias. Esa revisión se agrega como sección aparte al final del archivo, no mezclada con las respuestas.
6. Guarda el resultado como `<actividad>-borrador-ia.md` en la misma carpeta `actividades/` — nunca sobrescribe el original ni se llama igual, y queda marcado `borrador_ia: true` en el frontmatter.

### Notas y límites (solucionador de actividades)

- Usa `lmstudio_model_texto` para redactar y `lmstudio_model_embeddings` para el RAG (no el modelo de visión). Las llamadas de texto van por la **API nativa de LM Studio** (`/api/v1/chat`, no la compatible con OpenAI), que permite apagar el razonamiento por completo (`reasoning: "off"`) para tareas simples como dividir la actividad en puntos — sin esto, algunos modelos razonadores locales (probado con Qwen3) pueden quedarse dando vueltas "pensando" sin llegar nunca a una respuesta final limpia, incluso con `max_tokens` generosos.
- Resolver cada punto y auditar el borrador sí usan razonamiento (más lento, pero mejor calidad) — si tu modelo es muy verboso pensando, los `max_tokens` de esos pasos son altos a propósito (6.000–10.000); si aun así una respuesta sale cortada a mitad de frase, es la señal de subirlos todavía más en el código.
- La coherencia entre puntos depende de que el resumen de "lo ya resuelto" que se pasa a cada punto siguiente sea suficiente — en actividades con muchísimos puntos, ese contexto se acota (1.500 caracteres por punto anterior) para no volver a desbordar el contexto.
- El auditor no es infalible ni corrige nada automáticamente: solo señala qué mirar. Sigue siendo trabajo tuyo revisar el borrador, completar datos que falten (nombres del equipo, fechas) y ajustarlo antes de entregar.

## 7. Uso: nueva unidad (`nueva_unidad.py`)

Crea el esqueleto de una unidad de curso (o tema de `Desarrollo/`) nueva:
las carpetas `apuntes/`, `fuentes/`, `actividades/`, con un `apuntes.md` en
blanco ya con el frontmatter correcto — sin dependencias externas (no
necesita `pip install` ni LM Studio corriendo).

Opción 4 de `start.bat`, o desde la raíz:

```bash
python asistente_estudio/nueva_unidad.py "<ruta de la nueva unidad o tema>"
```

Ejemplos:

```bash
python asistente_estudio/nueva_unidad.py "Administracion de empresas/2026-1 T1 Gerencia del servicio/Unidad 3 - Herramientas para gerenciar el servicio"
python asistente_estudio/nueva_unidad.py "Desarrollo/Docker"
```

Si la ruta es una unidad nueva dentro de un curso: crea también `curso.md`
si el curso todavía no existe, o enlaza la unidad en la sección
"## Unidades" de un `curso.md` ya existente sin tocar el resto. Es seguro
volver a correrlo sobre algo que ya existe — no sobrescribe ni duplica.

## Notas generales de LM Studio

- La calidad de las descripciones depende completamente del modelo que
  tengas cargado en LM Studio. En mis pruebas, LM Studio a veces contesta
  con el modelo que ya está cargado en memoria en vez del que se pide por
  nombre en `lmstudio_model` — si el resultado sale pobre o genérico, entra
  a la pestaña "Developer" de LM Studio y confirma cuál modelo está
  realmente activo (debe soportar imágenes).
- Algunos modelos "razonadores" (formato harmony/gpt-oss) filtran su cadena
  de pensamiento antes de la respuesta final aunque se les pida no hacerlo;
  el script ya intenta limpiar eso, pero si ves texto raro tipo
  `<|channel|>` en el resultado, es una señal de que el modelo activo no es
  el más adecuado para esta tarea.
