"""
Segmentação das estruturas da plântula.

Estratégia (validada nas imagens reais):
  - O filamento branco tem contraste baixíssimo contra o papel branco. O que o
    revela é o filtro de realce de estruturas tubulares de Sato ("vesselness"),
    que destaca formas finas e alongadas independentemente do brilho absoluto.
  - A semente (tegumento escuro) tem alto contraste -> baixa luminância (V).
  - Os cotilédones são amarelados -> alta saturação (S).
  - Tudo é restringido à área de trabalho (papel) para descartar bordas da caixa,
    a régua e o fundo.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
import cv2
from skimage.filters import sato
from skimage import img_as_float


@dataclass
class ParametrosSegmentacao:
    """Parâmetros ajustáveis. 'sensibilidade' 0..100 é o controle principal da GUI."""
    sensibilidade: int = 50          # maior = pega filamentos mais fracos (e mais ruído)
    altura_processamento: int = 1800  # imagem é reduzida a esta altura para processar
    # limiares de cor
    sat_min_cotiledone: int = 50
    v_max_semente: int = 100
    # filtros morfológicos / de tamanho (em px da imagem reduzida)
    area_min_plantula: int = 350
    altura_min_plantula: int = 70
    # uma plântula é estreita e vertical; bordas da caixa são largas.
    # descarta componentes mais largos que esta fração da largura processada.
    largura_max_frac: float = 0.30


def _limiar_filamento(sensibilidade: int) -> float:
    """
    Converte a sensibilidade (0..100) no limiar aplicado ao mapa de Sato (0..255).
    Sensibilidade alta -> limiar baixo -> capta filamentos mais fracos.
    Faixa calibrada nos exemplos: ~20 (muito sensível) a ~60 (conservador).
    """
    sensibilidade = max(0, min(100, sensibilidade))
    return 60 - (sensibilidade / 100.0) * 40.0   # 100->20, 0->60


def reduzir(img_bgr: np.ndarray, altura_alvo: int) -> Tuple[np.ndarray, float]:
    """Reduz a imagem para `altura_alvo`. Devolve (imagem_reduzida, escala)."""
    h = img_bgr.shape[0]
    escala = altura_alvo / float(h) if h > altura_alvo else 1.0
    if escala < 1.0:
        red = cv2.resize(img_bgr, None, fx=escala, fy=escala,
                         interpolation=cv2.INTER_AREA)
    else:
        red = img_bgr.copy()
    return red, escala


def detectar_area_trabalho(img_bgr: np.ndarray) -> np.ndarray:
    """
    Detecta a área de trabalho (papel branco) como máscara binária (uint8 0/255).
    É um palpite inicial; a interface permite ao usuário ajustar um retângulo.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    _, S, V = cv2.split(hsv)
    papel = ((V > 140) & (S < 45)).astype(np.uint8) * 255
    papel = cv2.morphologyEx(papel, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    papel = cv2.morphologyEx(papel, cv2.MORPH_OPEN, np.ones((15, 15), np.uint8))

    n, lab, st, _ = cv2.connectedComponentsWithStats(papel)
    if n <= 1:
        return np.ones(img_bgr.shape[:2], np.uint8) * 255
    idx = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    roi = (lab == idx).astype(np.uint8) * 255
    roi = cv2.morphologyEx(roi, cv2.MORPH_CLOSE, np.ones((41, 41), np.uint8))
    roi = cv2.erode(roi, np.ones((9, 9), np.uint8))
    return roi


def mapa_sato(img_bgr: np.ndarray) -> np.ndarray:
    """Mapa de realce de filamentos (0..255), realçando estruturas claras finas."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
    gc = clahe.apply(gray)
    s = sato(img_as_float(gc), sigmas=range(2, 6), black_ridges=False)
    return cv2.normalize(s, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


def mascara_estruturas(img_bgr: np.ndarray,
                       roi: Optional[np.ndarray],
                       par: ParametrosSegmentacao) -> np.ndarray:
    """
    Máscara binária (0/255) das estruturas das plântulas: filamento + semente +
    cotilédone, restrita à área de trabalho.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    _, S, V = cv2.split(hsv)

    sat_map = mapa_sato(img_bgr)
    limiar = _limiar_filamento(par.sensibilidade)
    filamento = (sat_map > limiar).astype(np.uint8)
    cotiledone = ((S > par.sat_min_cotiledone) & (V > 80)).astype(np.uint8)
    semente = (V < par.v_max_semente).astype(np.uint8)
    semente = cv2.morphologyEx(semente, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    mask = ((filamento | cotiledone | semente) > 0).astype(np.uint8)
    if roi is not None:
        mask = mask & (roi > 0).astype(np.uint8)

    # fecha pequenas quebras verticais ao longo do filamento
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 11)))
    return (mask * 255).astype(np.uint8)


def mascara_semente(img_bgr: np.ndarray, roi: Optional[np.ndarray],
                    par: ParametrosSegmentacao) -> np.ndarray:
    """Apenas a máscara das sementes (usada para localizar o estrangulamento)."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    _, _, V = cv2.split(hsv)
    semente = (V < par.v_max_semente).astype(np.uint8)
    semente = cv2.morphologyEx(semente, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    if roi is not None:
        semente = semente & (roi > 0).astype(np.uint8)
    return (semente * 255).astype(np.uint8)
