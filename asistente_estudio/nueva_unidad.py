"""
Crea el esqueleto de una unidad de curso (o tema de Desarrollo) nueva: las
carpetas `apuntes/`, `fuentes/`, `actividades/`, con un `apuntes.md` en
blanco ya con el frontmatter correcto según dónde quede ubicada — el mismo
molde que ya usa el resto del repo, para no tener que armarlo a mano cada
vez que arranca una unidad.

Sin argumentos, navega el repo por menú numerado — área → curso/tema —
igual que el resto de las herramientas, en vez de tener que escribir la
ruta completa a mano. Si el curso elegido ya tiene unidades ("Unidad 1 - ...",
"Unidad 2 - ..."), detecta el siguiente número automáticamente y solo te
pide el nombre que va después del prefijo: si ya existe "Unidad 1 - Aspectos
generales de la formulacion", la próxima queda ofrecida como "Unidad 2 - ",
tú solo escribes lo que sigue.

Si la ruta resulta ser una "Unidad N - Tema" dentro de un curso:
  - Si el curso todavía no existe (ni su `curso.md`), lo crea también.
  - Si el curso ya existe y su `curso.md` tiene una sección "## Unidades",
    agrega ahí el enlace a la unidad nueva sin tocar el resto del archivo.
  - Si ya existe una unidad con ese nombre, no se toca nada que ya esté
    (es seguro volver a correrlo para completar piezas que falten).

No trae contenido real — es solo el molde vacío, igual que los demás
`apuntes.md` en blanco del repo. Sin dependencias externas (solo librería
estándar de Python).

Uso (desde la raíz del repo):
  python asistente_estudio/nueva_unidad.py
      Navega por menú: área → curso/tema → (si aplica) nombre de la unidad
      siguiente, con el prefijo "Unidad N - " ya puesto.

  python asistente_estudio/nueva_unidad.py "<ruta completa de la nueva unidad o tema>"
      Modo directo, sin menús — igual que antes.

Ejemplos:
  python asistente_estudio/nueva_unidad.py
  python asistente_estudio/nueva_unidad.py "Administracion de empresas/2026-1 T1 Gerencia del servicio/Unidad 3 - Herramientas para gerenciar el servicio"
  python asistente_estudio/nueva_unidad.py "Desarrollo/Docker"
"""

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent  # este script vive en asistente_estudio/, un nivel bajo la raíz
PATRON_UNIDAD = re.compile(r"^Unidad (\d+) - (.+)$")
PATRON_CURSO = re.compile(r"^(\d{4}-\d T\d) (.+)$")

NUEVO = object()


# ---------------------------------------------------------------------------
# Navegación por menú (área -> curso/tema -> nombre de la unidad siguiente)
# ---------------------------------------------------------------------------

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


def elegir_de_lista(titulo, opciones, mostrar=lambda o: o.name):
    print(f"\n{titulo}")
    for i, op in enumerate(opciones, 1):
        print(f"  {i}. {mostrar(op)}")
    print("  0. Cancelar")
    while True:
        raw = input("Elige un número: ").strip()
        if raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(opciones):
            return opciones[int(raw) - 1]
        print("  Opción inválida, intenta de nuevo.")


def siguiente_numero_unidad(carpeta_curso):
    numeros = []
    for p in listar_subcarpetas(carpeta_curso):
        m = PATRON_UNIDAD.match(p.name)
        if m:
            numeros.append(int(m.group(1)))
    return max(numeros, default=0) + 1


def elegir_contenedor():
    """Navega Área -> Curso/Tema (existente o nuevo). Devuelve la carpeta elegida, o None si se cancela."""
    areas = [a for a in listar_subcarpetas(REPO_ROOT) if a.name != SCRIPT_DIR.name]
    while True:
        area = elegir_de_lista("¿En qué área quieres crear la unidad o tema?", areas)
        if area is None:
            return None

        opciones = listar_subcarpetas(area) + [NUEVO]
        seleccion = elegir_de_lista(
            f"¿En qué curso/tema de '{area.name}'?",
            opciones,
            mostrar=lambda o: "+ Crear un curso/tema nuevo aquí" if o is NUEVO else o.name,
        )
        if seleccion is None:
            continue  # vuelve a elegir área
        if seleccion is NUEVO:
            print(
                "\nNombre de la carpeta nueva. Si es un curso formal, usa el formato "
                "'AAAA-N TN Nombre del curso' (p. ej. '2026-1 T1 Nombre del curso') "
                "para que quede numerada por unidades; si es un tema libre, cualquier nombre sirve."
            )
            nombre = input("Nombre: ").strip()
            if not nombre:
                continue
            return area / nombre
        return seleccion


