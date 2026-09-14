"""
Solucionador de actividades.

Genera un primer borrador resuelto de una actividad, punto por punto, usando
como fuente PRINCIPAL el material YA transcrito del curso completo —
`curso.md` más `fuentes/` y `apuntes/` de TODAS las unidades del curso, no
solo la unidad donde vive la actividad (recuperados por RAG — embeddings +
similitud de coseno, no mandando todo el contenido de golpe) — y el
conocimiento general del modelo solo como respaldo para lo que no esté
cubierto ahí. Si la actividad no vive dentro de un curso con `curso.md`
(p. ej. un tema plano de `Desarrollo/`), se usa solo la `fuentes/` de esa
carpeta, igual que antes.

El flujo (dos pasadas completas, no solo una crítica al final — el objetivo
es entregar algo cercano a una versión final, no un primer intento crudo):
  1. Detecta si la actividad pertenece a un curso completo (busca `curso.md`
     hacia arriba) y vectoriza TODO su material de referencia una vez (se
     cachea por carpeta; ver rag_fuentes.py) — puede tardar la primera vez,
     pero no hay apuro: es mejor una vectorización completa y lenta que una
     búsqueda rápida sobre material incompleto.
  2. Divide el enunciado de la actividad en sus puntos/preguntas individuales.
  3. **Primera pasada — borrador:** para cada punto, busca los fragmentos más
     relevantes para ESE punto (combinando una búsqueda estrecha por el punto
     y otra amplia por la actividad completa, para no perder de vista
     argumentos repartidos en material que la consulta puntual no habría
     encontrado — p. ej. comparar varias alternativas antes de elegir una) y
     lo resuelve por separado, con atención completa en vez de competir con
     el resto de la actividad en un solo prompt gigante. La búsqueda prioriza
     el material de la MISMA unidad de la actividad (ahí suele vivir el caso
     o fuente específico que hay que usar) y solo complementa, en menor
     proporción y claramente etiquetado, con material de otras unidades del
     curso — para no dejar que un ejercicio distinto con su propio nombre de
     empresa y cifras (de otra unidad) termine reemplazando por completo el
     caso real de la actividad.
  4. **Auditoría crítica** del borrador completo: puntos faltantes, cifras
     inventadas o inconsistentes entre puntos, fórmulas del material que se
     describieron en vez de aplicarse con números, decisiones tomadas sin
     comparar las alternativas disponibles.
  5. **Segunda pasada — corrección:** cada punto se reescribe a partir de las
     observaciones que el auditor hizo específicamente sobre ÉL (más las
     observaciones generales de todo el documento), con el mismo material de
     referencia a la mano — no es un resumen de cambios, es el reemplazo
     final de ese punto.
  6. **Verificación final:** se audita de nuevo el borrador YA CORREGIDO — lo
     que señale aquí suele ser lo que de verdad requiere al estudiante (datos
     reales que ni el material ni la IA pueden inventar: nombres del equipo,
     fechas exactas, cifras negociadas), no errores de fondo.

No es interactivo y no tiene que ser rápido — dos pasadas completas con
razonamiento activado tardan bastante más que una sola, y es una decisión
deliberada: para exámenes en vivo se necesita otra herramienta más rápida,
esta es para trabajos sin apuro donde importa más la calidad del resultado.

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
from nucleo import (  # noqa: E402
    REPO_ROOT,
    cargar_config,
    construir_frontmatter,
    quitar_frontmatter,
    slugify,
)
from transcriptor_documentos import CONVERSORES, insertar_descripciones  # noqa: E402
from rag_fuentes import indexar_fuentes, indexar_curso, buscar_relevantes  # noqa: E402

TOP_K_FRAGMENTOS = 6
# Con el curso completo indexado (varias unidades) hay más material entre el
# que elegir para cada punto; se pide más contexto que con la fuentes/ de una
# sola unidad para no perder cobertura por quedarnos cortos en top_k.
TOP_K_FRAGMENTOS_CURSO = 12
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

{decision_base}

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
- Si el material trae una fórmula, un procedimiento de cálculo o un ejemplo numérico resuelto que aplica a este punto, APLÍCALO con números concretos y muestra el cálculo paso a paso — no te limites a describirlo en abstracto. Una fórmula sin números no es una respuesta completa cuando el curso enseña cómo calcularla.
- Si este punto implica elegir entre varias opciones o alternativas mencionadas en el material o en la actividad (p. ej. elegir una estrategia, una fuente de financiación, un escenario entre varios), compara explícitamente los pros y contras de CADA opción disponible en el material antes de justificar cuál eliges — no elijas una sin haber sopesado las demás con sus propios argumentos en contra.
- No inventes datos específicos (nombres propios, cifras, fechas, ciudades) que no estén en el material o en el enunciado de la actividad. Si necesitas un dato concreto para completar el punto y no está disponible, usa un supuesto razonable pero MÁRCALO explícitamente como tal (p. ej. "(supuesto: ...)"), para que quede claro qué es del material y qué no.
- El caso, empresa o escenario concreto de ESTA actividad es el que describe el enunciado (y, si no da un nombre, el material de fuentes/apuntes de su misma unidad) — no adoptes el nombre de empresa, las cifras o los datos de un ejemplo o ejercicio DISTINTO que aparezca en el material (de otra unidad, u otro ejercicio de la misma unidad) como si fuera el caso real de esta actividad, aunque tenga una estructura parecida (p. ej. otro ejercicio de fijación de precios o de evaluación financiera con su propia empresa ficticia). Si un fragmento de material está marcado como "[material general de otra unidad]", úsalo solo para tomar prestada una fórmula, definición o metodología general — nunca sus datos concretos (nombre de empresa, cifras del ejemplo) como si fueran los de esta actividad.
- Si arriba aparece una "Decisión base ya establecida", esa decisión NO es negociable en este punto: aunque el material de referencia hable con más detalle o más énfasis de otra alternativa u opción distinta, tu respuesta debe desarrollarse sobre la decisión ya tomada, no sobre la que más aparezca en el material. Contradecir esa decisión (aunque sea implícitamente, retomando otra opción sin decirlo) es un error grave.
- Responde en español. No repitas el enunciado del punto ni comentes el proceso (nada de "aquí está tu respuesta"): ve directo al contenido."""

