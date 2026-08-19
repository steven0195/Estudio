"""
Solucionador de actividades.

Genera un primer borrador resuelto de una actividad, punto por punto, usando
como fuente PRINCIPAL los documentos ya transcritos en `fuentes/` de la
misma unidad (recuperados por RAG — embeddings + similitud de coseno, no
mandando todo el contenido de golpe), y el conocimiento general del modelo
solo como respaldo para lo que no esté cubierto ahí.

El flujo:
  1. Vectoriza fuentes/ una vez (se cachea; ver rag_fuentes.py).
  2. Divide el enunciado de la actividad en sus puntos/preguntas individuales.
  3. Para cada punto, busca solo los fragmentos de fuentes/ más relevantes
     para ESE punto (no el documento completo) y lo resuelve por separado —
     así cada respuesta recibe atención completa en vez de quedar a medias
     por competir con el resto de la actividad en un solo prompt gigante.
  4. Un último paso de auditoría revisa el borrador completo con ojo crítico
     (puntos faltantes, términos incorrectos, falta de sustento...) y esa
     revisión se agrega al final del archivo, aparte de las respuestas.

No es interactivo y no tiene que ser rápido — para exámenes en vivo se
necesita otra herramienta más rápida, esta es para trabajos sin apuro.

El archivo generado queda marcado con `borrador_ia: true` en el frontmatter
y nunca se llama igual que la actividad original — es un borrador para
revisar, no una entrega.

Requisitos: los mismos que transcriptor_documentos.py (para poder
transcribir la actividad si todavía no es .md) + LM Studio con un modelo de
texto y uno de embeddings cargados.

Uso:
  python solucionador_actividades.py "<archivo de actividad>"
  python solucionador_actividades.py "<archivo de actividad>" --fuentes "<carpeta>"
"""

import re
import sys
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from asistente_capturas import (  # noqa: E402
    REPO_ROOT,
    cargar_config,
    construir_frontmatter,
    quitar_frontmatter,
    slugify,
)
from transcriptor_documentos import CONVERSORES, insertar_descripciones  # noqa: E402
from rag_fuentes import indexar_fuentes, buscar_relevantes  # noqa: E402

TOP_K_FRAGMENTOS = 6
TOPE_RESUELTO_PREVIO = 1500  # caracteres máx. de cada punto anterior que se lleva de contexto a los siguientes

PROMPT_SEGMENTAR = """Aquí está el enunciado completo de una actividad académica. Divídelo en los puntos o preguntas de CONTENIDO que se deben resolver (ignora reglas administrativas como formato de entrega, fechas, tamaño del grupo o advertencias de plagio — esos no son puntos a resolver).

Responde ÚNICAMENTE con la lista de puntos, uno por línea, en este formato exacto (sin texto antes ni después de la lista):
1. <descripción clara y con suficiente detalle de qué pide ese punto, para poder resolverlo sin volver a leer el enunciado completo>
2. <...>

--- ENUNCIADO ---
{actividad}
--- FIN ENUNCIADO ---"""

PROMPT_PUNTO = """Eres un asistente académico ayudando a preparar, punto por punto, un primer borrador resuelto de una actividad.

Esta actividad tiene varios puntos; aquí está la lista completa para que tengas el contexto general (pero SOLO debes resolver el punto indicado más abajo, no los demás):
{contexto_general}

Puntos anteriores ya resueltos (mantén COHERENCIA con esto: mismo caso/empresa/ejemplo, mismos nombres, mismos datos y términos ya usados — no inventes un caso nuevo ni cambies nombres):
--- YA RESUELTO ---
{resueltos_previos}
--- FIN YA RESUELTO ---

Punto a resolver ahora (punto {numero}):
--- PUNTO ---
{punto}
--- FIN PUNTO ---

Material de referencia del curso más relevante para este punto específico (fuente PRINCIPAL — apóyate en él primero):
--- MATERIAL ---
{material}
--- FIN MATERIAL ---

Instrucciones:
- Resuelve ÚNICAMENTE este punto, de forma completa y bien desarrollada — no un resumen superficial, este es un primer borrador para que el estudiante lo revise y ajuste.
- Usa el material de referencia como fuente principal. Solo si algo no está cubierto ahí, complementa con tu conocimiento general, indicándolo brevemente (p. ej. "(no cubierto en el material del curso)").
- Responde en español. No repitas el enunciado del punto ni comentes el proceso (nada de "aquí está tu respuesta"): ve directo al contenido."""

