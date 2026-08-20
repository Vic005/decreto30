# Mapa IMIV — Decreto 30 (Ministerio de Transportes, Chile)

App web local para explorar el Decreto 30 (reglamento del IMIV) como un
mapa conceptual estilo "línea de metro": cada línea de color es un tema
del decreto (clasificación, procedimiento, mitigaciones, casos
especiales, etc.) y cada estación es un artículo o punto específico,
con resumen, texto, casos especiales, excepciones y artículos
relacionados a un clic.

**Sin JavaScript.** Todo — el mapa, la búsqueda, la navegación — se
genera en el servidor (Flask) y funciona con enlaces y formularios
HTML normales.

## Cómo correrla

```bash
cd imiv-app
python3 -m venv venv && source venv/bin/activate   # opcional pero recomendado
pip install -r requirements.txt
python app.py
```

Luego abre `http://127.0.0.1:5000` en el navegador.

## Estructura

```
imiv-app/
├── app.py                  # Flask: rutas, búsqueda, generación del SVG del mapa
├── data/decreto30.json     # TODO el contenido legal vive aquí
├── templates/              # HTML (Jinja2)
├── static/style.css        # Estilos
└── requirements.txt
```

## Cómo completar el contenido con el texto oficial

El archivo `data/decreto30.json` es lo único que necesitas editar para
que el mapa quede completo y preciso — no hay que tocar Python ni HTML.

Cada artículo/punto es un objeto así:

```json
{
  "id": "n5",
  "linea": "L2",
  "orden": 1,
  "articulo": "Art. 12°, inciso 3°",
  "titulo": "IMIV Básico",
  "resumen": "Una frase que resume el punto.",
  "texto": "Texto exacto (o cita fiel) del artículo/inciso.",
  "casos_especiales": ["Situación especial 1", "Situación especial 2"],
  "excepciones": ["Excepción 1"],
  "relacionados": ["n2", "n6"],
  "estado": "ok"
}
```

- `linea`: a qué categoría temática pertenece (ver el arreglo `lineas`
  al inicio del JSON — puedes agregar líneas nuevas si el decreto tiene
  más temas de los que ya modelé).
- `orden`: posición dentro de esa línea en el mapa (1, 2, 3…).
- `relacionados`: ids de otros nodos con los que se conecta (para que
  aparezca el enlace punteado en el mapa entre líneas distintas).
- `estado`: usa `"verificar"` mientras el contenido sea provisorio, y
  cámbialo a `"ok"` cuando ya esté contrastado con el texto oficial —
  así el aviso amarillo desaparece automáticamente de la página del
  artículo.

Para agregar un artículo nuevo, solo agrega un objeto más al arreglo
`nodos`. La app lo va a mostrar automáticamente en el mapa y en el
buscador, sin que tengas que tocar nada más.

## Importante

El dataset actual (`decreto30.json`) fue generado a partir del **texto
oficial completo** del Decreto 30 (versión consolidada a 07-12-2022,
extraída del PDF de LeyChile), y contiene los **94 artículos**
(1.1.1 a 4.6.9, más el artículo transitorio) organizados en 18 líneas
temáticas (una por cada Título/Capítulo real del decreto).

- Los **artículos relacionados** se detectaron automáticamente
  buscando referencias cruzadas dentro del propio texto (ej. "conforme
  al artículo 3.2.2 de este reglamento").
- Los campos **"casos especiales"** y **"excepciones"** se completaron
  con oraciones literales del propio artículo que contienen palabras
  clave como "exento", "excepto", "loteo o condominio tipo B", etc.
  Es una detección heurística — puede que falten casos o que algunos
  no sean relevantes; el texto completo del artículo siempre está
  disponible para revisar el contexto real.
- **3 artículos** (`1.2.3`, `1.3.2` y `3.3.7`) contienen tablas o
  cuadros de datos en el PDF original que no se lograron extraer
  correctamente (aparecen como puntos sueltos). Estos quedan marcados
  con `"estado": "verificar_tabla"` y muestran un aviso en la app —
  para esos casos, revisa la tabla directamente en el PDF oficial.
- El decreto puede haber sido modificado después de la fecha de esta
  versión consolidada. Antes de usar esta herramienta para un IMIV
  real, verifica que no haya cambios posteriores en
  [LeyChile](https://www.bcn.cl/leychile/navegar?idNorma=1131679).
