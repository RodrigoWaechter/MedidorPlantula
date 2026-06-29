"""Estruturas de dados do projeto."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import math

Ponto = Tuple[float, float]  # (x, y)


def _dist(a: Ponto, b: Ponto) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def comprimento_caminho(caminho: List[Ponto], ini: int = 0, fim: Optional[int] = None) -> float:
    """Soma das distâncias entre pontos consecutivos de ini até fim, em pixels."""
    if fim is None:
        fim = len(caminho) - 1
    total = 0.0
    for i in range(ini + 1, fim + 1):
        total += _dist(caminho[i - 1], caminho[i])
    return total


@dataclass
class Calibracao:
    """Converte pixels em unidade real (mm ou cm) a partir de dois pontos clicados."""
    p1: Optional[Ponto] = None
    p2: Optional[Ponto] = None
    distancia_real: float = 0.0
    unidade: str = "cm"

    @property
    def definida(self) -> bool:
        return (self.p1 is not None and self.p2 is not None
                and self.distancia_real > 0)

    @property
    def px_por_unidade(self) -> Optional[float]:
        """Razão entre a distância em pixels e a distância real informada."""
        if not self.definida:
            return None
        d_px = _dist(self.p1, self.p2)
        if d_px <= 0:
            return None
        return d_px / self.distancia_real

    def px_para_unidade(self, valor_px: float) -> Optional[float]:
        """Converte um valor em pixels para a unidade real calibrada."""
        ppu = self.px_por_unidade
        if ppu is None:
            return None
        return valor_px / ppu


@dataclass
class Plantula:
    """
    Uma plântula medida.

    caminho: lista de pontos (x, y) do topo até a ponta da raiz.
    idx_estrangulamento: índice no caminho que divide os dois segmentos:
      - Segmento 1 (hipocótilo): índice 0 até idx_estrangulamento.
      - Segmento 2 (raiz):       idx_estrangulamento até o último ponto.
    """
    id: int
    caminho: List[Ponto] = field(default_factory=list)
    idx_estrangulamento: int = 0
    rotulo: str = ""
    origem_automatica: bool = False

    @property
    def topo(self) -> Optional[Ponto]:
        return self.caminho[0] if self.caminho else None

    @property
    def ponta(self) -> Optional[Ponto]:
        return self.caminho[-1] if self.caminho else None

    @property
    def estrangulamento(self) -> Optional[Ponto]:
        if not self.caminho:
            return None
        i = max(0, min(self.idx_estrangulamento, len(self.caminho) - 1))
        return self.caminho[i]

    @property
    def seg1_px(self) -> float:
        """Comprimento do hipocótilo em pixels (topo → estrangulamento)."""
        if len(self.caminho) < 2:
            return 0.0
        return comprimento_caminho(self.caminho, 0, self.idx_estrangulamento)

    @property
    def seg2_px(self) -> float:
        """Comprimento da raiz em pixels (estrangulamento → ponta)."""
        if len(self.caminho) < 2:
            return 0.0
        return comprimento_caminho(self.caminho, self.idx_estrangulamento,
                                   len(self.caminho) - 1)

    @property
    def total_px(self) -> float:
        """Comprimento total em pixels (topo → ponta)."""
        return comprimento_caminho(self.caminho, 0, len(self.caminho) - 1)

    def medidas(self, cal: Calibracao) -> dict:
        """
        Retorna seg1, seg2 e total na unidade real calibrada,
        ou em pixels se a calibração não estiver definida.
        """
        d = {
            "rotulo": self.rotulo or f"P{self.id}",
            "seg1_px": self.seg1_px,
            "seg2_px": self.seg2_px,
            "total_px": self.total_px,
            "unidade": cal.unidade if cal.definida else "px",
        }
        if cal.definida:
            d["seg1"] = cal.px_para_unidade(self.seg1_px)
            d["seg2"] = cal.px_para_unidade(self.seg2_px)
            d["total"] = cal.px_para_unidade(self.total_px)
        else:
            d["seg1"] = self.seg1_px
            d["seg2"] = self.seg2_px
            d["total"] = self.total_px
        return d

    def mover_estrangulamento_para(self, ponto: Ponto) -> None:
        """Reposiciona o estrangulamento no ponto do caminho mais próximo de `ponto`."""
        if not self.caminho:
            return
        melhor, melhor_d = 0, float("inf")
        for i, p in enumerate(self.caminho):
            dd = _dist(p, ponto)
            if dd < melhor_d:
                melhor_d, melhor = dd, i
        self.idx_estrangulamento = melhor

    def recortar_topo_em(self, ponto: Ponto) -> None:
        """Descarta os pontos do caminho anteriores ao mais próximo de `ponto`."""
        if len(self.caminho) < 2:
            return
        i = self._indice_mais_proximo(ponto)
        if i >= len(self.caminho) - 1:
            return
        self.caminho = self.caminho[i:]
        self.idx_estrangulamento = max(0, self.idx_estrangulamento - i)

    def recortar_ponta_em(self, ponto: Ponto) -> None:
        """Descarta os pontos do caminho posteriores ao mais próximo de `ponto`."""
        if len(self.caminho) < 2:
            return
        i = self._indice_mais_proximo(ponto)
        if i <= 0:
            return
        self.caminho = self.caminho[:i + 1]
        self.idx_estrangulamento = min(self.idx_estrangulamento, len(self.caminho) - 1)

    def _indice_mais_proximo(self, ponto: Ponto) -> int:
        melhor, melhor_d = 0, float("inf")
        for i, p in enumerate(self.caminho):
            dd = _dist(p, ponto)
            if dd < melhor_d:
                melhor_d, melhor = dd, i
        return melhor


@dataclass
class Projeto:
    """Estado completo de uma análise: imagem, plântulas e calibração."""
    caminho_imagem: str = ""
    plantulas: List[Plantula] = field(default_factory=list)
    calibracao: Calibracao = field(default_factory=Calibracao)
    proximo_id: int = 1

    def adicionar_plantula(self, caminho_pts: List[Ponto],
                           idx_estrang: int = 0,
                           automatica: bool = False) -> Plantula:
        p = Plantula(id=self.proximo_id, caminho=list(caminho_pts),
                     idx_estrangulamento=idx_estrang,
                     rotulo=f"P{self.proximo_id}",
                     origem_automatica=automatica)
        self.plantulas.append(p)
        self.proximo_id += 1
        return p

    def remover(self, plantula: Plantula) -> None:
        if plantula in self.plantulas:
            self.plantulas.remove(plantula)

    def renumerar(self) -> None:
        """Reordena os rótulos P1 Pn por posição visual (cima para baixo, esquerda para direita)."""
        def chave(p: Plantula):
            t = p.topo or (0, 0)
            return (round(t[1] / 50), t[0])
        self.plantulas.sort(key=chave)
        for i, p in enumerate(self.plantulas, start=1):
            p.id = i
            p.rotulo = f"P{i}"
        self.proximo_id = len(self.plantulas) + 1