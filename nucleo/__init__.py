"""Núcleo de processamento (sem interface gráfica) — totalmente testável."""

from .modelos import Plantula, Calibracao, Projeto
from .segmentacao import ParametrosSegmentacao
from .analise import detectar_plantulas, gerar_mascara_visual
from . import imagem, exportar

__all__ = [
    "Plantula", "Calibracao", "Projeto", "ParametrosSegmentacao",
    "detectar_plantulas", "gerar_mascara_visual", "imagem", "exportar",
]
