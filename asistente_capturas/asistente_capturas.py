"""
Asistente de capturas de estudio.

Corre en segundo plano escuchando un atajo de teclado. Al presionarlo, te deja
recortar una región de la pantalla, la envía a un modelo de visión local en
LM Studio para transcribirla a Markdown, y te pregunta en la terminal dónde
guardarla: navegas el repo carpeta por carpeta hasta un .md nuevo o existente
(incluidos archivos sueltos como curso.md), y si el archivo tiene secciones
puedes elegir en cuál insertar la captura.

Requisitos:
  - LM Studio corriendo con el servidor local activo y un modelo con soporte
    de imágenes cargado (ver capturas_config.json -> lmstudio_model).
  - pip install -r requirements.txt

Uso:
  python asistente_capturas.py
"""

import base64
import json
import queue
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import keyboard
import requests
import tkinter as tk
from PIL import ImageGrab

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
CONFIG_PATH = SCRIPT_DIR / "capturas_config.json"
STATE_PATH = SCRIPT_DIR / "capturas_state.json"

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


# ---------------------------------------------------------------------------
# Captura de pantalla con selección de región (estilo "recorte")
# ---------------------------------------------------------------------------

def seleccionar_region(root):
    """Overlay de pantalla completa: arrastra para elegir una región. Esc cancela.

    `root` es la ventana raíz de Tk creada una sola vez en main() — esta función
    SIEMPRE debe llamarse desde el hilo principal (nunca desde el callback del
    atajo de teclado, que corre en su propio hilo; crear ventanas de Tk fuera
    del hilo principal puede tumbar todo el proceso)."""
    resultado = {}
    ventana = tk.Toplevel(root)
    ventana.attributes("-fullscreen", True)
    ventana.attributes("-alpha", 0.25)
    ventana.attributes("-topmost", True)
    ventana.configure(bg="black")
    canvas = tk.Canvas(ventana, cursor="cross", bg="black", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    inicio = {}
    rect_id = {"id": None}

    def on_press(event):
        inicio["x"], inicio["y"] = event.x, event.y
        rect_id["id"] = canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#ff3b3b", width=2
        )

    def on_drag(event):
        canvas.coords(rect_id["id"], inicio["x"], inicio["y"], event.x, event.y)

    def on_release(event):
        x1, y1, x2, y2 = inicio["x"], inicio["y"], event.x, event.y
        resultado["bbox"] = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        ventana.destroy()

    def on_escape(_event):
        resultado["bbox"] = None
        ventana.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    ventana.bind("<Escape>", on_escape)
    ventana.grab_set()
    ventana.focus_force()
    ventana.wait_window()  # espera a que se cierre, sin bloquear con un mainloop() anidado propio
    return resultado.get("bbox")


def capturar_region(root):
    bbox = seleccionar_region(root)
    if not bbox or bbox[2] - bbox[0] < 5 or bbox[3] - bbox[1] < 5:
        print("Captura cancelada.")
        return None
    time.sleep(0.15)  # dejar que el overlay se cierre antes de tomar la captura
    return ImageGrab.grab(bbox=bbox)


# ---------------------------------------------------------------------------
# LM Studio: transcripción de la imagen a Markdown
# ---------------------------------------------------------------------------

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


def transcribir_imagen(image_path, cfg):
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    payload = {
        "model": cfg["lmstudio_model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": cfg["prompt"]},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
    }
    resp = requests.post(
        f"{cfg['lmstudio_base_url']}/chat/completions", json=payload, timeout=180
    )
    resp.raise_for_status()
    data = resp.json()
    return limpiar_markdown(data["choices"][0]["message"]["content"])


# ---------------------------------------------------------------------------
# Selección interactiva del destino: un explorador de carpetas genérico.
#
# En cada carpeta ves sus subcarpetas Y sus archivos .md (como curso.md, que
# vive suelto en la raíz del curso) — puedes entrar a una subcarpeta, elegir
# un .md existente, o crear uno nuevo ahí mismo. "b" retrocede, "0" cancela.
# ---------------------------------------------------------------------------

CANCELAR = object()
ATRAS = object()
NUEVO = object()


