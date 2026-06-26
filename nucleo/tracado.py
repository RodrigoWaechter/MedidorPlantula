"""
Traçado do caminho de uma plântula a partir da sua máscara.

Etapas (validadas nas imagens reais):
  1. Esqueletização: reduz a estrutura a uma linha de 1 px de largura.
  2. Caminho mais longo: encontra a linha mais comprida dentro do esqueleto
     (de uma extremidade à outra), usando Dijkstra duplo com peso 1 para
     vizinhos ortogonais e raiz(2) para diagonais — assim o comprimento segue
     o caminho REAL, acompanhando curvas e enrolamentos (não em linha reta).
  3. Estrangulamento: procura o pico de escuridão (semente) no terço superior
     do caminho; o fim do tegumento marca a divisão hipocótilo/raiz.
"""

from __future__ import annotations
from typing import List, Optional, Tuple
import heapq
import numpy as np
from skimage.morphology import skeletonize

# pontos em (x, y) para os modelos; internamente usamos (linha, coluna) = (y, x)
PontoXY = Tuple[float, float]


def _esqueleto(mascara: np.ndarray) -> np.ndarray:
    return skeletonize(mascara > 0)


def _dijkstra_mais_distante(pts: set, origem: Tuple[int, int]):
    """A partir de `origem`, devolve o pixel mais distante e os predecessores."""
    melhor = {origem: 0.0}
    anterior = {origem: None}
    heap = [(0.0, origem)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > melhor.get(u, 1e18):
            continue
        uy, ux = u
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                v = (uy + dy, ux + dx)
                if v in pts:
                    peso = 1.41421356 if (dy and dx) else 1.0
                    nd = d + peso
                    if nd < melhor.get(v, 1e18):
                        melhor[v] = nd
                        anterior[v] = u
                        heapq.heappush(heap, (nd, v))
    alvo = max(melhor, key=melhor.get)
    return alvo, anterior, melhor


def caminho_mais_longo(mascara: np.ndarray) -> Optional[List[Tuple[int, int]]]:
    """
    Devolve a lista de pixels (y, x) do caminho mais longo do esqueleto,
    ordenada de cima (menor y) para baixo. None se não houver estrutura.
    """
    sk = _esqueleto(mascara)
    ys, xs = np.where(sk)
    if len(ys) < 2:
        return None
    pts = set(zip(ys.tolist(), xs.tolist()))

    inicio = next(iter(pts))
    a, _, _ = _dijkstra_mais_distante(pts, inicio)
    b, anterior, _ = _dijkstra_mais_distante(pts, a)

    caminho = []
    atual = b
    while atual is not None:
        caminho.append(atual)
        atual = anterior[atual]
    caminho.reverse()

    # garantir orientação topo -> ponta (topo = menor y, em cima)
    if caminho[0][0] > caminho[-1][0]:
        caminho.reverse()
    return caminho


def localizar_estrangulamento(caminho_yx: List[Tuple[int, int]],
                              canal_v: np.ndarray,
                              fracao_topo: float = 0.34,
                              janela: int = 6) -> int:
    """
    Localiza o índice do estrangulamento no caminho (divisão hipocótilo/raiz).

    Procura, no terço superior do caminho, o ponto mais escuro (a semente) e
    devolve o índice logo após o fim do tegumento escuro. Se nada se destacar,
    devolve um índice pequeno (estrangulamento perto do topo).
    """
    n = len(caminho_yx)
    if n < 4:
        return 0
    n_topo = max(3, int(n * fracao_topo))
    H, W = canal_v.shape[:2]

    escuridao = []
    for (py, px) in caminho_yx[:n_topo]:
        y0, y1 = max(0, py - janela), min(H, py + janela + 1)
        x0, x1 = max(0, px - janela), min(W, px + janela + 1)
        bloco = canal_v[y0:y1, x0:x1]
        escuridao.append(255.0 - float(bloco.mean()))
    escuridao = np.array(escuridao)

    pico = int(np.argmax(escuridao))
    # se o "pico" for fraco, a semente provavelmente não aparece -> perto do topo
    if escuridao[pico] < 60:
        return min(pico, n_topo // 2)

    # desce do pico até a escuridão cair pela metade (fim do tegumento)
    limiar = escuridao[pico] * 0.5
    idx = pico
    for i in range(pico, n_topo):
        if escuridao[i] < limiar:
            idx = i
            break
    else:
        idx = min(pico + 3, n - 2)
    return idx


def escalar_caminho(caminho_yx: List[Tuple[int, int]], escala: float) -> List[PontoXY]:
    """
    Converte um caminho em (y, x) na imagem reduzida para pontos (x, y) na
    imagem ORIGINAL, dividindo pela escala usada na redução.
    """
    fator = 1.0 / escala if escala else 1.0
    return [(x * fator, y * fator) for (y, x) in caminho_yx]


def simplificar(caminho: List[PontoXY], passo: int = 3) -> List[PontoXY]:
    """Reduz a densidade de pontos mantendo extremidades (deixa o desenho leve)."""
    if len(caminho) <= 2 or passo <= 1:
        return caminho
    reduzido = caminho[::passo]
    if reduzido[-1] != caminho[-1]:
        reduzido.append(caminho[-1])
    return reduzido
