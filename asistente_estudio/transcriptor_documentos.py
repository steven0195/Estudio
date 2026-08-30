"""
Transcriptor de documentos a Markdown.

Convierte .txt, .pdf, .docx y .pptx a Markdown. El texto se extrae tal cual
(no lo reescribe ni resume una IA — fidelidad al original), y cada imagen o
diagrama que encuentra se la muestra al modelo de visión local de LM Studio
para que la describa; esa descripción se inserta como **cita** justo junto a
la imagen (mismo formato que usa capturas.py), para que tanto una persona
como un modelo que solo lea texto entiendan también qué muestran las
ilustraciones, sin que la descripción se confunda con el texto original.

Requisitos:
  - pandoc instalado y en el PATH (para .docx y .pptx).
  - pip install -r requirements.txt (agrega pymupdf, para .pdf).
  - LM Studio con un modelo de visión cargado y el servidor local activo
    (usa el mismo config.json que el resto de los programas de esta carpeta).

Uso:
  python transcriptor_documentos.py "<archivo>"
  python transcriptor_documentos.py "<carpeta>"              # convierte todo lo soportado ahí
  python transcriptor_documentos.py "<carpeta>" --forzar     # re-convierte aunque ya exista el .md
"""

import base64
import hashlib
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

import pymupdf
import requests

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from nucleo import (  # noqa: E402
    REPO_ROOT,
    cargar_config,
    citar_bloque,
    construir_frontmatter,
    limpiar_markdown,
    slugify,
)

EXTENSIONES_SOPORTADAS = {".txt", ".pdf", ".docx", ".pptx", ".doc"}
EXTENSIONES_IMAGEN_DESCRIBIBLES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

PROMPT_DESCRIPCION_IMAGEN_DEFAULT = (
    "Esta imagen aparece dentro de un documento académico o de estudio. "
    "Descríbela de forma clara y completa para alguien que no puede verla: "
    "si es un diagrama, mapa conceptual o flujo, enumera sus elementos/pasos y "
    "cómo se conectan; si es una tabla o gráfico, describe los datos que "
    "muestra; si es una foto o ilustración, describe qué se ve. No repitas "
    "texto que ya esté transcrito en el documento, describe solo el "
    "contenido visual. Sé conciso pero completo, en español."
)


# ---------------------------------------------------------------------------
# Descripción de imágenes vía LM Studio
# ---------------------------------------------------------------------------