PROMPT_AUDITOR = """Eres un auditor académico MUY crítico revisando un borrador de actividad ya resuelta, antes de que el estudiante la entregue. Tu trabajo es encontrar problemas — no elogiar ni suavizar.

Actividad original:
--- ACTIVIDAD ---
{actividad}
--- FIN ACTIVIDAD ---

Borrador de solución a revisar (resuelto punto por punto):
--- BORRADOR ---
{borrador}
--- FIN BORRADOR ---

Revisa con ojo crítico y en detalle:
- ¿Se respondieron TODOS los puntos del enunciado? Señala cualquier punto faltante, resuelto a medias, o que se desvía de lo pedido.
- ¿Los términos y conceptos usados son correctos según el estándar del curso, o hay errores conceptuales?
- ¿Hay afirmaciones sin sustento, contradicciones entre puntos, o partes que suenan inventadas o genéricas?
- ¿Falta profundidad, ejemplos o justificación en algún punto comparado con lo que pide el enunciado?
- ¿Hay algo que debería tener una referencia o cita al material del curso y no la tiene?

Responde en español, en una lista concreta de observaciones — una por línea, cada una empezando con el punto o sección a la que aplica (p. ej. "Punto 2: ..."). Si en verdad no encuentras ningún problema en algún punto, dilo explícitamente ("Punto 3: sin observaciones") en vez de omitirlo. Sé específico: no digas "podría mejorar", di QUÉ falta o qué está mal exactamente."""


def chat_texto(mensaje, cfg, max_tokens=8000, avisar=print, razonar=True):
    """Usa la API nativa de LM Studio (`/api/v1/chat`, no la compatible con
    OpenAI): separa de verdad el razonamiento del mensaje final en la
    respuesta (`output: [{type: "reasoning"}, {type: "message"}]`), así que no
    hay que adivinar ni limpiar con regex — y permite apagar el razonamiento
    por completo con `reasoning: "off"` cuando la tarea no lo necesita. Sin
    esto, modelos razonadores locales (Qwen3...) pueden quedarse "pensando" en
    tareas simples de forma poco fiable, sin llegar nunca a una respuesta final
    limpia dentro de cualquier límite razonable de tokens — nos pasó de verdad
    armando este script: ver notas en segmentar_puntos()."""
    modelo = cfg.get("lmstudio_model_texto") or cfg["lmstudio_model"]
    url_base = cfg["lmstudio_base_url"].rsplit("/v1", 1)[0]
    payload = {
        "model": modelo,
        "input": mensaje,
        "temperature": 0.3,
        "max_output_tokens": max_tokens,
        "reasoning": "on" if razonar else "off",
    }
    try:
        resp = requests.post(f"{url_base}/api/v1/chat", json=payload, timeout=1200)
        resp.raise_for_status()
    except Exception as e:
        avisar(f"  ERROR llamando a LM Studio ({modelo}): {e}")
        raise
    data = resp.json()
    return "\n".join(
        item["content"] for item in data.get("output", []) if item.get("type") == "message"
    ).strip()


def obtener_texto_actividad(ruta_actividad, cfg, avisar=print):
    """Si la actividad no es .md todavía, la transcribe primero (reutilizando
    transcriptor_documentos.py) y deja ese .md guardado junto al original,
    igual que si se hubiera corrido el transcriptor a mano."""
    if ruta_actividad.suffix.lower() == ".md":
        return ruta_actividad.read_text(encoding="utf-8")

    ruta_md = ruta_actividad.parent / f"{ruta_actividad.stem}.md"
    if not ruta_md.exists():
        conversor = CONVERSORES.get(ruta_actividad.suffix.lower())
        if conversor is None:
            raise RuntimeError(f"Formato de actividad no soportado: {ruta_actividad.suffix}")
        avisar(f"Transcribiendo el enunciado de la actividad ({ruta_actividad.name})...")
        cuerpo = conversor(ruta_actividad, ruta_actividad.parent)
        cuerpo = insertar_descripciones(cuerpo, ruta_actividad.parent, cfg, avisar=avisar)
        frontmatter = construir_frontmatter(
            ruta_actividad.parent,
            ruta_actividad.stem,
            origen=f"transcripción automática de {ruta_actividad.name}",
        )
        ruta_md.write_text(f"{frontmatter}\n# {ruta_actividad.stem}\n\n{cuerpo}\n", encoding="utf-8")
    return ruta_md.read_text(encoding="utf-8")


def segmentar_puntos(actividad_texto, cfg, avisar=print):
    # razonar=False: es una tarea de estructura simple, y dejar que un modelo
    # razonador "piense" aquí solo agrega minutos de espera sin mejorar el
    # resultado (lo probamos: con razonamiento encendido llegó a redactar y
    # descartar la lista más de 40 veces sin terminar de decidirse).
    mensaje = PROMPT_SEGMENTAR.format(actividad=actividad_texto)
    respuesta = chat_texto(mensaje, cfg, max_tokens=2000, avisar=avisar, razonar=False)
    puntos = [p.strip() for p in re.findall(r"^\s*\d+[a-z]?\.\s+(.+)$", respuesta, re.MULTILINE) if p.strip()]
    if not puntos:
        avisar("  No se pudo dividir en puntos individuales — se resuelve como un solo bloque.")
        return [actividad_texto]
    avisar(f"Actividad dividida en {len(puntos)} punto(s):")
    for i, p in enumerate(puntos, 1):
        avisar(f"  {i}. {p[:100]}{'...' if len(p) > 100 else ''}")
    return puntos


def formatear_material(resultados):
    if not resultados:
        return "(sin material de referencia disponible para este punto)"
    return "\n\n".join(
        f"### Fragmento de {frag['archivo']} (similitud {sim:.2f})\n\n{frag['texto']}"
        for frag, sim in resultados
    )


