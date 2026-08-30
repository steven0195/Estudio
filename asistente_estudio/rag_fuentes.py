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


def indexar_fuentes(carpeta_fuentes, cfg, avisar=print):
    """Devuelve una lista de fragmentos con su embedding ya calculado (de caché
    si nada cambió, o vectorizando de nuevo si es la primera vez o los .md
    de la carpeta cambiaron)."""
    if not carpeta_fuentes.exists():
        return []

    archivos = sorted(carpeta_fuentes.glob("*.md"))
    fragmentos = []
    for archivo in archivos:
        texto = quitar_frontmatter(archivo.read_text(encoding="utf-8"))
        fragmentos.extend(dividir_en_fragmentos(archivo.name, texto))

    if not fragmentos:
        return []

    ruta_cache = carpeta_fuentes / ".rag_cache.json"
    huella = _huella_fragmentos(fragmentos)
    if ruta_cache.exists():
        try:
            cache = json.loads(ruta_cache.read_text(encoding="utf-8"))
            if cache.get("huella") == huella and len(cache.get("embeddings", [])) == len(fragmentos):
                for frag, emb in zip(fragmentos, cache["embeddings"]):
                    frag["embedding"] = emb
                avisar(f"Índice de fuentes/ cargado de caché ({len(fragmentos)} fragmentos, {len(archivos)} archivo(s)).")
                return fragmentos
        except (json.JSONDecodeError, KeyError):
            pass

    avisar(f"Vectorizando {len(fragmentos)} fragmentos de {len(archivos)} archivo(s) en fuentes/ (se cachea para la próxima vez)...")
    embeddings = obtener_embeddings([f["texto"] for f in fragmentos], cfg)
    for frag, emb in zip(fragmentos, embeddings):
        frag["embedding"] = emb
    try:
        ruta_cache.write_text(json.dumps({"huella": huella, "embeddings": embeddings}), encoding="utf-8")
    except OSError:
        pass
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
