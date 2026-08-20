"""
Mapa conceptual interactivo — Decreto 30 (MTT) / IMIV
--------------------------------------------------------
Aplicación Flask 100% server-side: toda la interactividad (navegar,
buscar, filtrar) ocurre mediante enlaces y formularios HTML normales
(GET), sin una sola línea de JavaScript. El "mapa conceptual" se
dibuja como un SVG estilo mapa de metro, generado en Python a partir
de data/decreto30.json.

Cómo correrla:
    pip install flask --break-system-packages   (o dentro de un venv)
    python app.py
    abrir http://127.0.0.1:5000

Cómo completar el contenido legal:
    Edita data/decreto30.json. Cada nodo tiene los campos:
    articulo, titulo, resumen, texto, casos_especiales, excepciones,
    relacionados (ids de otros nodos) y estado ("verificar" | "ok").
    No hay que tocar este archivo .py para agregar/editar artículos.
"""

from flask import Flask, render_template, request, abort
import json
import re
from pathlib import Path

APP_DIR = Path(__file__).parent
DATA_PATH = APP_DIR / "data" / "decreto30.json"

app = Flask(__name__)


# ---------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------

def cargar_datos():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def indexar(data):
    """Devuelve (nodos_por_id, lineas_por_id) para accesos rápidos."""
    nodos = {n["id"]: n for n in data["nodos"]}
    lineas = {l["id"]: l for l in data["lineas"]}
    return nodos, lineas


# ---------------------------------------------------------------------
# Mapeo de líneas (Título.Capítulo) -> categorías de IMIV a las que aplican
# ---------------------------------------------------------------------

CATEGORIAS_INFO = {
    "basico": {"nombre": "IMIV Básico", "color": "#2f5d50"},
    "intermedio": {"nombre": "IMIV Intermedio", "color": "#3d6fb4"},
    "mayor": {"nombre": "IMIV Mayor", "color": "#c1443c"},
}

TODAS = ["basico", "intermedio", "mayor"]

LINEA_A_CATEGORIAS = {
    "TICI": TODAS, "TICII": TODAS, "TICIII": TODAS,          # Título I: disposiciones generales
    "TIICI": ["basico"], "TIICII": ["basico"],               # Título II: IMIV Básico
    "TIVCI": TODAS,                                            # elaboración e ingreso (aplica a todas)
    "TIVCII": ["basico"],                                      # evaluación IMIV básicos
    "TIVCIII": ["intermedio", "mayor"],                        # evaluación intermedio/mayor
    "TIVCIV": TODAS, "TIVCV": TODAS, "TIVCVI": TODAS,          # loteos, modificaciones, permisos previos
}
# Título III completo (7 capítulos) es Intermedio y Mayor
for _c in ["I", "II", "III", "IV", "V", "VI", "VII"]:
    LINEA_A_CATEGORIAS[f"TIIIC{_c}"] = ["intermedio", "mayor"]


def categorias_de_linea(linea_id):
    return LINEA_A_CATEGORIAS.get(linea_id, TODAS)


def nodos_por_categoria(data, cat):
    return [n for n in data["nodos"] if cat in categorias_de_linea(n["linea"])]


# ---------------------------------------------------------------------
# Layout del mapa (coordenadas estilo "línea de metro")
# ---------------------------------------------------------------------

ROW_HEIGHT = 118
COL_WIDTH = 205
MARGIN_X = 230
MARGIN_Y = 80
LABEL_COL_X = 20
LABEL_MAX_CHARS = 40


def calcular_layout(data):
    """Asigna coordenadas (x, y) a cada nodo según su línea/orden."""
    lineas_orden = {l["id"]: i for i, l in enumerate(data["lineas"])}
    coords = {}
    for n in data["nodos"]:
        row = lineas_orden[n["linea"]]
        col = n["orden"]
        x = MARGIN_X + (col - 1) * COL_WIDTH
        y = MARGIN_Y + row * ROW_HEIGHT
        coords[n["id"]] = (x, y)
    return coords


