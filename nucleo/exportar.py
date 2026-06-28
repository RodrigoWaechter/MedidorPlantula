"""Exportação dos resultados: tabela CSV e imagem anotada."""

from __future__ import annotations
from typing import List
import csv
import numpy as np
import cv2

from .modelos import Plantula, Calibracao
from .imagem import salvar_bgr

# Cores em BGR (ordem usada pelo OpenCV)
COR_SEG1 = (60, 180, 60)    # verde  - hipocótilo
COR_SEG2 = (230, 130, 40)   # azul   - raiz
COR_TOPO = (0, 0, 230)      # vermelho
COR_ESTR = (200, 0, 200)    # magenta - estrangulamento
COR_PONTA = (0, 200, 230)   # amarelo


def exportar_csv(caminho_csv: str, plantulas: List[Plantula],
                 cal: Calibracao) -> None:
    """
    Salva a tabela de medidas em CSV.
    Usa ponto-e-vírgula como separador e vírgula como decimal,
    para compatibilidade com o Excel em configuração brasileira.
    """
    unidade = cal.unidade if cal.definida else "px"
    with open(caminho_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Plantula",
                    f"Segmento 1 - hipocotilo ({unidade})",
                    f"Segmento 2 - raiz ({unidade})",
                    f"Comprimento total ({unidade})"])
        for p in plantulas:
            m = p.medidas(cal)
            def fmt(v):
                # formata com 2 casas decimais e troca ponto por vírgula
                return f"{v:.2f}".replace(".", ",") if v is not None else ""
            w.writerow([m["rotulo"], fmt(m["seg1"]), fmt(m["seg2"]), fmt(m["total"])])
        if not cal.definida:
            w.writerow([])
            w.writerow(["Obs.: escala não calibrada - valores em pixels."])


def desenhar_anotacoes(img_bgr: np.ndarray, plantulas: List[Plantula],
                       cal: Calibracao, espessura: int = None,
                       raio: int = None) -> np.ndarray:
    """
    Desenha caminhos, pontos-chave e rótulos sobre uma cópia da imagem.
    A espessura das linhas e o raio dos círculos são calculados
    proporcionalmente à altura da imagem para ficarem visíveis em qualquer resolução.
    """
    vis = img_bgr.copy()
    h = vis.shape[0]
    if espessura is None:
        espessura = max(2, h // 600)
    if raio is None:
        raio = max(4, h // 250)
    fonte = cv2.FONT_HERSHEY_SIMPLEX
    escala_fonte = max(0.5, h / 1800.0)

    for p in plantulas:
        if len(p.caminho) < 2:
            continue
        ie = max(0, min(p.idx_estrangulamento, len(p.caminho) - 1))

        # desenha o segmento 1 (hipocótilo) do topo até o estrangulamento
        for i in range(1, ie + 1):
            a = tuple(map(int, p.caminho[i - 1]))
            b = tuple(map(int, p.caminho[i]))
            cv2.line(vis, a, b, COR_SEG1, espessura, cv2.LINE_AA)

        # desenha o segmento 2 (raiz) do estrangulamento até a ponta
        for i in range(ie + 1, len(p.caminho)):
            a = tuple(map(int, p.caminho[i - 1]))
            b = tuple(map(int, p.caminho[i]))
            cv2.line(vis, a, b, COR_SEG2, espessura, cv2.LINE_AA)

        topo = tuple(map(int, p.topo))
        estr = tuple(map(int, p.estrangulamento))
        ponta = tuple(map(int, p.ponta))
        cv2.circle(vis, topo, raio, COR_TOPO, -1, cv2.LINE_AA)
        cv2.circle(vis, estr, raio, COR_ESTR, -1, cv2.LINE_AA)
        cv2.circle(vis, ponta, raio, COR_PONTA, -1, cv2.LINE_AA)

        rot = p.rotulo or f"P{p.id}"
        pos = (topo[0] + raio + 3, topo[1] - raio)
        # rótulo com contorno escuro para legibilidade em qualquer fundo
        cv2.putText(vis, rot, pos, fonte, escala_fonte, (0, 0, 0),
                    espessura + 2, cv2.LINE_AA)
        cv2.putText(vis, rot, pos, fonte, escala_fonte, (255, 255, 255),
                    espessura, cv2.LINE_AA)
    return vis


def exportar_imagem(caminho_saida: str, img_bgr: np.ndarray,
                    plantulas: List[Plantula], cal: Calibracao) -> None:
    vis = desenhar_anotacoes(img_bgr, plantulas, cal)
    salvar_bgr(caminho_saida, vis)