PROMPT_CORREGIR = """Eres el mismo asistente académico, ahora corrigiendo tu propio borrador de un punto específico de la actividad, a partir de una auditoría crítica que ya se hizo sobre el borrador completo. Tu trabajo es entregar la versión FINAL corregida de este punto — no un comentario sobre los cambios, el texto corregido en sí, listo para reemplazar por completo la respuesta anterior.

Punto que estás corrigiendo (punto {numero}):
--- PUNTO ---
{punto}
--- FIN PUNTO ---

Tu respuesta ANTERIOR a este punto (a corregir):
--- RESPUESTA ANTERIOR ---
{respuesta_original}
--- FIN RESPUESTA ANTERIOR ---

{decision_base}

Observaciones del auditor que aplican a este punto (corrígelas todas; si alguna de verdad no se puede resolver con el material disponible, dilo brevemente dentro del texto en vez de ignorarla en silencio):
--- OBSERVACIONES ---
{hallazgos}
--- FIN OBSERVACIONES ---

Puntos ya corregidos de esta misma actividad (mantén coherencia total con esto: mismos nombres, cifras y decisiones — cualquier cifra nueva que agregues debe cuadrar con las que ya aparecen aquí, o explicar por qué difiere):
--- YA CORREGIDO ---
{resueltos_previos}
--- FIN YA CORREGIDO ---

Material de referencia del curso más relevante para este punto (vuelve a apoyarte en él para corregir con precisión):
--- MATERIAL ---
{material}
--- FIN MATERIAL ---

Instrucciones:
- Entrega la versión FINAL corregida de este punto, completa y lista para el documento — nunca un resumen de qué cambiaste ni una lista de correcciones aparte.
- Corrige específicamente lo que señalan las observaciones: agrega cifras o cálculos si faltan (paso a paso, con la fórmula del material si existe), elimina o marca explícitamente como supuesto cualquier dato que no venga del material ni del enunciado, resuelve contradicciones numéricas con otros puntos, completa lo que esté marcado como faltante o a medias.
- Si la respuesta anterior adoptó el nombre de una empresa, cifras o un escenario que en realidad pertenece a un ejemplo o ejercicio DISTINTO del material (de otra unidad, o etiquetado como "[material general de otra unidad]") en vez del caso real que describe el enunciado de la actividad, esto es un error grave de fondo, no un detalle — reemplázalo por completo, aunque implique reescribir la mayor parte del punto.
- Si arriba aparece una "Decisión base ya establecida" y la respuesta anterior la contradice (p. ej. desarrolla una alternativa distinta a la que el Punto 1 eligió), esto también es un error grave de fondo que corregir — ajusta el contenido para que sea coherente con esa decisión base, no con la que domine en el material de referencia.
- Conserva todo lo que la respuesta anterior ya tenía bien — no reescribas desde cero lo que el auditor no señaló como un problema.
- Responde en español, directo al contenido corregido, sin comentar el proceso de corrección ni mencionar al auditor."""

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
- ¿Hay cifras, porcentajes, nombres propios o datos específicos que parecen inventados (no vienen del material ni del enunciado) sin estar marcados como supuesto?
- ¿Hay contradicciones numéricas entre puntos — por ejemplo, un margen, tasa o porcentaje que cambia de un punto a otro sin ninguna explicación?
- Cuando el material trae una fórmula o metodología de cálculo aplicable a un punto, ¿se aplicó de verdad con números concretos paso a paso, o se quedó en una descripción abstracta sin calcular nada?
- Si algún punto implica elegir entre varias alternativas u opciones (una estrategia, una fuente de financiación, un escenario), ¿se compararon explícitamente TODAS las opciones disponibles en el material antes de decidir, o se eligió una sin sustento comparativo frente a las demás?
- ¿Falta profundidad, ejemplos o justificación en algún punto comparado con lo que pide el enunciado?
- ¿Hay algo que debería tener una referencia o cita al material del curso y no la tiene?