def generar_svg(data, nodos, lineas, coords, resaltar=None, buscar_ids=None):
    """Genera el SVG completo del mapa como string, con <a> reales
    (enlaces HTML normales, sin onclick ni JS) para cada estación."""

    max_col = max(n["orden"] for n in data["nodos"])
    width = MARGIN_X + max_col * COL_WIDTH + 40
    height = MARGIN_Y + len(data["lineas"]) * ROW_HEIGHT + 40

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="Mapa conceptual del Decreto 30" class="mapa-svg">'
    ]

    # --- Líneas de fondo (rieles) + etiquetas de línea ---
    for linea in data["lineas"]:
        row = list(lineas.keys()).index(linea["id"])
        y = MARGIN_Y + row * ROW_HEIGHT
        nodos_linea = [n for n in data["nodos"] if n["linea"] == linea["id"]]
        if not nodos_linea:
            continue
        x_start = MARGIN_X
        x_end = MARGIN_X + (max(n["orden"] for n in nodos_linea) - 1) * COL_WIDTH
        svg_parts.append(
            f'<line x1="{x_start}" y1="{y}" x2="{x_end}" y2="{y}" '
            f'stroke="{linea["color"]}" stroke-width="6" stroke-linecap="round" opacity="0.55"/>'
        )
        svg_parts.append(
            f'<text x="{LABEL_COL_X}" y="{y - 34}" class="linea-label" fill="{linea["color"]}">'
            f'{_esc(_truncar(linea["nombre"], LABEL_MAX_CHARS))}'
            f'<title>{_esc(linea["nombre"])}</title></text>'
        )

    # --- Conexiones entre nodos relacionados (transbordos) ---
    dibujadas = set()
    for n in data["nodos"]:
        x1, y1 = coords[n["id"]]
        for rel_id in n.get("relacionados", []):
            if rel_id not in coords:
                continue
            key = tuple(sorted([n["id"], rel_id]))
            if key in dibujadas:
                continue
            dibujadas.add(key)
            x2, y2 = coords[rel_id]
            if n["linea"] == nodos[rel_id]["linea"]:
                continue  # ya conectado por el riel de su propia línea
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            svg_parts.append(
                f'<path d="M{x1},{y1} Q{mx},{my - 25} {x2},{y2}" '
                f'class="conexion" fill="none"/>'
            )

    # --- Estaciones (nodos) ---
    for n in data["nodos"]:
        x, y = coords[n["id"]]
        color = lineas[n["linea"]]["color"]
        es_resaltado = resaltar == n["id"]
        es_match = buscar_ids is not None and n["id"] in buscar_ids
        atenuado = buscar_ids is not None and n["id"] not in buscar_ids

        clases = ["estacion"]
        if es_resaltado:
            clases.append("estacion-activa")
        if es_match:
            clases.append("estacion-match")
        if atenuado:
            clases.append("estacion-atenuada")

        # zigzag: alterna la etiqueta arriba/abajo para reducir choques de texto.
        # La primera estación de cada línea siempre va hacia abajo, para no
        # chocar con el nombre de la línea (que se dibuja arriba, a la izquierda).
        if n["orden"] == 1:
            arriba = False
        else:
            arriba = n["orden"] % 2 == 0
        label_y = y - 20 if arriba else y + 34
        art_y = y + 34 if arriba else y - 20
        anchor_class = "estacion-label-arriba" if arriba else "estacion-label-abajo"

        radio = 13 if (es_resaltado or es_match) else 9
        svg_parts.append(
            f'<a href="/articulo/{n["id"]}{_qs()}">'
            f'<g class="{" ".join(clases)}">'
            f'<circle cx="{x}" cy="{y}" r="{radio}" fill="{color}" stroke="#fff" stroke-width="3"/>'
            f'<text x="{x}" y="{label_y}" class="estacion-label {anchor_class}">{_esc(_truncar(n["titulo"], 24))}</text>'
            f'<text x="{x}" y="{art_y}" class="estacion-articulo">{_esc(n["articulo"])}</text>'
            f'<title>{_esc(n["titulo"])}</title>'
            f'</g></a>'
        )

    svg_parts.append("</svg>")
    return "".join(svg_parts)


def _qs():
    """Conserva el término de búsqueda actual al navegar (sin JS: vía querystring)."""
    q = request.args.get("q", "").strip()
    return f"?q={q}" if q else ""