def resolver_punto(numero, punto, lista_puntos, fragmentos, resueltos_previos, cfg, avisar=print):
    avisar(f"Resolviendo punto {numero}/{len(lista_puntos)}...")
    resultados = buscar_relevantes(punto, fragmentos, cfg, top_k=TOP_K_FRAGMENTOS)
    contexto_general = "\n".join(f"{i}. {p}" for i, p in enumerate(lista_puntos, 1))
    if resueltos_previos:
        texto_previos = "\n\n".join(f"### Punto {i}\n{texto}" for i, texto in resueltos_previos)
    else:
        texto_previos = "(este es el primer punto, todavía no hay nada resuelto)"
    mensaje = PROMPT_PUNTO.format(
        contexto_general=contexto_general,
        resueltos_previos=texto_previos,
        numero=numero,
        punto=punto,
        material=formatear_material(resultados),
    )
    return chat_texto(mensaje, cfg, max_tokens=6000, avisar=avisar)


def auditar_borrador(actividad_texto, borrador, cfg, avisar=print):
    # max_tokens generoso: el borrador completo (todos los puntos ya resueltos)
    # entra en el prompt, y una auditoría de verdad crítica sobre un borrador
    # largo necesita espacio de sobra para no cortarse a mitad de camino.
    avisar("Auditando el borrador completo (revisión crítica)...")
    mensaje = PROMPT_AUDITOR.format(actividad=actividad_texto, borrador=borrador)
    return chat_texto(mensaje, cfg, max_tokens=10000, avisar=avisar)


def resolver_actividad(ruta_actividad, carpeta_fuentes=None, avisar=print):
    cfg = cargar_config()
    actividad_texto = quitar_frontmatter(obtener_texto_actividad(ruta_actividad, cfg, avisar=avisar))

    if carpeta_fuentes is None:
        carpeta_fuentes = ruta_actividad.parent.parent / "fuentes"

    fragmentos = indexar_fuentes(carpeta_fuentes, cfg, avisar=avisar)
    if fragmentos:
        try:
            ubicacion = carpeta_fuentes.relative_to(REPO_ROOT)
        except ValueError:
            ubicacion = carpeta_fuentes
        avisar(f"Material de referencia: {ubicacion}")
    else:
        avisar(f"No se encontró material en '{carpeta_fuentes}' — se responde solo con el conocimiento general del modelo.")

    puntos = segmentar_puntos(actividad_texto, cfg, avisar=avisar)

    secciones = []
    resueltos_previos = []
    for i, punto in enumerate(puntos, 1):
        respuesta = resolver_punto(i, punto, puntos, fragmentos, resueltos_previos, cfg, avisar=avisar)
        titulo_punto = punto if len(punto) <= 90 else punto[:87] + "..."
        secciones.append(f"## Punto {i}: {titulo_punto}\n\n{respuesta}")
        # se acota el tamaño para que el contexto de "coherencia" no crezca sin
        # límite con actividades de muchos puntos o respuestas muy largas
        resumen_previo = respuesta if len(respuesta) <= TOPE_RESUELTO_PREVIO else respuesta[:TOPE_RESUELTO_PREVIO] + "\n[...]"
        resueltos_previos.append((i, resumen_previo))
    borrador = "\n\n".join(secciones)

    critica = auditar_borrador(actividad_texto, borrador, cfg, avisar=avisar)

    carpeta_actividades = ruta_actividad.parent
    slug = slugify(ruta_actividad.stem)
    ruta_salida = carpeta_actividades / f"{slug}-borrador-ia.md"

    frontmatter = construir_frontmatter(
        carpeta_actividades,
        f"{ruta_actividad.stem} (borrador IA)",
        origen="borrador generado por IA a partir de fuentes/ (RAG, punto por punto) — revisar y ajustar antes de entregar",
        campos_extra={"borrador_ia": True},
    )
    contenido = (
        f"{frontmatter}\n# {ruta_actividad.stem} — borrador IA\n\n{borrador}\n\n"
        "---\n\n## Revisión crítica (auditor IA)\n\n"
        "> Generada automáticamente por un segundo paso de revisión — no es infalible, "
        "pero señala puntos concretos a mirar antes de entregar.\n\n"
        f"{critica}\n"
    )
    ruta_salida.write_text(contenido, encoding="utf-8")
    avisar(f"\nCreado: {ruta_salida.relative_to(REPO_ROOT)}")
    return ruta_salida


def main():
    if len(sys.argv) < 2:
        print('Uso: python solucionador_actividades.py "<archivo de actividad>" [--fuentes "<carpeta>"]')
        sys.exit(1)

    ruta_actividad = Path(sys.argv[1]).resolve()
    carpeta_fuentes = None
    if "--fuentes" in sys.argv:
        idx = sys.argv.index("--fuentes")
        carpeta_fuentes = Path(sys.argv[idx + 1]).resolve()

    if not ruta_actividad.exists():
        print(f"No existe: {ruta_actividad}")
        sys.exit(1)

    resolver_actividad(ruta_actividad, carpeta_fuentes)


if __name__ == "__main__":
    main()
