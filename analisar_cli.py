#!/usr/bin/env python3
"""
Modo linha de comando: analisa uma imagem sem abrir a interface gráfica.

Uso:
    python analisar_cli.py FOTO.png [--sensibilidade 50] [--saida pasta]
    python analisar_cli.py FOTO.png --escala-px 500 --escala-real 10 --unidade cm

Gera, na pasta de saída:
    <nome>_anotada.png   imagem com as marcações
    <nome>_medidas.csv   tabela com os comprimentos

Sem calibração de escala, as medidas saem em pixels. Para calibrar pela linha
de comando, informe --escala-px (distância em pixels entre dois pontos da régua)
e --escala-real (a distância real correspondente).
"""

import argparse
import os
import sys

# permite rodar a partir de qualquer pasta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nucleo import imagem, exportar
from nucleo.segmentacao import ParametrosSegmentacao
from nucleo.analise import detectar_plantulas
from nucleo.modelos import Calibracao, Projeto


def main():
    ap = argparse.ArgumentParser(description="Mede plântulas em uma foto.")
    ap.add_argument("imagem", help="caminho da foto (.png, .jpg, .heic...)")
    ap.add_argument("--sensibilidade", type=int, default=50,
                    help="0..100 (maior pega filamentos mais fracos). Padrão 50.")
    ap.add_argument("--saida", default=None, help="pasta de saída (padrão: ao lado da foto)")
    ap.add_argument("--escala-px", type=float, default=None,
                    help="distância em pixels entre dois pontos da régua")
    ap.add_argument("--escala-real", type=float, default=None,
                    help="distância real correspondente (ex.: 10)")
    ap.add_argument("--unidade", default="cm", choices=["cm", "mm"])
    args = ap.parse_args()

    try:
        img = imagem.carregar_bgr(args.imagem)
    except imagem.ErroImagem as e:
        print(f"ERRO: {e}")
        sys.exit(1)

    par = ParametrosSegmentacao(sensibilidade=args.sensibilidade)
    print("Detectando plântulas...")
    plantulas = detectar_plantulas(img, par)

    proj = Projeto(caminho_imagem=args.imagem)
    for p in plantulas:
        proj.plantulas.append(p)
    proj.renumerar()

    # calibração opcional
    cal = Calibracao(unidade=args.unidade)
    if args.escala_px and args.escala_real:
        cal.p1 = (0.0, 0.0)
        cal.p2 = (args.escala_px, 0.0)
        cal.distancia_real = args.escala_real
    proj.calibracao = cal

    pasta = args.saida or os.path.dirname(os.path.abspath(args.imagem))
    os.makedirs(pasta, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.imagem))[0]
    cam_img = os.path.join(pasta, f"{base}_anotada.png")
    cam_csv = os.path.join(pasta, f"{base}_medidas.csv")

    exportar.exportar_imagem(cam_img, img, proj.plantulas, cal)
    exportar.exportar_csv(cam_csv, proj.plantulas, cal)

    print(f"\n{len(proj.plantulas)} plântula(s) detectada(s).")
    unidade = cal.unidade if cal.definida else "px"
    print(f"{'Plântula':<10}{'Seg1 ('+unidade+')':>14}{'Seg2 ('+unidade+')':>14}{'Total ('+unidade+')':>14}")
    for p in proj.plantulas:
        m = p.medidas(cal)
        print(f"{m['rotulo']:<10}{m['seg1']:>14.2f}{m['seg2']:>14.2f}{m['total']:>14.2f}")
    print(f"\nImagem anotada: {cam_img}")
    print(f"Tabela CSV:     {cam_csv}")


if __name__ == "__main__":
    main()