def _esc(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _truncar(s, n):
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


# ---------------------------------------------------------------------
# Formateo de texto largo en bloques legibles (párrafos vs. listas a) b) c)…)
# ---------------------------------------------------------------------

ITEM_RE = re.compile(
    r"^([a-hj-z]\)|i\)|ii\)|iii\)|iv\)|v\)|vi\)|vii\)|viii\)|ix\)|x\))\s*(.*)$"
)


def dividir_en_bloques(texto):
    bloques = []
    for ln in texto.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        m = ITEM_RE.match(ln)
        if m:
            bloques.append({"tipo": "item", "marca": m.group(1), "contenido": m.group(2)})
        else:
            bloques.append({"tipo": "parrafo", "contenido": ln})
    return bloques


app.jinja_env.filters["bloques"] = dividir_en_bloques


# ---------------------------------------------------------------------
# Análisis por tipo de proyecto (destino): cruza la clasificación de
# usos de suelo del art. 1.2.3 con los casos especiales del art. 3.6.12
# y con cualquier otra mención en el resto del decreto.
# ---------------------------------------------------------------------

TIPOS_PROYECTO = [
    {"slug": "vivienda", "nombre": "Vivienda (casas y departamentos)", "letra_123": "a",
     "keywords": ["vivienda", "habitacional", "departamentos"]},
    {"slug": "hogares_acogida", "nombre": "Hogares de acogida", "letra_123": "b",
     "keywords": ["hogares de acogida"]},
    {"slug": "hospedaje", "nombre": "Hospedaje y turismo (hoteles, hostales)", "letra_123": "c",
     "keywords": ["hospedaje", "hotel", "hostería"]},
    {"slug": "cientifico", "nombre": "Equipamiento científico", "letra_123": "d",
     "keywords": ["científico"]},
    {"slug": "comercio", "nombre": "Comercio", "letra_123": "e",
     "keywords": ["comercio", "comercial"]},
    {"slug": "culto_cultura", "nombre": "Culto y cultura", "letra_123": "f",
     "keywords": ["culto y cultura", "culto", "cultura"]},
    {"slug": "deporte", "nombre": "Deporte", "letra_123": "g",
     "keywords": ["deporte", "deportivo"]},
    {"slug": "educacion", "nombre": "Educación (colegios, jardines, universidades)", "letra_123": "h",
     "keywords": ["educación", "educacional", "educacionales"], "caso_especial_letra": "a"},
    {"slug": "esparcimiento", "nombre": "Esparcimiento", "letra_123": "i",
     "keywords": ["esparcimiento"]},
    {"slug": "salud", "nombre": "Salud (hospitales, clínicas, consultorios)", "letra_123": "j",
     "keywords": ["salud", "hospital", "consultorio"], "caso_especial_letra": "b"},
    {"slug": "seguridad", "nombre": "Seguridad (cuarteles, recintos militares/policiales)", "letra_123": "k",
     "keywords": ["seguridad", "cuartel", "militar", "policial", "gendarmería", "bomberos"]},
    {"slug": "servicios", "nombre": "Oficinas y servicios", "letra_123": "l",
     "keywords": ["equipamiento, clase servicios", "oficinas públicas"]},
    {"slug": "social", "nombre": "Equipamiento social", "letra_123": "m",
     "keywords": ["equipamiento social"]},
    {"slug": "industrial_bodegas", "nombre": "Industria y bodegas", "letra_123": "n",
     "keywords": ["industrial", "industria", "bodega", "bodegas", "bodegas industriales"]},
    {"slug": "infraestructura", "nombre": "Infraestructura (terminales, puertos, aeropuertos)", "letra_123": "o",
     "keywords": ["infraestructura", "terminal", "terminales", "puerto", "aeródromo", "aeropuerto"],
     "caso_especial_letra": "c"},
    {"slug": "espacio_publico_area_verde", "nombre": "Espacio público y áreas verdes", "letra_123": "p",
     "keywords": ["área verde", "áreas verdes", "espacio público"]},
]

LETRA_RE_123 = re.compile(r"\b([a-p])\)\s*Uso de suelo")


def extraer_usos_de_suelo(texto_123):
    """Divide el Art. 1.2.3 en sus literales a)…p), usando 'Uso de suelo'
    como ancla (evita el choque entre la letra 'i' y los numerales
    romanos i)/ii) que aparecen anidados dentro de algunos literales)."""
    matches = list(LETRA_RE_123.finditer(texto_123))
    bloques_por_letra = {}
    for idx, mobj in enumerate(matches):
        letra = mobj.group(1)
        inicio = mobj.start()
        fin = matches[idx + 1].start() if idx + 1 < len(matches) else len(texto_123)
        bloques_por_letra[letra] = texto_123[inicio:fin].strip()
    return bloques_por_letra


def extraer_item_por_letra(texto, letra):
    """Devuelve el contenido de un ítem 'a) …' / 'b) …' de nivel superior
    (usado para los literales del art. 3.6.12)."""
    for b in dividir_en_bloques(texto):
        if b["tipo"] == "item" and b["marca"] == f"{letra})":
            return b["contenido"]
    return None


def buscar_por_keywords(data, keywords, excluir_ids=()):
    """Búsqueda OR: cualquier nodo cuyo contenido mencione al menos una
    de las palabras clave (sin distinguir mayúsculas/acentos simples)."""
    kws = [k.lower() for k in keywords]
    resultados = []
    for n in data["nodos"]:
        if n["id"] in excluir_ids:
            continue
        campos = " ".join([
            n["titulo"], n["resumen"], n["texto"],
            " ".join(n.get("casos_especiales", [])),
            " ".join(n.get("excepciones", [])),
        ]).lower()
        if any(k in campos for k in kws):
            resultados.append(n)
    return resultados


# ---------------------------------------------------------------------
# Búsqueda (server-side, sin JS)
# ---------------------------------------------------------------------

def buscar(data, query, categoria=None):
    if not query and not categoria:
        return None
    q = query.lower().strip()
    resultados = []
    for n in data["nodos"]:
        if categoria and n["linea"] != categoria:
            continue
        campos = " ".join([
            n["articulo"], n["titulo"], n["resumen"], n["texto"],
            " ".join(n.get("casos_especiales", [])),
            " ".join(n.get("excepciones", [])),
        ]).lower()
        if not q or q in campos:
            resultados.append(n)
    return resultados


TITULO_NOMBRES = {
    "I": "Disposiciones generales",
    "II": "IMIV Básico",
    "III": "IMIV Intermedio y Mayor",
    "IV": "Evaluación de los IMIV",
}


def agrupar_lineas_por_titulo(lineas):
    grupos = []
    vistos = set()
    for l in lineas:
        t = l["titulo_num"]
        if t not in vistos:
            vistos.add(t)
            grupos.append({"titulo_num": t, "titulo_nombre": TITULO_NOMBRES.get(t, t), "lineas": []})
        for g in grupos:
            if g["titulo_num"] == t:
                g["lineas"].append(l)
                break
    return grupos


# ---------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------

@app.route("/")
def mapa():
    data = cargar_datos()
    nodos, lineas = indexar(data)
    coords = calcular_layout(data)

    q = request.args.get("q", "").strip()
    categoria = request.args.get("linea", "").strip() or None
    resultados = buscar(data, q, categoria) if (q or categoria) else None
    buscar_ids = {r["id"] for r in resultados} if resultados is not None else None

    svg = generar_svg(data, nodos, lineas, coords, buscar_ids=buscar_ids)

    # Conteo de artículos por categoría de IMIV, para las tarjetas de selección
    conteo_categorias = {
        cat: len(nodos_por_categoria(data, cat)) for cat in TODAS
    }

    conteo_por_linea = {}
    for n in data["nodos"]:
        conteo_por_linea[n["linea"]] = conteo_por_linea.get(n["linea"], 0) + 1
    grupos_tema = agrupar_lineas_por_titulo(data["lineas"])

    return render_template(
        "mapa.html",
        meta=data["meta"],
        lineas=data["lineas"],
        svg=svg,
        q=q,
        categoria=categoria,
        resultados=resultados,
        categorias_info=CATEGORIAS_INFO,
        conteo_categorias=conteo_categorias,
        grupos_tema=grupos_tema,
        conteo_por_linea=conteo_por_linea,
    )


@app.route("/categoria/<cat>")
def categoria_imiv(cat):
    if cat not in CATEGORIAS_INFO:
        abort(404)
    data = cargar_datos()
    nodos, lineas = indexar(data)

    nodos_cat = nodos_por_categoria(data, cat)
    ids_cat = {n["id"] for n in nodos_cat}

    # Agrupar por línea, conservando el orden de aparición en el decreto
    grupos = []
    vistos = set()
    for n in nodos_cat:
        lid = n["linea"]
        if lid not in vistos:
            vistos.add(lid)
            grupos.append({"linea": lineas[lid], "nodos": []})
        for g in grupos:
            if g["linea"]["id"] == lid:
                g["nodos"].append(n)
                break

    con_excepciones = [n for n in nodos_cat if n["excepciones"]]
    con_casos = [n for n in nodos_cat if n["casos_especiales"]]

    return render_template(
        "categoria.html",
        meta=data["meta"],
        cat=cat,
        info=CATEGORIAS_INFO[cat],
        categorias_info=CATEGORIAS_INFO,
        grupos=grupos,
        total=len(nodos_cat),
        con_excepciones=con_excepciones,
        con_casos=con_casos,
    )


@app.route("/linea/<linea_id>")
def linea_detalle(linea_id):
    data = cargar_datos()
    nodos, lineas = indexar(data)
    if linea_id not in lineas:
        abort(404)
    linea = lineas[linea_id]
    nodos_linea = [n for n in data["nodos"] if n["linea"] == linea_id]
    nodos_linea.sort(key=lambda n: n["orden"])

    return render_template(
        "linea.html",
        meta=data["meta"],
        linea=linea,
        nodos=nodos_linea,
        categorias_aplicables=[CATEGORIAS_INFO[c] for c in categorias_de_linea(linea_id)],
    )


@app.route("/tipos-proyecto")
def tipos_proyecto():
    data = cargar_datos()
    return render_template("tipos_proyecto.html", meta=data["meta"], tipos=TIPOS_PROYECTO)


@app.route("/tipo/<slug>")
def tipo_proyecto(slug):
    tipo = next((t for t in TIPOS_PROYECTO if t["slug"] == slug), None)
    if not tipo:
        abort(404)
    data = cargar_datos()
    nodos, lineas = indexar(data)

    nodo_123 = nodos.get("n1_2_3")
    nodo_3612 = nodos.get("n3_6_12")

    usos_de_suelo = extraer_usos_de_suelo(nodo_123["texto"]) if nodo_123 else {}
    bloque_123 = usos_de_suelo.get(tipo["letra_123"])
    tabla_rota = nodo_123 is not None and nodo_123.get("estado") == "verificar_tabla"

    caso_especial = None
    if tipo.get("caso_especial_letra") and nodo_3612:
        caso_especial = extraer_item_por_letra(nodo_3612["texto"], tipo["caso_especial_letra"])

    excluir = {"n1_2_3", "n3_6_12"}
    relacionados = buscar_por_keywords(data, tipo["keywords"], excluir_ids=excluir)
    relacionados.sort(key=lambda n: n["articulo"])

    return render_template(
        "tipo_proyecto.html",
        meta=data["meta"],
        tipo=tipo,
        bloque_123=bloque_123,
        tabla_rota=tabla_rota,
        nodo_123=nodo_123,
        caso_especial=caso_especial,
        nodo_3612=nodo_3612,
        relacionados=relacionados,
    )


@app.route("/articulo/<nodo_id>")
def articulo(nodo_id):
    data = cargar_datos()
    nodos, lineas = indexar(data)
    if nodo_id not in nodos:
        abort(404)
    nodo = nodos[nodo_id]
    linea = lineas[nodo["linea"]]
    relacionados = [nodos[r] for r in nodo.get("relacionados", []) if r in nodos]

    categorias_aplicables = [CATEGORIAS_INFO[c] for c in categorias_de_linea(nodo["linea"])]

    return render_template(
        "articulo.html",
        meta=data["meta"],
        nodo=nodo,
        linea=linea,
        relacionados=relacionados,
        q=request.args.get("q", ""),
        categorias_aplicables=categorias_aplicables,
    )


@app.errorhandler(404)
def no_encontrado(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)
