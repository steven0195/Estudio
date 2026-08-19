# Estudio — guía para el asistente

Este repositorio es una base de conocimiento personal de estudio. Contiene dos áreas:

- `Administracion de empresas/` — cursos formales de un programa académico, organizados por periodo.
- `Desarrollo/` — aprendizaje autodidacta por temas (sin periodo/curso formal).

## Estructura

```text
<Periodo> <Curso>/              # p. ej. "2026-1 T1 Gerencia del servicio"
  curso.md                      # ficha del curso: docente, fechas, temario, notas generales
  fuentes/                      # documentos generales del curso (carta descriptiva, instrucciones, etc.)
  Unidad N - <Tema>/
    apuntes/                    # síntesis propia del estudiante (apuntes o notas), en Markdown limpio
    fuentes/                    # material crudo: PDFs, PPTX, MP3, y su conversión a .md si existe
    actividades/                # enunciados y respuestas de talleres/evaluaciones entregados
```

`Desarrollo/<Tema>/` sigue el mismo patrón (`apuntes/`, `fuentes/`, `actividades/`) pero sin `curso.md` ni periodo, porque no es una materia formal.

`curso.md` es el punto de partida de cada curso: resumen, temario, notas generales. No hace falta una carpeta aparte para eso — se edita como cualquier `.md`, sección por sección (ver "Asistente de capturas" más abajo).

## Cómo interpretar cada tipo de archivo

Todo `.md` con contenido real lleva frontmatter YAML con un campo `tipo`:

- **`curso`** (en `curso.md`) — metadatos y vista general del curso completo: temario, notas, documentos generales. Es el punto de partida para orientarte antes de entrar al detalle de una unidad.
- **`apunte`** — apuntes o notas de síntesis propia del estudiante sobre un tema puntual. Es la fuente de verdad más confiable para explicar algo en detalle: prioriza esto sobre `fuente` al responder preguntas de repaso.
- **`fuente`** — material original (lecturas, diapositivas convertidas, transcripciones). Puede ser una conversión cruda de PDF/PPT sin mucha estructura; trátalo como referencia, no como resumen ya digerido. Si un `apunte` y una `fuente` se contradicen, dilo explícitamente en vez de mezclarlos.
- **`actividad`** — enunciado y/o respuesta de un taller, evaluación o tarea ya entregada. No la presentes como si fuera una respuesta nueva tuya a menos que el usuario pida explícitamente ayuda para refutarla o mejorarla. Si el usuario pide "ayúdame a repasar la Unidad X", usa esto para generar preguntas de práctica, no para regenerar la tarea. Excepción: si tiene `borrador_ia: true` en el frontmatter (generado por `solucionador_actividades.py`), es un borrador sin revisar, no una entrega real — puedes ayudar a mejorarlo o completarlo libremente.
- **`nota`** — cualquier `.md` creado fuera de `apuntes/`, `fuentes/` o `actividades/` (p. ej. directo en la raíz de una unidad). Trátalo como contenido informal sin clasificar.

Archivos vacíos con solo el frontmatter y una nota "Borrador vacío" son plantillas pendientes de llenar — no inventes contenido ahí salvo que el usuario pida explícitamente que redactes la síntesis.

## Comportamiento esperado

- Cuando el usuario pregunte por un tema, busca primero en `apuntes/` de la unidad correspondiente; usa `fuentes/` solo para profundizar o verificar algo que el apunte no cubre.
- Al ayudar a preparar un examen o quiz, apóyate en `actividades/` para saber qué ya se evaluó, pero no lo repitas literal.
- Si el usuario pide crear una nota nueva, sigue el formato de `1 Ecuaciones.md` (Ciencias Básicas, Unidad 1) como referencia de estilo: encabezados jerárquicos, tablas para comparar conceptos, ejemplos resueltos paso a paso, resumen al final.
- Los nombres de carpeta usan `Unidad N - Tema` (con espacio y guion, no guion bajo). Mantén esa convención si creas unidades nuevas.

## Asistente de capturas

