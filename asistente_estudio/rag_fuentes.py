"""
RAG ligero sobre carpetas fuentes/.

Parte los .md de una carpeta en fragmentos, los vectoriza con el modelo de
embeddings de LM Studio, y permite recuperar los fragmentos más relevantes
para una consulta por similitud de coseno. Sin base de datos vectorial
externa (chromadb, etc.) — con carpetas fuentes/ del tamaño de una unidad
de curso, una lista en memoria + numpy es más que suficiente.

Los embeddings se cachean en disco (`.rag_cache.json`, dentro de la propia
carpeta fuentes/) por huella de contenido, así que solo se vectoriza de
verdad la primera vez o cuando cambian los documentos.

Pensado para reutilizarse desde cualquier herramienta que necesite
"buscar rápido en las fuentes de una unidad" (solucionador_actividades.py,
y más adelante el ayudante de examen).
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import requests

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from nucleo import quitar_frontmatter  # noqa: E402

TAMANO_FRAGMENTO = 1500  # caracteres
SOLAPE = 200


def dividir_en_fragmentos(nombre_archivo, texto):
    """Corta primero por encabezados (fragmentos con sentido temático); si una
    sección igual queda muy larga, la subdivide por tamaño con solape."""
    partes = re.split(r"(?=^#{1,6}[ \t]+.+$)", texto, flags=re.MULTILINE)
    fragmentos = []
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        if len(parte) <= TAMANO_FRAGMENTO:
            fragmentos.append(parte)
            continue
        inicio = 0
        while inicio < len(parte):
            fragmentos.append(parte[inicio:inicio + TAMANO_FRAGMENTO])
            if inicio + TAMANO_FRAGMENTO >= len(parte):
                break
            inicio += TAMANO_FRAGMENTO - SOLAPE
    return [{"archivo": nombre_archivo, "texto": f} for f in fragmentos]


def obtener_embeddings(textos, cfg):
    if not textos:
        return []
    modelo = cfg.get("lmstudio_model_embeddings", "text-embedding-nomic-embed-text-v1.5")
    payload = {"model": modelo, "input": textos}
    resp = requests.post(f"{cfg['lmstudio_base_url']}/embeddings", json=payload, timeout=180)
    resp.raise_for_status()
    return [d["embedding"] for d in resp.json()["data"]]


def _huella_fragmentos(fragmentos):
    contenido = "\x00".join(f["archivo"] + "\x01" + f["texto"] for f in fragmentos)
    return hashlib.md5(contenido.encode("utf-8")).hexdigest()


def _vectorizar_con_cache(fragmentos, ruta_cache, cfg, avisar, descripcion):
    """Le asigna a cada fragmento su `embedding` (clave "embedding"), de
    caché si `ruta_cache` existe y coincide en huella y cantidad, o
    vectorizando de nuevo si no. Devuelve la misma lista, ya completa —
    cualquier fragmento que pase por aquí queda con su embedding asignado,
    nunca a medias."""
    if not fragmentos:
        return fragmentos

    huella = _huella_fragmentos(fragmentos)
    if ruta_cache.exists():
        try:
            cache = json.loads(ruta_cache.read_text(encoding="utf-8"))
            if cache.get("huella") == huella and len(cache.get("embeddings", [])) == len(fragmentos):
                for frag, emb in zip(fragmentos, cache["embeddings"]):
                    frag["embedding"] = emb
                avisar(f"  Índice de {descripcion} cargado de caché ({len(fragmentos)} fragmentos).")
                return fragmentos
        except (json.JSONDecodeError, KeyError):
            pass

    avisar(f"  Vectorizando {len(fragmentos)} fragmentos de {descripcion} (se cachea para la próxima vez)...")
    embeddings = obtener_embeddings([f["texto"] for f in fragmentos], cfg)
    for frag, emb in zip(fragmentos, embeddings):
        frag["embedding"] = emb
    try:
        ruta_cache.write_text(json.dumps({"huella": huella, "embeddings": embeddings}), encoding="utf-8")
    except OSError:
        pass
    return fragmentos


def indexar_fuentes(carpeta_fuentes, cfg, avisar=print, raiz_etiquetas=None):
    """Devuelve una lista de fragmentos con su embedding ya calculado (de caché
    si nada cambió, o vectorizando de nuevo si es la primera vez o los .md
    de la carpeta cambiaron).

    `raiz_etiquetas`, si se da, hace que cada fragmento se etiquete con su
    ruta relativa a esa raíz (p. ej. "Unidad 2 - .../fuentes/archivo.md") en
    vez de solo el nombre del archivo — útil cuando se combinan fragmentos de
    varias carpetas (varias unidades) y archivos de distintas unidades
    podrían llamarse igual (p. ej. "apuntes.md" en cada unidad)."""
    if not carpeta_fuentes.exists():
        return []

    archivos = sorted(carpeta_fuentes.glob("*.md"))
    fragmentos = []
    for archivo in archivos:
        # .as_posix(): siempre "/" como separador, incluso en Windows (donde
        # relative_to() por defecto usa "\") — así el resto del código puede
        # comparar/filtrar estas etiquetas por prefijo sin depender del SO.
        etiqueta = archivo.relative_to(raiz_etiquetas).as_posix() if raiz_etiquetas else archivo.name
        texto = quitar_frontmatter(archivo.read_text(encoding="utf-8"))
        fragmentos.extend(dividir_en_fragmentos(etiqueta, texto))

    if not fragmentos:
        return []

    ruta_cache = carpeta_fuentes / ".rag_cache.json"
    descripcion = f"{carpeta_fuentes.name}/ ({len(archivos)} archivo(s))"
    return _vectorizar_con_cache(fragmentos, ruta_cache, cfg, avisar, descripcion)


def indexar_curso(carpeta_curso, cfg, avisar=print):
    """Vectoriza TODO el material de referencia de un curso completo, no solo
    el de una unidad: `curso.md` (temario y notas generales) más `fuentes/` y
    `apuntes/` de CADA unidad (`<carpeta_curso>/Unidad N - Tema/...`).

    Reutiliza indexar_fuentes()/_vectorizar_con_cache() por carpeta (y para
    curso.md), así que cada carpeta mantiene su propio archivo de caché y
    solo se re-vectoriza lo que de verdad cambió de una corrida a la
    siguiente — el costo de indexar el curso completo se paga una vez (puede
    tardar, sobre todo la primera corrida) y las siguientes actividades de
    ese mismo curso reutilizan el caché."""
    fragmentos = []

    curso_md = carpeta_curso / "curso.md"
    if curso_md.exists():
        texto = quitar_frontmatter(curso_md.read_text(encoding="utf-8"))
        fragmentos_curso = dividir_en_fragmentos("curso.md", texto)
        ruta_cache = carpeta_curso / ".rag_cache_curso.json"
        fragmentos.extend(_vectorizar_con_cache(fragmentos_curso, ruta_cache, cfg, avisar, "curso.md"))

    carpetas_material = sorted(
        carpeta
        for patron in ("fuentes", "apuntes")
        for carpeta in carpeta_curso.glob(f"*/{patron}")
        if carpeta.is_dir()
    )
    for carpeta in carpetas_material:
        fragmentos.extend(indexar_fuentes(carpeta, cfg, avisar=avisar, raiz_etiquetas=carpeta_curso))

    return fragmentos


def buscar_relevantes(consulta, fragmentos, cfg, top_k=5):
    """Los top_k fragmentos más parecidos a `consulta` por similitud de coseno,
    como lista de (fragmento, similitud) ordenada de más a menos relevante."""
    if not fragmentos:
        return []
    consulta_emb = np.array(obtener_embeddings([consulta], cfg)[0])
    matriz = np.array([f["embedding"] for f in fragmentos])
    normas = np.linalg.norm(matriz, axis=1) * np.linalg.norm(consulta_emb)
    normas[normas == 0] = 1e-9
    similitudes = (matriz @ consulta_emb) / normas
    indices = np.argsort(-similitudes)[:top_k]
    return [(fragmentos[i], float(similitudes[i])) for i in indices]
