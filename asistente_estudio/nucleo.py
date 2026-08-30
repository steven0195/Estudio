"""
Funciones y configuración compartidas entre los programas de asistente_estudio/
(capturas.py, transcriptor_documentos.py, solucionador_actividades.py,
rag_fuentes.py). No se corre directo.
"""

import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# En algunas consolas de Windows (cp1252/cp850) los acentos y "¿/¡" salen mal
# si no se fuerza UTF-8 explícitamente en la entrada/salida estándar.
for _stream in (sys.stdout, sys.stdin, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent  # raíz del repo: aquí viven "Administracion de empresas" y "Desarrollo"
CONFIG_PATH = SCRIPT_DIR / "config.json"
STATE_PATH = SCRIPT_DIR / "estado.json"

# Si un archivo nuevo se crea dentro de una carpeta con uno de estos nombres,
# el frontmatter usa el "tipo" correspondiente. Fuera de esas carpetas (p. ej.
# directo en la raíz de un curso, junto a curso.md) se usa "nota" por defecto.
TIPO_POR_CARPETA = {"apuntes": "apunte", "fuentes": "fuente", "actividades": "actividad"}

DEFAULT_CONFIG = {
    "lmstudio_base_url": "http://localhost:1234/v1",
    "lmstudio_model": "google/gemma-4-e2b",
    "lmstudio_model_texto": "qwen/qwen3.5-9b",
    "lmstudio_model_embeddings": "text-embedding-nomic-embed-text-v1.5",
    "hotkey": "ctrl+shift+p",
    "prompt": (
        "Transcribe TODO el contenido visible de esta imagen a formato Markdown, "
        "preservando la estructura original con la mayor fidelidad posible: usa "
        "encabezados (#, ##, ###) para títulos y subtítulos, tablas Markdown si hay "
        "tablas, listas (- o 1.) si hay listas, y bloques de código ``` para código "
        "o fórmulas. No describas la imagen ni agregues comentarios propios: "
        "transcribe únicamente lo que está escrito o dibujado. Si una parte es "
        "ilegible, escribe [ilegible] en ese punto. Conserva el idioma original del texto."
    ),
    "prompt_descripcion_imagen": (
        "Esta imagen aparece dentro de un documento académico o de estudio. "
        "Descríbela de forma clara y completa para alguien que no puede verla: "
        "si es un diagrama, mapa conceptual o flujo, enumera sus elementos/pasos y "
        "cómo se conectan; si es una tabla o gráfico, describe los datos que "
        "muestra; si es una foto o ilustración, describe qué se ve. No repitas "
        "texto que ya esté transcrito en el documento, describe solo el "
        "contenido visual. Sé conciso pero completo, en español."
    ),
}


def cargar_config():
    if CONFIG_PATH.exists():
        cfg = {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text(encoding="utf-8"))}
    else:
        cfg = dict(DEFAULT_CONFIG)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def cargar_ultimo_archivo():
    """Último archivo donde se guardó una captura, si todavía existe."""
    if not STATE_PATH.exists():
        return None
    try:
        ruta = json.loads(STATE_PATH.read_text(encoding="utf-8")).get("ultimo_archivo")
    except (json.JSONDecodeError, OSError):
        return None
    if not ruta:
        return None
    archivo = REPO_ROOT / ruta
    return archivo if archivo.is_file() else None


def guardar_ultimo_archivo(archivo):
    try:
        STATE_PATH.write_text(
            json.dumps({"ultimo_archivo": str(archivo.relative_to(REPO_ROOT))}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def slugify(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    return re.sub(r"[\s_]+", "-", texto) or "sin-titulo"


def quitar_frontmatter(texto):
    return re.sub(r"^---\n.*?\n---\n", "", texto, count=1, flags=re.DOTALL).strip()


def limpiar_markdown(texto):
    texto = texto.strip()

    # Algunos modelos "razonadores" (formato harmony/gpt-oss) filtran su cadena de
    # pensamiento con marcadores de canal antes de la respuesta final, aunque se les
    # pida no comentar nada. Si aparece un marcador de ese tipo, nos quedamos solo
    # con lo que viene después del último.
    partes = re.split(r"<\|?channel\|?>\s*final\s*<\|?message\|?>|<channel\|>", texto, flags=re.IGNORECASE)
    if len(partes) > 1:
        texto = partes[-1]
    texto = re.sub(r"<\|[^>]*\|>", "", texto).strip()

    # Otros modelos (familia Qwen3, DeepSeek-R1) envuelven el razonamiento en
    # <think>...</think> en vez del formato harmony. La etiqueta de apertura a
    # veces la agrega el propio chat template del servidor y no se repite en la
    # respuesta — así que basta con cortar todo lo que venga antes del ÚLTIMO
    # </think>, exista o no un <think> de apertura visible.
    if "</think>" in texto.lower():
        texto = re.split(r"</think>", texto, flags=re.IGNORECASE)[-1].strip()

    if texto.startswith("```"):
        lineas = texto.split("\n")
        if lineas[0].startswith("```"):
            lineas = lineas[1:]
        if lineas and lineas[-1].strip() == "```":
            lineas = lineas[:-1]
        texto = "\n".join(lineas)
    return texto.strip()


def metadatos_desde_ruta(carpeta):
    """Deriva área/curso/periodo/unidad/tema/tipo a partir de la ubicación de la carpeta en el repo."""
    partes = carpeta.relative_to(REPO_ROOT).parts
    meta = {"area": partes[0] if partes else None}
    for parte in partes:
        m = re.match(r"^(\d{4}-\d T\d) (.+)$", parte)
        if m:
            meta["periodo"], meta["curso"] = m.group(1), m.group(2)
        mu = re.match(r"^Unidad (\d+) - (.+)$", parte)
        if mu:
            meta["unidad"], meta["tema"] = mu.group(1), mu.group(2).replace("_", " ")
    if "curso" not in meta and len(partes) > 1:
        meta["tema_area"] = partes[1]  # p. ej. Desarrollo/Spring Boot -> "Spring Boot"
    meta["tipo"] = TIPO_POR_CARPETA.get(partes[-1] if partes else "", "nota")
    return meta


def construir_frontmatter(carpeta, titulo, origen="captura de pantalla", campos_extra=None):
    meta = metadatos_desde_ruta(carpeta)
    campos = {"tipo": meta["tipo"], "area": meta["area"]}
    if "curso" in meta:
        campos["curso"] = meta["curso"]
        campos["periodo"] = meta["periodo"]
    if "tema_area" in meta:
        campos["tema_area"] = meta["tema_area"]
    if "unidad" in meta:
        campos["unidad"] = meta["unidad"]
        campos["tema"] = meta["tema"]
    campos["titulo"] = titulo
    campos["origen"] = origen
    if campos_extra:
        campos.update(campos_extra)

    lineas = ["---"]
    for clave, valor in campos.items():
        if isinstance(valor, bool):
            lineas.append(f"{clave}: {'true' if valor else 'false'}")  # YAML, no el "True" de Python
        elif isinstance(valor, str) and (" " in valor or ":" in valor):
            lineas.append(f'{clave}: "{valor}"')
        else:
            lineas.append(f"{clave}: {valor}")
    lineas.append("tags: []")
    lineas.append("---\n")
    return "\n".join(lineas)


def citar_bloque(texto):
    """Antepone '> ' a cada línea para que el bloque se lea como una cita/aparte,
    nunca como un encabezado ni como texto corrido del documento."""
    return "\n".join(f"> {linea}" if linea else ">" for linea in texto.split("\n"))