def resolver_ruta_final(contenedor):
    """Si `contenedor` es un curso (nombre con patrón de periodo), pide solo el
    nombre de la unidad y le antepone el prefijo "Unidad N - " ya calculado.
    Si no, `contenedor` mismo es la carpeta final (temas tipo Desarrollo/Tema,
    sin subdivisión en unidades)."""
    if not PATRON_CURSO.match(contenedor.name):
        return contenedor

    siguiente = siguiente_numero_unidad(contenedor)
    prefijo = f"Unidad {siguiente} - "
    print(f"\nPróxima unidad de '{contenedor.name}': {prefijo}...")
    tema = input(f"Nombre de la unidad (lo que va después de '{prefijo}'): ").strip()
    if not tema:
        return None
    return contenedor / f"{prefijo}{tema}"


# ---------------------------------------------------------------------------
# Frontmatter y creación del esqueleto
# ---------------------------------------------------------------------------

def construir_frontmatter(campos):
    lineas = ["---"]
    for clave, valor in campos.items():
        if isinstance(valor, str) and (" " in valor or ":" in valor):
            lineas.append(f'{clave}: "{valor}"')
        else:
            lineas.append(f"{clave}: {valor}")
    lineas.append("tags: []")
    lineas.append("---\n")
    return "\n".join(lineas)


def metadatos_desde_ruta(partes):
    """Misma lógica que metadatos_desde_ruta() en nucleo.py — duplicada aquí a
    propósito para que este script siga siendo un archivo suelto, sin depender
    de la estructura interna del resto de la carpeta ni de tener las demás
    dependencias (pymupdf, requests...) instaladas para algo tan simple."""
    meta = {"area": partes[0] if partes else None}
    for parte in partes:
        m = PATRON_CURSO.match(parte)
        if m:
            meta["periodo"], meta["curso"] = m.group(1), m.group(2)
        mu = PATRON_UNIDAD.match(parte)
        if mu:
            meta["unidad"], meta["tema"] = mu.group(1), mu.group(2).replace("_", " ")
    if "curso" not in meta and len(partes) > 1:
        meta["tema_area"] = partes[1]
    return meta


def crear_apuntes_md(carpeta_unidad, meta):
    campos = {"tipo": "apunte", "area": meta["area"]}
    if "curso" in meta:
        campos["curso"] = meta["curso"]
        campos["periodo"] = meta["periodo"]
    if "tema_area" in meta:
        campos["tema_area"] = meta["tema_area"]
    if "unidad" in meta:
        campos["unidad"] = meta["unidad"]
        campos["tema"] = meta["tema"]
    campos["titulo"] = "Apuntes"

    titulo_visible = meta.get("tema") or meta.get("tema_area") or carpeta_unidad.name
    ruta = carpeta_unidad / "apuntes" / "apuntes.md"
    if ruta.exists():
        print(f"  Ya existe, no se toca: {ruta.relative_to(REPO_ROOT)}")
        return
    contenido = (
        construir_frontmatter(campos) + f"\n# {titulo_visible}\n\n"
        "> Borrador vacío. Aquí van tus apuntes de síntesis de esta unidad "
        "(no el material crudo, eso vive en `../fuentes/`).\n"
    )
    ruta.write_text(contenido, encoding="utf-8")
    print(f"  Creado: {ruta.relative_to(REPO_ROOT)}")


