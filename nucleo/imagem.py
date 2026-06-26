"""
Carregamento de imagens.

Aceita formatos comuns (PNG, JPG) via OpenCV. Para HEIC (fotos de iPhone),
tenta usar a biblioteca opcional `pillow-heif`. Se ela não estiver instalada,
mostra uma mensagem clara explicando como proceder.
"""

from __future__ import annotations
import os
import numpy as np
import cv2

# Suporte opcional a HEIC
_HEIC_OK = False
try:
    import pillow_heif  # type: ignore
    from PIL import Image  # type: ignore
    pillow_heif.register_heif_opener()
    _HEIC_OK = True
except Exception:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        Image = None  # type: ignore


EXTENSOES_SUPORTADAS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff",
                        ".heic", ".heif", ".webp")


class ErroImagem(Exception):
    pass


def heic_disponivel() -> bool:
    return _HEIC_OK


def carregar_bgr(caminho: str) -> np.ndarray:
    """
    Carrega uma imagem e devolve um array BGR (uint8) pronto para o OpenCV.
    Levanta ErroImagem com mensagem amigável se algo der errado.
    """
    if not os.path.exists(caminho):
        raise ErroImagem(f"Arquivo não encontrado:\n{caminho}")

    ext = os.path.splitext(caminho)[1].lower()

    if ext in (".heic", ".heif"):
        if not _HEIC_OK:
            raise ErroImagem(
                "Esta é uma imagem HEIC (formato de iPhone).\n\n"
                "Para abrir HEIC, instale o suporte opcional executando:\n"
                "    pip install pillow-heif\n\n"
                "Ou converta a foto para PNG/JPG antes de abrir."
            )
        img = Image.open(caminho).convert("RGB")
        rgb = np.array(img)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    # Demais formatos: tentar OpenCV primeiro
    dados = np.fromfile(caminho, dtype=np.uint8)  # lida com acentos no caminho
    img = cv2.imdecode(dados, cv2.IMREAD_COLOR)
    if img is not None:
        return img

    # Fallback via Pillow
    if Image is not None:
        try:
            pil = Image.open(caminho).convert("RGB")
            return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        except Exception as e:
            raise ErroImagem(f"Não foi possível abrir a imagem:\n{e}")

    raise ErroImagem("Formato de imagem não suportado ou arquivo corrompido.")


def salvar_bgr(caminho: str, img_bgr: np.ndarray) -> None:
    """Salva uma imagem BGR, lidando com caminhos que tenham acentos."""
    ext = os.path.splitext(caminho)[1].lower() or ".png"
    ok, buf = cv2.imencode(ext, img_bgr)
    if not ok:
        raise ErroImagem("Falha ao codificar a imagem para salvar.")
    buf.tofile(caminho)
