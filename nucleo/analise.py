"""
Orquestração da pré-categorização automática.

Recebe uma imagem (BGR) e devolve uma lista de Plantula com o caminho já
reescalado para a resolução ORIGINAL e o estrangulamento localizado.

Este módulo é o "motor" da detecção automática. A interface gráfica chama
`detectar_plantulas` e depois deixa o usuário ajustar o resultado.
"""

from __future__ import annotations
from typing import List, Optional, Tuple
import numpy as np
import cv2

from . import segmentacao as seg
from . import tracado as tr
from .modelos import Plantula


def _componentes_plantula(mascara: np.ndarray, par: seg.ParametrosSegmentacao):
    """Separa a máscara em componentes que parecem plântulas (alongados o bastante)."""
    n, lab, st, _ = cv2.connectedComponentsWithStats(mascara)
    larg_max = par.largura_max_frac * mascara.shape[1]
    comps = []
    for i in range(1, n):
        area = st[i, cv2.CC_STAT_AREA]
        alt = st[i, cv2.CC_STAT_HEIGHT]
        larg = st[i, cv2.CC_STAT_WIDTH]
        if area < par.area_min_plantula or alt < par.altura_min_plantula:
            continue
        # descarta bordas largas (mais largas que o limite e não claramente verticais)
        if larg > larg_max and larg > alt * 0.8:
            continue
        comps.append(i)
    return lab, comps


def detectar_plantulas(img_bgr: np.ndarray,
                       par: Optional[seg.ParametrosSegmentacao] = None,
                       roi_retangulo: Optional[Tuple[int, int, int, int]] = None
                       ) -> List[Plantula]:
    """
    Detecta as plântulas na imagem.

    par: parâmetros de segmentação (sensibilidade etc.).
    roi_retangulo: (x, y, w, h) em coordenadas da imagem ORIGINAL para limitar a
                   área de trabalho. Se None, a área é detectada automaticamente.

    Retorna lista de Plantula (coordenadas na imagem original, sem rótulos finais).
    """
    if par is None:
        par = seg.ParametrosSegmentacao()

    reduzida, escala = seg.reduzir(img_bgr, par.altura_processamento)

    # Área de trabalho
    if roi_retangulo is not None:
        x, y, w, h = roi_retangulo
        roi = np.zeros(reduzida.shape[:2], np.uint8)
        x0, y0 = int(x * escala), int(y * escala)
        x1, y1 = int((x + w) * escala), int((y + h) * escala)
        x0, y0 = max(0, x0), max(0, y0)
        x1 = min(reduzida.shape[1], x1)
        y1 = min(reduzida.shape[0], y1)
        roi[y0:y1, x0:x1] = 255
    else:
        roi = seg.detectar_area_trabalho(reduzida)

    mascara = seg.mascara_estruturas(reduzida, roi, par)
    canal_v = cv2.cvtColor(reduzida, cv2.COLOR_BGR2HSV)[:, :, 2]

    lab, comps = _componentes_plantula(mascara, par)

    plantulas: List[Plantula] = []
    for cid, i in enumerate(comps, start=1):
        comp_mask = (lab == i).astype(np.uint8) * 255
        caminho_yx = tr.caminho_mais_longo(comp_mask)
        if not caminho_yx or len(caminho_yx) < 2:
            continue
        idx_estr = tr.localizar_estrangulamento(caminho_yx, canal_v)
        caminho_xy = tr.escalar_caminho(caminho_yx, escala)
        caminho_xy = tr.simplificar(caminho_xy, passo=2)
        # reposicionar o índice do estrangulamento após a simplificação (proporcional)
        if len(caminho_yx) > 1:
            frac = idx_estr / (len(caminho_yx) - 1)
            idx_estr_simpl = int(round(frac * (len(caminho_xy) - 1)))
        else:
            idx_estr_simpl = 0

        p = Plantula(id=cid, caminho=caminho_xy,
                     idx_estrangulamento=idx_estr_simpl,
                     rotulo=f"P{cid}", origem_automatica=True)
        plantulas.append(p)

    return plantulas


def gerar_mascara_visual(img_bgr: np.ndarray,
                         par: Optional[seg.ParametrosSegmentacao] = None,
                         roi_retangulo: Optional[Tuple[int, int, int, int]] = None
                         ) -> np.ndarray:
    """
    Devolve a máscara de estruturas redimensionada para o tamanho ORIGINAL.
    Útil para a interface mostrar uma prévia do que está sendo detectado.
    """
    if par is None:
        par = seg.ParametrosSegmentacao()
    reduzida, escala = seg.reduzir(img_bgr, par.altura_processamento)
    if roi_retangulo is not None:
        x, y, w, h = roi_retangulo
        roi = np.zeros(reduzida.shape[:2], np.uint8)
        x0, y0 = max(0, int(x * escala)), max(0, int(y * escala))
        x1 = min(reduzida.shape[1], int((x + w) * escala))
        y1 = min(reduzida.shape[0], int((y + h) * escala))
        roi[y0:y1, x0:x1] = 255
    else:
        roi = seg.detectar_area_trabalho(reduzida)
    mascara = seg.mascara_estruturas(reduzida, roi, par)
    return cv2.resize(mascara, (img_bgr.shape[1], img_bgr.shape[0]),
                      interpolation=cv2.INTER_NEAREST)
