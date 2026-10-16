import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app.modules.essays import imaging


def _page_photo(angle: float = 0.0) -> np.ndarray:
    """Folha branca com linhas de texto sobre fundo escuro, levemente girada."""
    bg = np.full((1400, 1100, 3), 40, np.uint8)
    page = np.full((1000, 700, 3), 245, np.uint8)
    for y in range(80, 950, 40):
        cv2.line(page, (40, y), (660, y), (60, 60, 60), 3)
    matrix = cv2.getRotationMatrix2D((350, 500), angle, 1.0)
    rotated = cv2.warpAffine(page, matrix, (700, 1000), borderValue=(40, 40, 40))
    bg[200:1200, 200:900] = rotated
    return bg


def _jpeg(img: np.ndarray, exif_orientation: int | None = None) -> bytes:
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    buf = io.BytesIO()
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        pil.save(buf, "JPEG", exif=exif)
    else:
        pil.save(buf, "JPEG")
    return buf.getvalue()


def test_recorta_a_folha():
    result = imaging.preprocess(_jpeg(_page_photo()))
    assert result.cropped
    # a folha tem 700x1000: o recorte deve ficar perto disso
    assert abs(result.width - 700) < 60 and abs(result.height - 1000) < 60
    out = cv2.imdecode(np.frombuffer(result.data, np.uint8), cv2.IMREAD_COLOR)
    assert out.mean() > 150  # sem o fundo escuro


def test_corrige_inclinacao():
    img = np.full((1000, 1000, 3), 245, np.uint8)
    for y in range(100, 900, 50):
        cv2.line(img, (100, y), (900, y), (50, 50, 50), 3)
    tilted = cv2.warpAffine(
        img,
        cv2.getRotationMatrix2D((500, 500), -4, 1.0),
        (1000, 1000),
        borderValue=(245, 245, 245),
    )
    assert imaging.estimate_skew(tilted) == pytest.approx(4, abs=0.6)
    fixed = imaging.rotate(tilted, imaging.estimate_skew(tilted))
    assert abs(imaging.estimate_skew(fixed)) < 0.6


def test_aplica_orientacao_exif():
    img = np.full((300, 600, 3), 200, np.uint8)  # paisagem
    loaded = imaging.load_image(_jpeg(img, exif_orientation=6))  # girada 90°
    assert loaded.shape[:2] == (600, 300)


def test_redimensiona_lado_maior():
    big = np.full((5000, 3000, 3), 220, np.uint8)
    result = imaging.preprocess(_jpeg(big), max_long_edge=2576)
    assert max(result.width, result.height) == 2576


def test_arquivo_invalido():
    with pytest.raises(imaging.InvalidImageError):
        imaging.preprocess(b"isto nao e uma imagem")