def crear_curso_md(carpeta_curso, meta, nombre_unidad_nueva):
    campos = {
        "tipo": "curso",
        "periodo": meta["periodo"],
        "curso": meta["curso"],
        "docente": "",
        "fecha_inicio": "",
        "fecha_fin": "",
    }
    contenido = (
        construir_frontmatter(campos) + f"\n# {meta['curso']}\n\n"
        "> Ficha del curso. Completa docente, fechas y temario a medida que avance el periodo.\n\n"
        "## Unidades\n\n"
        f"- [{nombre_unidad_nueva}](<{nombre_unidad_nueva}>)\n"
    )
    ruta = carpeta_curso / "curso.md"
    ruta.write_text(contenido, encoding="utf-8")
    print(f"  Creado: {ruta.relative_to(REPO_ROOT)}")


def enlazar_en_curso_md(ruta_curso_md, nombre_unidad):
    texto = ruta_curso_md.read_text(encoding="utf-8")
    enlace = f"- [{nombre_unidad}](<{nombre_unidad}>)"
    if f"<{nombre_unidad}>" in texto:
        print("  curso.md ya enlaza esta unidad, no se toca.")
        return

    m = re.search(r"^## Unidades[ \t]*$", texto, re.MULTILINE)
    if not m:
        print("  curso.md no tiene una sección '## Unidades' — agrega el enlace a mano.")
        return

    # se inserta después del último renglón de la lista ya existente bajo ese
    # encabezado (líneas en blanco o que empiecen con "- "), sin depender de
    # dónde esté el próximo encabezado (el archivo puede tener contenido
    # ajeno a nuestra plantilla agregado después, y no hay que tocarlo)
    resto = texto[m.end():].split("\n")
    fin_lista = 0
    for i, linea in enumerate(resto):
        if linea.strip() == "" or linea.lstrip().startswith("- "):
            fin_lista = i + 1
        else:
            break
    offset = m.end() + sum(len(linea) + 1 for linea in resto[:fin_lista])

    antes = texto[:offset].rstrip("\n")
    ultima_no_vacia = next((l for l in reversed(antes.splitlines()) if l.strip()), "")
    separador = "\n" if ultima_no_vacia.lstrip().startswith("- ") else "\n\n"
    nuevo_texto = antes + separador + enlace + "\n" + texto[offset:].lstrip("\n")
    ruta_curso_md.write_text(nuevo_texto, encoding="utf-8")
    print(f"  Enlazada en: {ruta_curso_md.relative_to(REPO_ROOT)}")


def crear_esqueleto(ruta_completa):
    try:
        partes = ruta_completa.relative_to(REPO_ROOT).parts
    except ValueError:
        print(f"La ruta debe estar dentro del repo ({REPO_ROOT}).")
        sys.exit(1)
    if not partes:
        print("Ruta vacía.")
        sys.exit(1)

    meta = metadatos_desde_ruta(partes)
    es_unidad = PATRON_UNIDAD.match(partes[-1]) is not None

    print(f"\nCreando esqueleto en: {ruta_completa.relative_to(REPO_ROOT)}")

    if es_unidad and "curso" in meta:
        carpeta_curso = ruta_completa.parent
        ruta_curso_md = carpeta_curso / "curso.md"
        if not ruta_curso_md.exists():
            carpeta_curso.mkdir(parents=True, exist_ok=True)
            crear_curso_md(carpeta_curso, meta, nombre_unidad_nueva=ruta_completa.name)
        else:
            enlazar_en_curso_md(ruta_curso_md, ruta_completa.name)

    for sub in ("apuntes", "fuentes", "actividades"):
        (ruta_completa / sub).mkdir(parents=True, exist_ok=True)
    print("  Creadas: apuntes/, fuentes/, actividades/")

    crear_apuntes_md(ruta_completa, meta)

    print("\nListo.")


def ruta_desde_argumento(arg):
    ruta_arg = Path(arg)
    ruta_completa = ruta_arg if ruta_arg.is_absolute() else REPO_ROOT / ruta_arg
    return Path(str(ruta_completa).rstrip("/\\"))


def main():
    if len(sys.argv) >= 2:
        crear_esqueleto(ruta_desde_argumento(sys.argv[1]))
        return

    contenedor = elegir_contenedor()
    if contenedor is None:
        print("Cancelado.")
        return

    ruta_completa = resolver_ruta_final(contenedor)
    if ruta_completa is None:
        print("Cancelado.")
        return

    crear_esqueleto(ruta_completa)


if __name__ == "__main__":
    main()