def listar_subcarpetas(path):
    if not path.exists():
        return []
    return sorted(
        [
            p
            for p in path.iterdir()
            if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("__")
        ],
        key=lambda p: p.name.lower(),
    )


def describir_archivo_md(path):
    """Título (del frontmatter o del primer encabezado) + fecha de edición, para orientar la elección."""
    etiqueta = path.stem
    try:
        texto = path.read_text(encoding="utf-8")
        m = re.search(r'^titulo:\s*"?([^"\n]+?)"?\s*$', texto, re.MULTILINE)
        if not m:
            m = re.search(r"^#\s+(.+)$", texto, re.MULTILINE)
        if m:
            etiqueta = m.group(1).strip()
    except OSError:
        pass
    editado = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return f"{path.name}  —  \"{etiqueta}\"  (editado {editado})"


def elegir_de_lista(breadcrumb, titulo, opciones, mostrar=lambda o: o.name, permitir_atras=True):
    if breadcrumb:
        print(f"\n[{breadcrumb}]")
    print(titulo)
    for i, op in enumerate(opciones, 1):
        print(f"  {i}. {mostrar(op)}")
    if permitir_atras:
        print("  b. Atrás")
    print("  0. Cancelar")
    while True:
        raw = input("Elige un número: ").strip().lower()
        if raw == "0":
            return CANCELAR
        if permitir_atras and raw == "b":
            return ATRAS
        if raw.isdigit() and 1 <= int(raw) <= len(opciones):
            return opciones[int(raw) - 1]
        print("  Opción inválida, intenta de nuevo.")


MISMO_ARCHIVO = object()
OTRO_DESTINO = object()


def elegir_destino():
    """Explora el repo carpeta por carpeta hasta llegar a un .md (nuevo o existente).

    Si la captura anterior se guardó en algún archivo, primero pregunta si esta
    también va ahí (y en tal caso salta directo a elegir la sección) antes de
    mostrar el explorador de carpetas completo desde el principio.
    """
    ultimo = cargar_ultimo_archivo()
    if ultimo is not None:
        while True:
            sel = elegir_de_lista(
                "",
                "¿Dónde quieres guardar esta captura?",
                [MISMO_ARCHIVO, OTRO_DESTINO],
                mostrar=lambda o: (
                    f"Seguir en el mismo archivo de la última vez: {ultimo.relative_to(REPO_ROOT)}"
                    if o is MISMO_ARCHIVO
                    else "Elegir un destino distinto"
                ),
                permitir_atras=False,
            )
            if sel is CANCELAR:
                return None
            if sel is OTRO_DESTINO:
                break
            seccion = elegir_seccion_destino(ultimo)
            if seccion is CANCELAR:
                continue  # vuelve a preguntar "mismo archivo o distinto"
            return {"modo": "append", "archivo": ultimo, "seccion": seccion}

    actual = REPO_ROOT
    pila = []

    while True:
        rel = actual.relative_to(REPO_ROOT)
        migas = str(rel) if str(rel) != "." else "raíz del repo"

        subcarpetas = [p for p in listar_subcarpetas(actual) if p != SCRIPT_DIR]
        archivos_md = sorted(actual.glob("*.md"))
        opciones = subcarpetas + archivos_md + [NUEVO]

        def mostrar(o):
            if o is NUEVO:
                return "+ Crear un archivo nuevo aquí"
            if o in subcarpetas:
                return f"[carpeta] {o.name}"
            return f"[archivo] {describir_archivo_md(o)}"

        sel = elegir_de_lista(
            migas, "¿Dónde quieres guardar la captura?", opciones, mostrar=mostrar, permitir_atras=bool(pila)
        )
        if sel is CANCELAR:
            return None
        if sel is ATRAS:
            actual = pila.pop()
            continue
        if sel is NUEVO:
            titulo = input("Título de la nota nueva: ").strip() or "Captura sin título"
            return {
                "modo": "nuevo",
                "carpeta": actual,
                "titulo": titulo,
                "archivo": actual / f"{slugify(titulo)}.md",
            }
        if sel in subcarpetas:
            pila.append(actual)
            actual = sel
            continue

        # sel es un .md existente: preguntar en qué sección insertar la captura
        seccion = elegir_seccion_destino(sel)
        if seccion is CANCELAR:
            continue  # vuelve al mismo listado, no se perdió nada
        return {"modo": "append", "archivo": sel, "seccion": seccion}


