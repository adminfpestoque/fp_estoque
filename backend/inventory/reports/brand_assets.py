import math
from pathlib import Path

from django.conf import settings
from reportlab.graphics.shapes import Circle, Drawing, Path as GraphicPath, Polygon, Rect, String
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image


GOLD = HexColor("#F5B400")
BLACK = HexColor("#111111")


def _find_png_logo():
    candidates = [
        Path(settings.BASE_DIR).parent / "frontend" / "public" / "fp-logo.png",
        Path(settings.BASE_DIR) / "inventory" / "assets" / "fp-logo.png",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            ImageReader(str(path)).getSize()
            return path
        except Exception:
            continue
    return None


def _star_points(cx, cy, outer_radius, inner_radius):
    points = []
    for index in range(10):
        angle = math.radians(-90 + index * 36)
        radius = outer_radius if index % 2 == 0 else inner_radius
        points.extend([cx + math.cos(angle) * radius, cy + math.sin(angle) * radius])
    return points


def _leaf_points(cx, cy, side, scale):
    return [
        cx,
        cy,
        cx + side * 5 * scale,
        cy + 3 * scale,
        cx + side * 7 * scale,
        cy + 7 * scale,
        cx + side * 2 * scale,
        cy + 5 * scale,
    ]


def _vector_logo(size):
    scale = size / 64
    drawing = Drawing(size, size)

    drawing.add(Circle(32 * scale, 32 * scale, 29 * scale, fillColor=BLACK, strokeColor=GOLD, strokeWidth=2.3 * scale))
    drawing.add(Circle(32 * scale, 32 * scale, 25.5 * scale, fillColor=None, strokeColor=white, strokeWidth=1.2 * scale))

    left_stem = GraphicPath()
    left_stem.moveTo(13 * scale, 11 * scale)
    left_stem.curveTo(4 * scale, 21 * scale, 4 * scale, 43 * scale, 15 * scale, 54 * scale)
    left_stem.strokeColor = GOLD
    left_stem.strokeWidth = 1.5 * scale
    left_stem.fillColor = None
    drawing.add(left_stem)

    right_stem = GraphicPath()
    right_stem.moveTo(51 * scale, 11 * scale)
    right_stem.curveTo(60 * scale, 21 * scale, 60 * scale, 43 * scale, 49 * scale, 54 * scale)
    right_stem.strokeColor = GOLD
    right_stem.strokeWidth = 1.5 * scale
    right_stem.fillColor = None
    drawing.add(right_stem)

    for index, y in enumerate((14, 20, 26, 32, 38, 44, 50)):
        offset = index * 0.55
        drawing.add(Polygon(_leaf_points((12 - offset) * scale, y * scale, -1, scale), fillColor=GOLD, strokeColor=None))
        drawing.add(Polygon(_leaf_points((52 + offset) * scale, y * scale, 1, scale), fillColor=GOLD, strokeColor=None))

    drawing.add(String(32 * scale, 50 * scale, "2024", fontName="Helvetica-Bold", fontSize=6.3 * scale, fillColor=white, textAnchor="middle"))

    for x in (25, 32, 39):
        drawing.add(Polygon(_star_points(x * scale, 43.5 * scale, 3.3 * scale, 1.45 * scale), fillColor=GOLD, strokeColor=None))

    drawing.add(String(32 * scale, 27 * scale, "FP", fontName="Times-Bold", fontSize=21 * scale, fillColor=white, textAnchor="middle"))
    drawing.add(String(32 * scale, 20 * scale, "DEPÓSITO DE BEBIDAS", fontName="Helvetica-Bold", fontSize=4.5 * scale, fillColor=white, textAnchor="middle"))

    drawing.add(Circle(18 * scale, 10.5 * scale, 3.2 * scale, fillColor=None, strokeColor=GOLD, strokeWidth=1.5 * scale))
    drawing.add(Circle(46 * scale, 10.5 * scale, 3.2 * scale, fillColor=None, strokeColor=GOLD, strokeWidth=1.5 * scale))
    drawing.add(Rect(19 * scale, 5 * scale, 10 * scale, 12 * scale, rx=1.3 * scale, ry=1.3 * scale, fillColor=GOLD, strokeColor=white, strokeWidth=1.1 * scale))
    drawing.add(Rect(35 * scale, 5 * scale, 10 * scale, 12 * scale, rx=1.3 * scale, ry=1.3 * scale, fillColor=GOLD, strokeColor=white, strokeWidth=1.1 * scale))
    drawing.add(Rect(19 * scale, 14 * scale, 10 * scale, 3 * scale, rx=1 * scale, ry=1 * scale, fillColor=white, strokeColor=white))
    drawing.add(Rect(35 * scale, 14 * scale, 10 * scale, 3 * scale, rx=1 * scale, ry=1 * scale, fillColor=white, strokeColor=white))

    return drawing


def fp_logo_flowable(size):
    png_logo = _find_png_logo()
    if png_logo:
        return Image(str(png_logo), width=size, height=size)
    return _vector_logo(size)