Responde en español, en una lista concreta de observaciones — una por línea, cada una empezando con el punto o sección a la que aplica (p. ej. "Punto 2: ..."), o "General: ..." para observaciones que aplican a todo el documento (no a un punto en particular). Si en verdad no encuentras ningún problema en algún punto, dilo explícitamente ("Punto 3: sin observaciones") en vez de omitirlo. Sé específico: no digas "podría mejorar", di QUÉ falta o qué está mal exactamente, y en qué punto."""


MAX_TOKENS_TOPE = 24000  # límite superior del reintento por respuesta vacía (ver chat_texto)


def chat_texto(mensaje, cfg, max_tokens=8000, avisar=print, razonar=True, _reintento=False):
    """Usa la API nativa de LM Studio (`/api/v1/chat`, no la compatible con
    OpenAI): separa de verdad el razonamiento del mensaje final en la
    respuesta (`output: [{type: "reasoning"}, {type: "message"}]`), así que no
    hay que adivinar ni limpiar con regex — y permite apagar el razonamiento
    por completo con `reasoning: "off"` cuando la tarea no lo necesita. Sin
    esto, modelos razonadores locales (Qwen3...) pueden quedarse "pensando" en
    tareas simples de forma poco fiable, sin llegar nunca a una respuesta final
    limpia dentro de cualquier límite razonable de tokens — nos pasó de verdad
    armando este script: ver notas en segmentar_puntos().

    Si la respuesta sale vacía (típico en puntos que exigen mucho cálculo —
    presupuestos, WACC — donde el modelo agota `max_tokens` "pensando" antes
    de llegar a escribir la respuesta final), se reintenta UNA vez con el
    doble de `max_tokens` en vez de devolver un punto en blanco en el
    documento final."""
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
    respuesta = "\n".join(
        item["content"] for item in data.get("output", []) if item.get("type") == "message"
    ).strip()

    if not respuesta and not _reintento and max_tokens < MAX_TOKENS_TOPE:
        max_tokens_reintento = min(max_tokens * 2, MAX_TOKENS_TOPE)
        avisar(f"  Respuesta vacía de {modelo} (probablemente agotó el presupuesto de razonamiento) — reintentando con max_tokens={max_tokens_reintento}...")
        return chat_texto(mensaje, cfg, max_tokens=max_tokens_reintento, avisar=avisar, razonar=razonar, _reintento=True)

    return respuesta


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


def buscar_material_para_punto(punto, actividad_texto, fragmentos, cfg, top_k, unidad_actual=None):
    """Combina dos búsquedas: una ESTRECHA por el texto del punto (lo más
    relevante para responder justo esto) y otra AMPLIA por la actividad
    completa (para no perder argumentos repartidos en material que la
    consulta puntual, por sí sola, no habría encontrado — p. ej. cuando un
    punto pide "elegir una alternativa" pero los pros/contras de cada una
    están dispersos en fragmentos que no mencionan la palabra "elegir").

    Si `unidad_actual` se da (el nombre de la carpeta de la unidad donde
    vive la actividad, p. ej. "Unidad 3 - ..."), ambas búsquedas se hacen
    PRIMERO solo contra `fuentes/` y `apuntes/` de ESA unidad — ahí es donde
    casi siempre vive el caso o fuente específico que la actividad pide
    usar — y solo se agregan dos complementos más chicos: uno de `curso.md`
    (temario/contexto general del curso) y otro del resto de unidades,
    etiquetado explícitamente como material de otra unidad. `curso.md` NO
    se mete en el grupo principal aunque técnicamente sea "de este curso":
    son fragmentos cortos tipo pregunta/encabezado ("¿Qué es un proyecto?")
    que puntúan artificialmente alto en similitud contra casi cualquier
    consulta sobre "definir/formular un proyecto", y sin este límite pueden
    llenar TODOS los puestos del top_k desplazando por completo el material
    específico de la unidad (incluido el caso real de la actividad) — es el
    mismo tipo de contaminación que el filtro de otras unidades evita, solo
    que con un origen distinto.

    Los resultados se combinan sin duplicar fragmentos."""
    if unidad_actual:
        prefijo = unidad_actual + "/"
        propios = [f for f in fragmentos if f["archivo"].startswith(prefijo)]
        material_curso = [f for f in fragmentos if f["archivo"] == "curso.md"]
        otros = [f for f in fragmentos if not (f["archivo"].startswith(prefijo) or f["archivo"] == "curso.md")]
    else:
        propios, material_curso, otros = fragmentos, [], []

    resultados = buscar_relevantes(punto, propios, cfg, top_k=top_k)
    vistos = {(f["archivo"], f["texto"]) for f, _ in resultados}
    if actividad_texto:
        extra_k = max(4, top_k // 3)
        extra = buscar_relevantes(actividad_texto, propios, cfg, top_k=extra_k)
        for frag, sim in extra:
            clave = (frag["archivo"], frag["texto"])
            if clave not in vistos:
                resultados.append((frag, sim))
                vistos.add(clave)

    if material_curso:
        curso_k = min(2, len(material_curso))
        complemento = buscar_relevantes(punto, material_curso, cfg, top_k=curso_k)
        for frag, sim in complemento:
            clave = (frag["archivo"], frag["texto"])
            if clave not in vistos:
                resultados.append((frag, sim))
                vistos.add(clave)

    if otros:
        complemento_k = max(2, top_k // 4)
        complemento = buscar_relevantes(punto, otros, cfg, top_k=complemento_k)
        for frag, sim in complemento:
            clave = (frag["archivo"], frag["texto"])
            if clave in vistos:
                continue
            frag_etiquetado = {
                "archivo": f"[material general de otra unidad] {frag['archivo']}",
                "texto": frag["texto"],
            }
            resultados.append((frag_etiquetado, sim))
            vistos.add(clave)

    return resultados


def formatear_decision_base(numero, respuesta_punto_1):
    """El Punto 1 casi siempre establece una decisión fundacional (el nombre
    del proyecto, la alternativa estratégica elegida...) de la que dependen
    todos los demás puntos. Pasarla solo dentro de "resueltos_previos" no
    basta: ese bloque se trunca a 1.500 caracteres por punto y compite con
    el resto del contexto, así que en la práctica un punto posterior puede
    "olvidarla" y terminar desarrollando una alternativa distinta —
    literalmente la que más aparezca en el material recuperado para ESE
    punto — sin darse cuenta de que contradice al Punto 1. Por eso el texto
    completo del Punto 1 se repite aparte, con una etiqueta que dice
    explícitamente que no se puede contradecir (ver la instrucción
    correspondiente en PROMPT_PUNTO/PROMPT_CORREGIR)."""
    if numero == 1 or not respuesta_punto_1:
        return ""
    return (
        "Decisión base ya establecida en el Punto 1 (nombre del proyecto y/o alternativa elegida — "
        "NO la cambies ni la contradigas en este punto, ver instrucciones):\n"
        "--- PUNTO 1 (completo) ---\n"
        f"{respuesta_punto_1}\n"
        "--- FIN PUNTO 1 ---"
    )


def resolver_punto(numero, punto, lista_puntos, fragmentos, resueltos_previos, cfg, avisar=print, top_k=TOP_K_FRAGMENTOS, actividad_texto=None, unidad_actual=None, respuesta_punto_1=None):
    """Resuelve un punto por primera vez. Devuelve (respuesta, resultados) —
    `resultados` (los fragmentos de material usados) se reutiliza después en
    corregir_punto() para la segunda pasada, así la corrección se apoya en el
    mismo material sin tener que volver a buscarlo."""
    avisar(f"Resolviendo punto {numero}/{len(lista_puntos)}...")
    resultados = buscar_material_para_punto(punto, actividad_texto, fragmentos, cfg, top_k, unidad_actual=unidad_actual)
    contexto_general = "\n".join(f"{i}. {p}" for i, p in enumerate(lista_puntos, 1))
    if resueltos_previos:
        texto_previos = "\n\n".join(f"### Punto {i}\n{texto}" for i, texto in resueltos_previos)
    else:
        texto_previos = "(este es el primer punto, todavía no hay nada resuelto)"
    mensaje = PROMPT_PUNTO.format(
        contexto_general=contexto_general,
        decision_base=formatear_decision_base(numero, respuesta_punto_1),
        resueltos_previos=texto_previos,
        numero=numero,
        punto=punto,
        material=formatear_material(resultados),
    )
    respuesta = chat_texto(mensaje, cfg, max_tokens=10000, avisar=avisar)
    return respuesta, resultados


def parsear_critica_por_punto(critica):
    """Divide la crítica del auditor (una observación por línea, cada una
    empezando con "Punto N: ..." o "General: ...") en un dict {numero:
    [líneas]} más una lista aparte de observaciones "General". Tolera que el
    modelo parta una observación en varias líneas: lo que no calza con el
    patrón se pega a la última clave detectada, en vez de perderse."""
    por_punto = {}
    general = []
    clave_actual = None
    for linea in critica.splitlines():
        linea = linea.strip().lstrip("-*• ").strip()
        if not linea:
            continue
        m = re.match(r"^Punto\s+(\d+)\s*[:\-]\s*(.+)$", linea, re.IGNORECASE)
        if m:
            numero = int(m.group(1))
            por_punto.setdefault(numero, []).append(m.group(2))
            clave_actual = numero
            continue
        m = re.match(r"^General\s*[:\-]\s*(.+)$", linea, re.IGNORECASE)
        if m:
            general.append(m.group(1))
            clave_actual = "general"
            continue
        if clave_actual == "general":
            general[-1] += " " + linea
        elif isinstance(clave_actual, int):
            por_punto[clave_actual][-1] += " " + linea
        else:
            general.append(linea)
    return por_punto, general


def corregir_punto(numero, punto, respuesta_original, hallazgos_texto, material_formateado, resueltos_previos, cfg, avisar=print, total=None, respuesta_punto_1_corregida=None):
    avisar(f"Corrigiendo punto {numero}{f'/{total}' if total else ''}...")
    if resueltos_previos:
        texto_previos = "\n\n".join(f"### Punto {i}\n{texto}" for i, texto in resueltos_previos)
    else:
        texto_previos = "(este es el primer punto, todavía no hay nada corregido)"
    mensaje = PROMPT_CORREGIR.format(
        numero=numero,
        punto=punto,
        respuesta_original=respuesta_original,
        decision_base=formatear_decision_base(numero, respuesta_punto_1_corregida),
        hallazgos=hallazgos_texto or "(el auditor no señaló observaciones específicas para este punto)",
        resueltos_previos=texto_previos,
        material=material_formateado,
    )
    return chat_texto(mensaje, cfg, max_tokens=10000, avisar=avisar)


def auditar_borrador(actividad_texto, borrador, cfg, avisar=print, mensaje_progreso="Auditando el borrador completo (revisión crítica)..."):
    # max_tokens generoso: el borrador completo (todos los puntos ya resueltos)
    # entra en el prompt, y una auditoría de verdad crítica sobre un borrador
    # largo necesita espacio de sobra para no cortarse a mitad de camino.
    avisar(mensaje_progreso)
    mensaje = PROMPT_AUDITOR.format(actividad=actividad_texto, borrador=borrador)
    return chat_texto(mensaje, cfg, max_tokens=10000, avisar=avisar)


def encontrar_carpeta_curso(ruta_actividad):
    """Sube desde la actividad buscando un `curso.md` en algún ancestro — eso
    marca la carpeta del curso completo (`<Periodo> <Curso>/`), con todas sus
    unidades. Se detiene en REPO_ROOT (o si no encuentra ninguno, en la raíz
    del sistema de archivos) y devuelve None si nunca lo encuentra — p. ej.
    para un tema plano de `Desarrollo/`, que no tiene `curso.md`."""
    for ancestro in ruta_actividad.parents:
        if (ancestro / "curso.md").exists():
            return ancestro
        if ancestro == REPO_ROOT:
            break
    return None


def resolver_actividad(ruta_actividad, carpeta_fuentes=None, avisar=print):
    cfg = cargar_config()
    actividad_texto = quitar_frontmatter(obtener_texto_actividad(ruta_actividad, cfg, avisar=avisar))

    top_k = TOP_K_FRAGMENTOS
    unidad_actual = None  # solo se usa cuando se indexa el curso completo (ver más abajo)
    descripcion_material = "fuentes/ (carpeta indicada explícitamente con --fuentes)"
    if carpeta_fuentes is not None:
        # Carpeta de fuentes explícita (--fuentes): se respeta tal cual, sin
        # ampliar al curso completo.
        fragmentos = indexar_fuentes(carpeta_fuentes, cfg, avisar=avisar)
        try:
            ubicacion = carpeta_fuentes.relative_to(REPO_ROOT)
        except ValueError:
            ubicacion = carpeta_fuentes
    else:
        carpeta_curso = encontrar_carpeta_curso(ruta_actividad)
        if carpeta_curso is not None:
            avisar(f"Curso detectado: {carpeta_curso.relative_to(REPO_ROOT)}")
            avisar("Indexando curso.md + fuentes/ y apuntes/ de TODAS las unidades del curso (puede tardar la primera vez)...")
            fragmentos = indexar_curso(carpeta_curso, cfg, avisar=avisar)
            ubicacion = carpeta_curso.relative_to(REPO_ROOT)
            top_k = TOP_K_FRAGMENTOS_CURSO
            descripcion_material = f"curso.md + fuentes/ y apuntes/ de todas las unidades de '{carpeta_curso.name}'"
            # nombre de la carpeta de la unidad de la actividad tal como
            # queda etiquetado en `archivo` por indexar_curso() (relativo a
            # carpeta_curso) — se usa para priorizar su propio material
            # sobre el de otras unidades al buscar (ver buscar_material_para_punto)
            unidad_actual = ruta_actividad.parent.parent.name
        else:
            carpeta_fuentes = ruta_actividad.parent.parent / "fuentes"
            avisar(f"No se encontró 'curso.md' en ningún ancestro — se usa solo '{carpeta_fuentes.name}/' de esta carpeta.")
            fragmentos = indexar_fuentes(carpeta_fuentes, cfg, avisar=avisar)
            try:
                ubicacion = carpeta_fuentes.relative_to(REPO_ROOT)
            except ValueError:
                ubicacion = carpeta_fuentes
            descripcion_material = f"{carpeta_fuentes.name}/ de esta carpeta (no se encontró curso.md en ningún ancestro)"

    if fragmentos:
        avisar(f"Material de referencia: {ubicacion} ({len(fragmentos)} fragmentos en total)")
    else:
        avisar(f"No se encontró material en '{ubicacion}' — se responde solo con el conocimiento general del modelo.")

    puntos = segmentar_puntos(actividad_texto, cfg, avisar=avisar)

    # --- Primera pasada: borrador inicial, punto por punto ---
    secciones = []
    resueltos_previos = []
    respuestas_por_punto = {}
    material_por_punto = {}
    respuesta_punto_1 = None  # texto completo del Punto 1 — ver formatear_decision_base()
    for i, punto in enumerate(puntos, 1):
        respuesta, resultados = resolver_punto(
            i, punto, puntos, fragmentos, resueltos_previos, cfg,
            avisar=avisar, top_k=top_k, actividad_texto=actividad_texto,
            unidad_actual=unidad_actual, respuesta_punto_1=respuesta_punto_1,
        )
        respuestas_por_punto[i] = respuesta
        if i == 1:
            respuesta_punto_1 = respuesta
        material_por_punto[i] = resultados
        titulo_punto = punto if len(punto) <= 90 else punto[:87] + "..."
        secciones.append(f"## Punto {i}: {titulo_punto}\n\n{respuesta}")
        # se acota el tamaño para que el contexto de "coherencia" no crezca sin
        # límite con actividades de muchos puntos o respuestas muy largas
        resumen_previo = respuesta if len(respuesta) <= TOPE_RESUELTO_PREVIO else respuesta[:TOPE_RESUELTO_PREVIO] + "\n[...]"
        resueltos_previos.append((i, resumen_previo))
    borrador = "\n\n".join(secciones)

    critica = auditar_borrador(actividad_texto, borrador, cfg, avisar=avisar)

    # --- Segunda pasada: corrección dirigida por los hallazgos de la auditoría ---
    avisar("Corrigiendo el borrador punto por punto a partir de la auditoría...")
    hallazgos_por_punto, hallazgos_generales = parsear_critica_por_punto(critica)
    texto_generales = "\n".join(f"- {h}" for h in hallazgos_generales)

    secciones_corregidas = []
    resueltos_corregidos = []
    respuesta_punto_1_corregida = None
    for i, punto in enumerate(puntos, 1):
        partes_hallazgos = [f"- {h}" for h in hallazgos_por_punto.get(i, [])]
        if texto_generales:
            partes_hallazgos.append(f"Observaciones generales de todo el documento:\n{texto_generales}")
        respuesta_corregida = corregir_punto(
            i, punto, respuestas_por_punto[i], "\n".join(partes_hallazgos),
            formatear_material(material_por_punto[i]), resueltos_corregidos, cfg,
            avisar=avisar, total=len(puntos), respuesta_punto_1_corregida=respuesta_punto_1_corregida,
        )
        if i == 1:
            respuesta_punto_1_corregida = respuesta_corregida
        titulo_punto = punto if len(punto) <= 90 else punto[:87] + "..."
        secciones_corregidas.append(f"## Punto {i}: {titulo_punto}\n\n{respuesta_corregida}")
        resumen_corr = respuesta_corregida if len(respuesta_corregida) <= TOPE_RESUELTO_PREVIO else respuesta_corregida[:TOPE_RESUELTO_PREVIO] + "\n[...]"
        resueltos_corregidos.append((i, resumen_corr))
    borrador_final = "\n\n".join(secciones_corregidas)

    # --- Verificación final: auditar la versión YA corregida ---
    critica_final = auditar_borrador(
        actividad_texto, borrador_final, cfg, avisar=avisar,
        mensaje_progreso="Verificación final (auditando el borrador ya corregido)...",
    )

    carpeta_actividades = ruta_actividad.parent
    slug = slugify(ruta_actividad.stem)
    ruta_salida = carpeta_actividades / f"{slug}-borrador-ia.md"

    frontmatter = construir_frontmatter(
        carpeta_actividades,
        f"{ruta_actividad.stem} (borrador IA)",
        origen=(
            f"borrador generado por IA a partir de {descripcion_material} "
            "(RAG, punto por punto, con una segunda pasada de corrección dirigida "
            "por auditoría crítica) — revisar y ajustar antes de entregar"
        ),
        campos_extra={"borrador_ia": True},
    )
    contenido = (
        f"{frontmatter}\n# {ruta_actividad.stem} — borrador IA\n\n{borrador_final}\n\n"
        "---\n\n## Verificación final (auditor IA, tras la corrección)\n\n"
        "> Este borrador ya pasó por una primera auditoría crítica y una corrección "
        "dirigida por esos hallazgos, punto por punto. Lo que se señala aquí es la "
        "auditoría sobre la versión YA CORREGIDA — no es infalible, pero lo que quede "
        "listado suele ser lo que de verdad conviene mirar antes de entregar (a menudo "
        "datos reales que ni el material del curso ni la IA pueden inventar: nombres del "
        "equipo, fechas exactas, cifras negociadas con terceros).\n\n"
        f"{critica_final}\n"
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