`asistente_capturas/` captura pantallazos con un atajo de teclado y los
transcribe a Markdown con un modelo de visión local en LM Studio. Deja
navegar el repo carpeta por carpeta hasta **cualquier `.md` existente**
(incluido `curso.md`, que vive suelto en la raíz del curso, no dentro de una
carpeta `apuntes/fuentes/actividades`) o crear uno nuevo ahí mismo. Si el
archivo elegido ya tiene secciones (`##`, `###`, ...), pregunta en cuál
insertar la captura — para poder alimentar, por ejemplo, la sección
"Notas" de un `curso.md` sin tocar el resto de su estructura. Al final
pregunta cómo insertarla:

- **Nota completa** — imagen y texto transcrito, todo como **cita**
  (`>`): material auxiliar/de referencia (equivalente a `fuente`),
  claramente separado de los apuntes o la prosa propia del archivo.
- **Agregar al contenido** — solo la referencia ("Captura de
  pantalla" + imagen) va como cita; el texto transcrito se agrega
  como contenido normal del documento (útil cuando la transcripción
  ya es el apunte que querías, no solo una referencia).

Y opcionalmente un encabezado propio (Enter para no ponerle ninguno).
Se inicia con `start.bat` (raíz).

`asistente_capturas/transcriptor_documentos.py` hace lo mismo pero para
documentos completos: convierte `.txt`, `.pdf`, `.docx` y `.pptx` a
Markdown junto al original (`pandoc` para .docx/.pptx, PyMuPDF para .pdf).
El texto se extrae tal cual, sin que una IA lo reescriba — la fidelidad es
la prioridad, por eso es `fuente` y no un resumen ya digerido. Cada imagen
o diagrama que encuentra se describe con el modelo de visión de LM Studio
y esa descripción se inserta como cita junto a la imagen (igual formato que
las capturas de pantalla) — así un modelo que solo lee texto también
entiende qué muestran las ilustraciones. Uso: `python
asistente_capturas/transcriptor_documentos.py "<archivo o carpeta>"`.

`asistente_capturas/solucionador_actividades.py` genera un primer borrador
resuelto de una actividad (`actividades/*.doc(x)/.pdf/...`, la transcribe
sola si hace falta), **punto por punto**, usando como fuente PRINCIPAL los
`.md` de la carpeta `fuentes/` de esa misma unidad (recuperados por RAG —
`rag_fuentes.py` vectoriza `fuentes/` con el modelo de embeddings de LM
Studio y busca por similitud, en vez de mandar todo el contenido de golpe),
y el conocimiento general del modelo solo como respaldo para lo que no
esté cubierto ahí. Cada punto de la actividad se resuelve por separado
(con un resumen de los puntos anteriores para mantener coherencia), y al
final un paso de auditoría revisa el borrador completo con ojo crítico
(puntos faltantes, términos, inconsistencias, referencias) y agrega esa
revisión como sección aparte. No es interactivo ni rápido — aceptable
aquí, es para trabajos sin apuro, no para exámenes en vivo. El resultado
se guarda como `<actividad>-borrador-ia.md`, **nunca sobrescribe ni se
llama igual que el original**, y queda marcado con `borrador_ia: true` en
el frontmatter — trátalo como una ayuda para revisar y ajustar, no como
una entrega real. Uso: `python
asistente_capturas/solucionador_actividades.py "<archivo de actividad>"`.

Ver [asistente_capturas/LEEME_asistente_capturas.md](asistente_capturas/LEEME_asistente_capturas.md)
para instalación y uso de los tres programas.

## Pendientes conocidos

- `2026-1 T1 Gerencia del servicio/_sin_clasificar/` tiene material antiguo sin clasificar (carpetas "1" y "2" con una versión previa de un trabajo). Falta revisarlo y decidir si se archiva o se integra a una unidad.
- La mayoría de unidades tienen `apuntes/apuntes.md` vacío (borrador) porque el material original no incluía notas de síntesis propias — solo PDFs/PPTX crudos. Se irán completando conforme el usuario avance en cada curso.
- En `2026-1 T2 Liderazgo y negociación/Unidad 2/fuentes/`, `ASSESMENT.pdf` y `Assessment.pdf` son documentos distintos con nombres casi idénticos por un typo del material original (no son duplicados).