# ---------------------------------------------------------------------------
# Inserción dentro de una sección concreta del archivo (para no romper su
# estructura: si el archivo tiene "## Unidades", "## Notas", etc., insertamos
# la captura dentro de la sección elegida en vez de siempre al final).
# ---------------------------------------------------------------------------

def listar_secciones(texto):
    return [
        {"nivel": len(m.group(1)), "titulo": m.group(2).strip(), "inicio": m.start()}
        for m in re.finditer(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", texto, re.MULTILINE)
    ]


def elegir_seccion_destino(path):
    texto = path.read_text(encoding="utf-8")
    secciones = listar_secciones(texto)
    opciones = [None] + secciones
    sel = elegir_de_lista(
        path.name,
        "¿En qué parte del archivo va la captura?",
        opciones,
        mostrar=lambda o: "Al final del archivo"
        if o is None
        else ("    " * (o["nivel"] - 1)) + f"Dentro de: {'#' * o['nivel']} {o['titulo']}",
    )
    return sel  # None = al final; dict de sección = insertar ahí; CANCELAR si cancela


def insertar_en_seccion(texto, seccion, bloque):
    """Inserta `bloque` justo antes del siguiente encabezado del mismo nivel o superior
    a `seccion` (o al final del archivo si no hay ninguno), preservando todo lo demás."""
    fin_linea = texto.find("\n", seccion["inicio"])
    cuerpo_desde = (fin_linea + 1) if fin_linea != -1 else len(texto)
    patron_siguiente = re.compile(r"^#{1,%d}[ \t]+.+$" % seccion["nivel"], re.MULTILINE)
    m = patron_siguiente.search(texto, cuerpo_desde)
    punto = m.start() if m else len(texto)
    antes = texto[:punto].rstrip("\n")
    despues = texto[punto:].lstrip("\n")
    return f"{antes}\n\n{bloque}\n\n{despues}" if despues else f"{antes}\n\n{bloque}\n"


# ---------------------------------------------------------------------------
# Construcción del frontmatter y escritura del archivo
# ---------------------------------------------------------------------------

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


MODO_COMPLETA = "completa"
MODO_CONTENIDO = "contenido"
DESCRIPCION_MODO_BLOQUE = {
    MODO_COMPLETA: "Nota completa: imagen y texto transcrito, todo como cita",
    MODO_CONTENIDO: "Agregar al contenido: solo la referencia de la captura va como cita; el texto transcrito se agrega como contenido normal",
}


def elegir_opciones_bloque():
    """Pregunta el modo de inserción y, al final, un encabezado opcional (Enter = ninguno)."""
    modo = elegir_de_lista(
        "",
        "¿Cómo quieres agregar la captura?",
        [MODO_COMPLETA, MODO_CONTENIDO],
        mostrar=lambda o: DESCRIPCION_MODO_BLOQUE[o],
        permitir_atras=False,
    )
    if modo is CANCELAR:
        return None
    encabezado = input("Encabezado para esta captura (Enter para no ponerle uno): ").strip()
    return {"modo_bloque": modo, "encabezado": encabezado or None}


def formatear_bloque_captura(ts, ref_imagen, markdown_texto, modo_bloque, encabezado):
    fecha_legible = datetime.strptime(ts, "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M")
    referencia = citar_bloque(f"**Captura de pantalla** — {fecha_legible}\n\n{ref_imagen}")

    if modo_bloque == MODO_COMPLETA:
        bloque = citar_bloque(f"**Captura de pantalla** — {fecha_legible}\n\n{ref_imagen}\n\n{markdown_texto}")
    else:
        bloque = f"{referencia}\n\n{markdown_texto}"

    if encabezado:
        bloque = f"## {encabezado}\n\n{bloque}"
    return bloque


def guardar_captura(img, markdown_texto, destino, opciones_bloque):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    carpeta = destino["carpeta"] if destino["modo"] == "nuevo" else destino["archivo"].parent
    src_dir = carpeta / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    imagen_nombre = f"captura-{ts}.png"
    img.save(src_dir / imagen_nombre)
    ref_imagen = f"![Captura](src/{imagen_nombre})"

    if not markdown_texto:
        markdown_texto = "_[No se pudo transcribir automáticamente. Edita este bloque a mano.]_"

    bloque = formatear_bloque_captura(
        ts, ref_imagen, markdown_texto, opciones_bloque["modo_bloque"], opciones_bloque["encabezado"]
    )

    if destino["modo"] == "nuevo":
        contenido = construir_frontmatter(destino["carpeta"], destino["titulo"])
        contenido += f"\n# {destino['titulo']}\n\n{bloque}\n"
        destino["carpeta"].mkdir(parents=True, exist_ok=True)
        destino["archivo"].write_text(contenido, encoding="utf-8")
        guardar_ultimo_archivo(destino["archivo"])
        print(f"\nCreado: {destino['archivo'].relative_to(REPO_ROOT)}")
        return

    existente = destino["archivo"].read_text(encoding="utf-8")
    seccion = destino.get("seccion")
    if seccion is None:
        nuevo_texto = existente.rstrip("\n") + f"\n\n{bloque}\n"
    else:
        nuevo_texto = insertar_en_seccion(existente, seccion, bloque)
    destino["archivo"].write_text(nuevo_texto, encoding="utf-8")
    guardar_ultimo_archivo(destino["archivo"])
    print(f"\nAñadido a: {destino['archivo'].relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Flujo principal
# ---------------------------------------------------------------------------

def procesar_captura(cfg, root):
    print("\n[Captura] Arrastra el mouse para seleccionar una región (Esc para cancelar)...")
    img = capturar_region(root)
    if img is None:
        return

    print("Transcribiendo con el modelo local de LM Studio...")
    try:
        markdown_texto = transcribir_imagen_temp(img, cfg)
    except Exception as e:
        print(f"  No se pudo transcribir automáticamente ({e}).")
        print("  Se guardará la imagen igual; puedes escribir la transcripción a mano.")
        markdown_texto = ""

    destino = elegir_destino()
    if destino is None:
        print("Cancelado, nada se guardó.")
        return

    opciones_bloque = elegir_opciones_bloque()
    if opciones_bloque is None:
        print("Cancelado, nada se guardó.")
        return

    guardar_captura(img, markdown_texto, destino, opciones_bloque)


def transcribir_imagen_temp(img, cfg):
    tmp_path = SCRIPT_DIR / "_captura_temp.png"
    try:
        img.save(tmp_path)
        return transcribir_imagen(tmp_path, cfg)
    finally:
        tmp_path.unlink(missing_ok=True)


def main():
    cfg = cargar_config()
    print("Asistente de capturas de estudio")
    print(f"  Atajo de captura : {cfg['hotkey']}")
    print(f"  LM Studio        : {cfg['lmstudio_base_url']} (modelo: {cfg['lmstudio_model']})")
    print("  Ctrl+C en esta ventana para salir.\n")
    print("Deja esta terminal abierta. Presiona el atajo cuando quieras capturar algo.")

    # Una sola raíz de Tk, creada aquí en el hilo principal y nunca destruida
    # hasta salir. El atajo de teclado corre en su propio hilo (biblioteca
    # `keyboard`) y NO debe tocar Tkinter directamente: solo encola un aviso
    # thread-safe; root.after() lo recoge y procesa la captura en el hilo
    # principal, que es el único seguro para crear/destruir ventanas.
    root = tk.Tk()
    root.withdraw()

    solicitudes = queue.Queue()
    keyboard.add_hotkey(cfg["hotkey"], lambda: solicitudes.put(True))

    def revisar_solicitudes():
        try:
            solicitudes.get_nowait()
        except queue.Empty:
            pass
        else:
            procesar_captura(cfg, root)
        root.after(150, revisar_solicitudes)

    root.after(150, revisar_solicitudes)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    print("\nHasta luego.")


if __name__ == "__main__":
    main()