def describir_imagen(ruta_imagen, cfg):
    with open(ruta_imagen, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    prompt = cfg.get("prompt_descripcion_imagen") or PROMPT_DESCRIPCION_IMAGEN_DEFAULT
    payload = {
        "model": cfg["lmstudio_model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
        "temperature": 0.2,
        "max_tokens": 1000,
    }
    resp = requests.post(f"{cfg['lmstudio_base_url']}/chat/completions", json=payload, timeout=120)
    resp.raise_for_status()
    return limpiar_markdown(resp.json()["choices"][0]["message"]["content"])


def insertar_descripciones(md_texto, carpeta_md, cfg, avisar=print):
    """Busca cada imagen en el markdown —tanto ![alt](ruta) como <img src="ruta">,
    que es lo que usa pandoc cuando el docx/pptx original traía un tamaño explícito
    para la imagen— y, si el formato es uno que el modelo de visión puede leer,
    inserta su descripción justo después como cita. Formatos no soportados
    (p. ej. .emf/.wmf, típicos de gráficos vectoriales de Office) se dejan sin
    describir, con un aviso, en vez de fallar.

    Cachea por hash de contenido: es común que un mismo documento repita la
    misma imagen muchas veces (p. ej. un fondo decorativo detrás de cada cuadro
    de texto de una diapositiva) — así solo se describe una vez cada una."""
    import re

    cache = {}

    def describir_y_citar(ruta_str):
        ruta_completa = carpeta_md / ruta_str
        if ruta_completa.suffix.lower() not in EXTENSIONES_IMAGEN_DESCRIBIBLES or not ruta_completa.exists():
            avisar(f"  (sin describir, formato no soportado por el modelo de visión: {ruta_str})")
            return None
        huella = hashlib.md5(ruta_completa.read_bytes()).hexdigest()
        if huella in cache:
            return cache[huella]
        try:
            descripcion = describir_imagen(ruta_completa, cfg)
        except Exception as e:
            avisar(f"  (no se pudo describir {ruta_str}: {e})")
            cache[huella] = None
            return None
        cita = citar_bloque(f"**Descripción de la imagen** — {descripcion}")
        cache[huella] = cita
        return cita

    def reemplazo_markdown(m):
        cita = describir_y_citar(m.group(2))
        return f"{m.group(0)}\n\n{cita}" if cita else m.group(0)

    def reemplazo_html(m):
        cita = describir_y_citar(m.group(1))
        return f"{m.group(0)}\n\n{cita}" if cita else m.group(0)

    # La ruta puede venir seguida de un título entre comillas: ![alt](ruta "título") —
    # el grupo de ruta debe cortar ahí, si no se le pega el título completo a la extensión.
    md_texto = re.sub(r'!\[([^\]]*)\]\(([^\s)]+)(?:\s+"[^"]*")?\)', reemplazo_markdown, md_texto)
    md_texto = re.sub(r'<img\s+src="([^"]+)"[^>]*/?>', reemplazo_html, md_texto)
    return md_texto


# ---------------------------------------------------------------------------
# DOCX / PPTX vía pandoc
# ---------------------------------------------------------------------------

def convertir_docx_pptx(ruta_origen, carpeta_salida, slug=None):
    formato = "docx" if ruta_origen.suffix.lower() == ".docx" else "pptx"
    # `slug` se puede forzar (p. ej. desde convertir_doc_legacy, donde ruta_origen
    # es un .docx temporal cuyo nombre no debe filtrarse a la carpeta de imágenes).
    slug = slug or slugify(ruta_origen.stem)
    media_rel = f"src/{slug}"  # carpeta propia por documento: evita que dos
    # conversiones en la misma carpeta se pisen los nombres image1.png, image2.png...
    shutil.rmtree(carpeta_salida / media_rel, ignore_errors=True)  # re-conversión limpia e idempotente
    ruta_md_temp = carpeta_salida / f".{slug}.tmp.md"

    resultado = subprocess.run(
        [
            "pandoc",
            str(ruta_origen),
            "-f",
            formato,
            "-t",
            "gfm",
            "--wrap=preserve",
            f"--extract-media={media_rel}",
            "-o",
            str(ruta_md_temp),
        ],
        cwd=carpeta_salida,
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"pandoc falló: {resultado.stderr.strip()}")

    texto = ruta_md_temp.read_text(encoding="utf-8")
    ruta_md_temp.unlink()

    # pandoc guarda las imágenes en <media_rel>/media/... (docx) o
    # <media_rel>/ppt/media/... (pptx), según el formato interno del archivo
    # de origen. Las subimos todas a <media_rel>/ directamente para una ruta
    # simple y uniforme sin importar cuántos niveles haya usado pandoc.
    carpeta_base = carpeta_salida / media_rel
    for carpeta_media_pandoc in list(carpeta_base.rglob("media")):
        if not carpeta_media_pandoc.is_dir():
            continue
        prefijo_original = carpeta_media_pandoc.relative_to(carpeta_salida).as_posix()
        for archivo in carpeta_media_pandoc.iterdir():
            destino = carpeta_base / archivo.name
            destino.unlink(missing_ok=True)
            archivo.rename(destino)
        texto = texto.replace(f"{prefijo_original}/", f"{media_rel}/")
        carpeta_media_pandoc.rmdir()
        padre = carpeta_media_pandoc.parent
        while padre != carpeta_base and padre.exists() and not any(padre.iterdir()):
            padre.rmdir()
            padre = padre.parent

    return texto


def convertir_doc_legacy(ruta_origen, carpeta_salida):
    """.doc (el formato binario antiguo de Word, previo a .docx) no lo lee pandoc
    directamente. Si hay Microsoft Word instalado, lo abrimos por COM, lo
    guardamos como .docx temporal, y de ahí seguimos el mismo camino que un
    .docx normal — mismo resultado, solo un paso previo de conversión."""
    try:
        import win32com.client
    except ImportError:
        raise RuntimeError(
            "no se pudo convertir .doc: instala pywin32 (pip install pywin32) y "
            "Microsoft Word, o resalva el archivo como .docx a mano ('Guardar como' en Word)"
        )

    slug = slugify(ruta_origen.stem)
    ruta_docx_temp = carpeta_salida / f".{slug}.tmp.docx"
    ruta_docx_temp.unlink(missing_ok=True)

    WD_FORMAT_DOCX = 12  # wdFormatXMLDocument
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(ruta_origen), ReadOnly=True)
        try:
            doc.SaveAs(str(ruta_docx_temp), FileFormat=WD_FORMAT_DOCX)
        finally:
            doc.Close(False)
    finally:
        word.Quit()

    try:
        return convertir_docx_pptx(ruta_docx_temp, carpeta_salida, slug=slug)
    finally:
        ruta_docx_temp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# PDF vía PyMuPDF: texto con jerarquía aproximada por tamaño de fuente + imágenes
# ---------------------------------------------------------------------------

def _nivel_encabezado(tamano, tamano_base, negrita):
    if tamano >= tamano_base * 1.6:
        return 2
    if tamano >= tamano_base * 1.25 or (negrita and tamano >= tamano_base * 1.1):
        return 3
    return 0


def convertir_pdf(ruta_origen, carpeta_salida):
    slug = slugify(ruta_origen.stem)
    carpeta_media = carpeta_salida / "src" / slug
    carpeta_media.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(ruta_origen)
    partes = []
    contador_imagen = 0

    for num_pagina, pagina in enumerate(doc, start=1):
        eventos = []  # (y0, tipo, contenido)

        datos = pagina.get_text("dict")
        tamanos = [
            span["size"]
            for bloque in datos["blocks"]
            if bloque.get("type") == 0
            for linea in bloque["lines"]
            for span in linea["spans"]
            if span["text"].strip()
        ]
        tamano_base = statistics.median(tamanos) if tamanos else 10

        y_anterior = None
        for bloque in datos["blocks"]:
            if bloque.get("type") != 0:
                continue
            for linea in bloque["lines"]:
                texto_linea = "".join(s["text"] for s in linea["spans"]).strip()
                if not texto_linea:
                    continue
                tamano = max(s["size"] for s in linea["spans"])
                negrita = any("bold" in s["font"].lower() for s in linea["spans"])
                y0 = linea["bbox"][1]
                nivel = _nivel_encabezado(tamano, tamano_base, negrita)
                salto_parrafo = y_anterior is not None and (y0 - y_anterior) > tamano * 1.8
                prefijo = "#" * nivel + " " if nivel else ""
                marca = "¶" if salto_parrafo and not nivel else ""
                eventos.append((y0, "texto", marca + prefijo + texto_linea))
                y_anterior = y0

        try:
            info_imagenes = pagina.get_image_info(xrefs=True)
        except Exception:
            info_imagenes = []
        for info in info_imagenes:
            xref = info.get("xref")
            if not xref:
                continue
            eventos.append((info["bbox"][1], "imagen", xref))

        eventos.sort(key=lambda e: e[0])

        lineas_pagina = [f"<!-- página {num_pagina} -->"]
        for _, tipo, contenido in eventos:
            if tipo == "texto":
                if contenido.startswith("¶"):
                    lineas_pagina.append("")
                    contenido = contenido[1:]
                lineas_pagina.append(contenido)
            else:
                try:
                    base_imagen = doc.extract_image(contenido)
                except Exception:
                    continue
                contador_imagen += 1
                nombre_imagen = f"image{contador_imagen}.{base_imagen['ext']}"
                (carpeta_media / nombre_imagen).write_bytes(base_imagen["image"])
                lineas_pagina.append("")
                lineas_pagina.append(f"![Imagen p.{num_pagina}](src/{slug}/{nombre_imagen})")
                lineas_pagina.append("")

        partes.append("\n".join(lineas_pagina))

    doc.close()
    return "\n\n---\n\n".join(partes) + "\n"


# ---------------------------------------------------------------------------
# TXT: se copia tal cual, no necesita conversión
# ---------------------------------------------------------------------------

def convertir_txt(ruta_origen, carpeta_salida):
    return ruta_origen.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

CONVERSORES = {
    ".docx": convertir_docx_pptx,
    ".pptx": convertir_docx_pptx,
    ".pdf": convertir_pdf,
    ".txt": convertir_txt,
    ".doc": convertir_doc_legacy,
}


def procesar_archivo(ruta_origen, cfg, avisar=print):
    carpeta_salida = ruta_origen.parent
    ruta_md = carpeta_salida / f"{ruta_origen.stem}.md"

    avisar(f"Extrayendo texto e imágenes de: {ruta_origen.name}")
    conversor = CONVERSORES[ruta_origen.suffix.lower()]
    cuerpo = conversor(ruta_origen, carpeta_salida)

    avisar("Describiendo imágenes con el modelo de visión de LM Studio...")
    cuerpo = insertar_descripciones(cuerpo, carpeta_salida, cfg, avisar=avisar)

    frontmatter = construir_frontmatter(carpeta_salida, ruta_origen.stem, origen=f"transcripción automática de {ruta_origen.name}")
    ruta_md.write_text(f"{frontmatter}\n# {ruta_origen.stem}\n\n{cuerpo}\n", encoding="utf-8")
    avisar(f"Creado: {ruta_md.relative_to(REPO_ROOT)}\n")
    return ruta_md


def procesar_ruta(ruta, cfg, forzar=False, avisar=print):
    if ruta.is_file():
        archivos = [ruta]
    else:
        archivos = sorted(
            p for p in ruta.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES_SOPORTADAS
        )

    procesados = []
    for archivo in archivos:
        if archivo.suffix.lower() not in EXTENSIONES_SOPORTADAS:
            avisar(f"Omitido (formato no soportado): {archivo.name}")
            continue
        ruta_md = archivo.parent / f"{archivo.stem}.md"
        if ruta_md.exists() and not forzar:
            avisar(f"Omitido (ya existe {ruta_md.name}, usa --forzar para re-convertir): {archivo.name}")
            continue
        try:
            procesados.append(procesar_archivo(archivo, cfg, avisar=avisar))
        except Exception as e:
            avisar(f"ERROR procesando {archivo.name}: {e}\n")
    return procesados


def main():
    if len(sys.argv) < 2:
        print('Uso: python transcriptor_documentos.py "<archivo o carpeta>" [--forzar]')
        sys.exit(1)

    ruta = Path(sys.argv[1]).resolve()
    forzar = "--forzar" in sys.argv[2:]

    if not ruta.exists():
        print(f"No existe: {ruta}")
        sys.exit(1)

    if shutil.which("pandoc") is None:
        print("No se encontró 'pandoc' en el PATH. Instálalo desde https://pandoc.org/installing.html")
        sys.exit(1)

    cfg = cargar_config()
    procesados = procesar_ruta(ruta, cfg, forzar=forzar)
    print(f"Listo. {len(procesados)} archivo(s) convertido(s).")


if __name__ == "__main__":
    main()
