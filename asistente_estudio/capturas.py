"""
Capturas de pantalla de estudio.

Corre en segundo plano escuchando un atajo de teclado. Al presionarlo, te deja
recortar una región de la pantalla, la envía a un modelo de visión local en
LM Studio para transcribirla a Markdown, y te pregunta en la terminal dónde
guardarla: navegas el repo carpeta por carpeta hasta un .md nuevo o existente
(incluidos archivos sueltos como curso.md), y si el archivo tiene secciones
puedes elegir en cuál insertar la captura.

Requisitos:
  - LM Studio corriendo con el servidor local activo y un modelo con soporte
    de imágenes cargado (ver config.json -> lmstudio_model).
  - pip install -r requirements.txt

Uso:
  python capturas.py
"""

import base64
import queue
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import keyboard
import requests
import tkinter as tk
from PIL import ImageGrab

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from nucleo import (  # noqa: E402
    REPO_ROOT,
    cargar_config,
    cargar_ultimo_archivo,
    citar_bloque,
    construir_frontmatter,
    guardar_ultimo_archivo,
    limpiar_markdown,
    slugify,
)


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
# Formato del bloque insertado (cita, nunca encabezado real ni texto corrido)
# ---------------------------------------------------------------------------

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
    print("Capturas de pantalla de estudio")
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
