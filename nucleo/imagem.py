"""Carregamento e salvamento de imagens."""

from __future__ import annotations
import os
import numpy as np
import cv2

# Importa o suporte a HEIC (fotos de iPhone) - obrigatório
import pillow_heif  # type: ignore
from PIL import Image  # type: ignore

pillow_heif.register_heif_opener()


EXTENSOES_SUPORTADAS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff",
                        ".heic", ".heif", ".webp")


class ErroImagem(Exception):
    pass


def carregar_bgr(caminho: str) -> np.ndarray:
    """
    Carrega uma imagem e devolve um array BGR pronto para o OpenCV.
    Levanta ErroImagem com mensagem amigável se algo der errado.

    Suporta todos os formatos incluindo HEIC (fotos de iPhone).
    """
    if not os.path.exists(caminho):
        raise ErroImagem(f"Arquivo não encontrado:\n{caminho}")

    ext = os.path.splitext(caminho)[1].lower()

    if ext in (".heic", ".heif"):
        img = Image.open(caminho).convert("RGB")
        rgb = np.array(img)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    # np.fromfile lida com caminhos que contenham acentos ou caracteres especiais,
    # ao contrário de cv2.imread que pode falhar nesses casos no Windows
    dados = np.fromfile(caminho, dtype=np.uint8)
    img = cv2.imdecode(dados, cv2.IMREAD_COLOR)
    if img is not None:
        return img

    # fallback via Pillow para formatos não suportados pelo OpenCV
    try:
        pil = Image.open(caminho).convert("RGB")
        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    except Exception as e:
        raise ErroImagem(f"Não foi possível abrir a imagem:\n{e}")


def salvar_bgr(caminho: str, img_bgr: np.ndarray) -> None:
    """
    Salva uma imagem BGR em disco.
    Usa imencode + tofile para suportar caminhos com acentos no Windows.
    """
    ext = os.path.splitext(caminho)[1].lower() or ".png"
    ok, buf = cv2.imencode(ext, img_bgr)
    if not ok:
        raise ErroImagem("Falha ao codificar a imagem para salvar.")
    buf.tofile(caminho)