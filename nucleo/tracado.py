"""Apoio ao traçado manual: sugestão automática do ponto de estrangulamento."""

from __future__ import annotations
from typing import List, Tuple
import math
import numpy as np
import cv2

PontoXY = Tuple[float, float]


def _detectar_sementes_proximas(gray: np.ndarray,
                                caminho_yx: List[Tuple[int, int]],
                                margem: int = 80) -> List[Tuple[int, int]]:
    """
    Acha os contornos escuros (semente) em uma janela ao redor do trecho
    superior do caminho. Devolve uma lista de centros (y, x).
    """
    H, W = gray.shape[:2]
    n = len(caminho_yx)
    if n < 2:
        return []

    topo = caminho_yx[: max(2, n // 2)]
    ys = [p[0] for p in topo]
    xs = [p[1] for p in topo]
    y0 = max(0, min(ys) - margem)
    y1 = min(H, max(ys) + margem)
    x0 = max(0, min(xs) - margem)
    x1 = min(W, max(xs) + margem)
    if y1 <= y0 or x1 <= x0:
        return []

    sub = gray[y0:y1, x0:x1]
    suave = cv2.GaussianBlur(sub, (5, 5), 0)

    # inverte para que pixels escuros (semente) fiquem brancos,
    # depois binariza com o limiar de Otsu calculado automaticamente
    _, escuro = cv2.threshold(suave, 0, 255,
                              cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    cnts, _ = cv2.findContours(escuro, cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)
    centros = []
    for c in cnts:
        a = cv2.contourArea(c)
        if a < 80 or a > 8000:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if min(w, h) == 0 or max(w, h) / min(w, h) > 5:
            # descarta riscos longos (bordas, fios, etc.)
            continue
        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        # centroide pelo método dos momentos
        cx = int(M["m10"] / M["m00"]) + x0
        cy = int(M["m01"] / M["m00"]) + y0
        centros.append((cy, cx))
    return centros


def localizar_estrangulamento(caminho_yx: List[Tuple[int, int]],
                              gray: np.ndarray,
                              fracao_topo: float = 0.5,
                              dist_max: float = 70.0) -> int:
    """
    Devolve o índice do ponto do caminho mais próximo do estrangulamento
    (divisão hipocótilo / raiz), que coincide com a semente.

    Tenta primeiro achar a semente via contornos; se não encontrar nenhuma
    suficientemente perto, usa o pixel mais escuro do trecho superior
    como estimativa.

    Parâmetros:
      caminho_yx  : lista de pontos (y, x) do topo para a ponta.
      gray        : imagem em escala de cinza.
      fracao_topo : fração do caminho considerada trecho superior.
      dist_max    : distância máxima (px) entre semente e caminho para aceitar.
    """
    n = len(caminho_yx)
    if n < 4:
        return 0
    topo = caminho_yx[: max(2, int(n * fracao_topo))]

    sementes = _detectar_sementes_proximas(gray, caminho_yx)
    if sementes:
        # escolhe a semente mais próxima do trecho superior
        melhor_s = None
        melhor_d = float("inf")
        for s in sementes:
            d = min(math.hypot(s[0] - p[0], s[1] - p[1]) for p in topo)
            if d < melhor_d:
                melhor_d, melhor_s = d, s
        if melhor_s is not None and melhor_d <= dist_max:
            idx = min(range(n),
                      key=lambda i: math.hypot(caminho_yx[i][0] - melhor_s[0],
                                               caminho_yx[i][1] - melhor_s[1]))
            return idx

    # plano B: ponto mais escuro do trecho superior
    H, W = gray.shape[:2]
    melhor_i, melhor_v = 0, 256
    for i, (py, px) in enumerate(topo):
        if 0 <= py < H and 0 <= px < W:
            v = int(gray[py, px])
            if v < melhor_v:
                melhor_v, melhor_i = v, i
    return melhor_i


def escalar_caminho(caminho_yx: List[Tuple[int, int]], escala: float) -> List[PontoXY]:
    """
    Converte um caminho em (y, x) na imagem reduzida para pontos (x, y)
    na imagem original, revertendo a escala usada na redução.
    """
    fator = 1.0 / escala if escala else 1.0
    return [(x * fator, y * fator) for (y, x) in caminho_yx]


def simplificar(caminho: List[PontoXY], passo: int = 3) -> List[PontoXY]:
    """Reduz a densidade de pontos mantendo as extremidades."""
    if len(caminho) <= 2 or passo <= 1:
        return caminho
    reduzido = caminho[::passo]
    if reduzido[-1] != caminho[-1]:
        reduzido.append(caminho[-1])
    return reduzido
