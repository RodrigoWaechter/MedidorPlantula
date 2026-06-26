#!/usr/bin/env python3
"""
Ponto de entrada do Medidor de Plântulas.

Execute:
    python run.py

Se o Tkinter não estiver instalado, o programa avisa como instalá-lo.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    try:
        import tkinter  # noqa: F401
    except ModuleNotFoundError:
        print("ERRO: o módulo Tkinter não está disponível.\n")
        print("O Tkinter normalmente já vem com o Python. Se não veio:")
        print("  - Windows/macOS: reinstale o Python pelo site oficial")
        print("    (https://www.python.org) marcando a opção 'tcl/tk'.")
        print("  - Linux (Debian/Ubuntu): sudo apt install python3-tk")
        print("  - Linux (Fedora):        sudo dnf install python3-tkinter")
        sys.exit(1)

    try:
        import cv2, numpy, scipy, skimage  # noqa: F401
        from PIL import Image  # noqa: F401
    except ModuleNotFoundError as e:
        print(f"ERRO: faltam bibliotecas: {e.name}\n")
        print("Instale as dependências com:")
        print("    pip install -r requirements.txt")
        sys.exit(1)

    from interface.janela import iniciar
    iniciar()


if __name__ == "__main__":
    main()
