"""Pré-processamento da foto da redação antes da transcrição.

1. orientação EXIF; 2. recorte da folha com correção de perspectiva;
3. correção de inclinação; 4. contraste leve (CLAHE, sem binarizar, porque a
IA lê melhor uma imagem natural); 5. redimensiona e salva em JPEG 90.
"""

import io
import logging
import math
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()
logger = logging.getLogger(__name__)

# A folha precisa ocupar ao menos esta fração da foto para ser recortada.
MIN_PAGE_AREA = 0.25
MAX_DESKEW_DEGREES = 8.0


class InvalidImageError(Exception):
    pass


@dataclass
class ProcessedImage:
    data: bytes
    width: int
    height: int
    cropped: bool
    deskew_degrees: float


def load_image(data: bytes) -> np.ndarray:
    """Abre JPEG/PNG/HEIC/WebP aplicando a orientação EXIF. Devolve BGR."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            rgb = img.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError("Não foi possível abrir a imagem.") from exc
    return cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)


def _order_corners(pts: np.ndarray) -> np.ndarray:
    pts = pts.reshape(4, 2).astype("float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array(
        [pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]],
        dtype="float32",
    )  # topo-esq, topo-dir, baixo-dir, baixo-esq


def find_page(img: np.ndarray) -> np.ndarray | None:
    """Procura o contorno de 4 lados da folha. Devolve os cantos ordenados ou None."""
    h, w = img.shape[:2]
    scale = 1000 / max(h, w) if max(h, w) > 1000 else 1.0
    small = cv2.resize(img, None, fx=scale, fy=scale) if scale != 1.0 else img
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_total = small.shape[0] * small.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(contour) < MIN_PAGE_AREA * area_total:
            break
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return _order_corners(approx / scale)
    return None


def warp_page(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = corners
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], "float32")
    matrix = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(img, matrix, (width, height), flags=cv2.INTER_CUBIC)


def estimate_skew(img: np.ndarray) -> float:
    """Ângulo (graus) das linhas de texto, pela mediana das retas quase horizontais."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    min_len = max(img.shape[1] // 4, 50)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 720, threshold=100, minLineLength=min_len, maxLineGap=20
    )
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if abs(angle) <= MAX_DESKEW_DEGREES:
            angles.append(angle)
    if len(angles) < 3:
        return 0.0
    return float(np.median(angles))


def rotate(img: np.ndarray, degrees: float) -> np.ndarray:
    h, w = img.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    return cv2.warpAffine(
        img, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def enhance_contrast(img: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return cv2.cvtColor(cv2.merge((clahe.apply(l_channel), a, b)), cv2.COLOR_LAB2BGR)


def resize_max(img: np.ndarray, max_long_edge: int) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= max_long_edge:
        return img
    scale = max_long_edge / max(h, w)
    return cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)


def encode_jpeg(img: np.ndarray, quality: int = 90) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise InvalidImageError("Falha ao gerar JPEG.")
    return buf.tobytes()


def preprocess(data: bytes, max_long_edge: int = 2576) -> ProcessedImage:
    img = load_image(data)
    corners = find_page(img)
    cropped = corners is not None
    if cropped:
        img = warp_page(img, corners)
    skew = estimate_skew(img)
    if abs(skew) >= 0.3:
        img = rotate(img, skew)
    img = enhance_contrast(img)
    img = resize_max(img, max_long_edge)
    h, w = img.shape[:2]
    return ProcessedImage(encode_jpeg(img), w, h, cropped, round(skew, 2))
