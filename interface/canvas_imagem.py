"""
Canvas interativo da interface gráfica.

Responsável por:
  - exibir a imagem com zoom (roda do mouse) e deslocamento/pan (botão direito);
  - desenhar as plântulas (caminhos coloridos e pontos-chave);
  - permitir edição (arrastar o estrangulamento, o topo e a ponta);
  - os modos de calibração (2 cliques), definição da área e traçado manual.

Toda a conversão entre coordenadas da TELA e da IMAGEM ORIGINAL fica centralizada
em `img_para_canvas` e `canvas_para_img`, para evitar erros de alinhamento.
"""

from __future__ import annotations
from typing import Callable, List, Optional, Tuple
import tkinter as tk
from PIL import Image, ImageTk

from nucleo.modelos import Plantula

# Modos de interação
MODO_NAVEGAR = "navegar"
MODO_CALIBRAR = "calibrar"
MODO_AREA = "area"
MODO_TRACAR = "tracar"

# Cores (hexadecimal, para o Tkinter)
COR_SEG1 = "#3cb43c"     # verde - hipocótilo
COR_SEG2 = "#2882e6"     # azul  - raiz
COR_TOPO = "#e60000"     # vermelho
COR_ESTR = "#c800c8"     # magenta
COR_PONTA = "#e6c800"    # amarelo
COR_SEL = "#ff8000"      # laranja - seleção
COR_AREA = "#00b0b0"     # ciano - área de trabalho

RAIO_ALCA = 6            # raio das alças em pixels de tela
TOLERANCIA_CLIQUE = 12   # distância em px de tela para "pegar" uma alça


class CanvasImagem(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)

        self.canvas = tk.Canvas(self, bg="#2b2b2b", highlightthickness=0,
                                cursor="cross")
        self.hbar = tk.Scrollbar(self, orient="horizontal")
        self.vbar = tk.Scrollbar(self, orient="vertical")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # imagem
        self.pil_base: Optional[Image.Image] = None
        self.img_w = 0
        self.img_h = 0
        self.zoom = 1.0
        self.ox = 0.0   # posição no canvas do pixel (0,0) da imagem
        self.oy = 0.0
        self._tk_img = None  # referência viva do PhotoImage

        # estado
        self.modo = MODO_NAVEGAR
        self.plantulas: List[Plantula] = []
        self.selecionada: Optional[Plantula] = None
        self._precisa_ajustar = False

        # arrasto de pan
        self._pan_inicio = None
        # arrasto de alça (edição)
        self._arrasto = None  # dict com info do que está sendo arrastado
        # calibração / área / traçado
        self._pontos_temp: List[Tuple[float, float]] = []
        self._retangulo_temp = None
        self._area_inicio = None

        # callbacks que a janela principal define
        self.ao_calibrar: Optional[Callable] = None
        self.ao_definir_area: Optional[Callable] = None
        self.ao_criar_plantula: Optional[Callable] = None
        self.ao_mudar_selecao: Optional[Callable] = None
        self.ao_editar: Optional[Callable] = None
        self.ao_status: Optional[Callable] = None

        self._bind_eventos()

    # ------------------------------------------------------------------ #
    #  Configuração de imagem e projeto                                   #
    # ------------------------------------------------------------------ #
    def definir_imagem(self, pil_image: Image.Image):
        self.pil_base = pil_image.convert("RGB")
        self.img_w, self.img_h = self.pil_base.size
        self.selecionada = None
        self._precisa_ajustar = True
        self.after(50, self._tentar_ajuste_inicial)

    def _tentar_ajuste_inicial(self):
        if self._precisa_ajustar and self.canvas.winfo_width() > 1:
            self._precisa_ajustar = False
            self.ajustar_a_janela()
        elif self._precisa_ajustar:
            self.after(50, self._tentar_ajuste_inicial)

    def definir_plantulas(self, plantulas: List[Plantula]):
        self.plantulas = plantulas
        self.redesenhar()

    def ajustar_a_janela(self):
        """Ajusta zoom e posição para a imagem caber inteira no canvas."""
        if self.pil_base is None:
            return
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        self.zoom = min(cw / self.img_w, ch / self.img_h) * 0.98
        self.zoom = max(0.02, self.zoom)
        # centraliza
        self.ox = (cw - self.img_w * self.zoom) / 2
        self.oy = (ch - self.img_h * self.zoom) / 2
        self.redesenhar()

    # ------------------------------------------------------------------ #
    #  Conversão de coordenadas                                           #
    # ------------------------------------------------------------------ #
    def img_para_canvas(self, x: float, y: float) -> Tuple[float, float]:
        return x * self.zoom + self.ox, y * self.zoom + self.oy

    def canvas_para_img(self, cx: float, cy: float) -> Tuple[float, float]:
        return (cx - self.ox) / self.zoom, (cy - self.oy) / self.zoom

    # ------------------------------------------------------------------ #
    #  Desenho                                                            #
    # ------------------------------------------------------------------ #
    def redesenhar(self):
        self.canvas.delete("all")
        if self.pil_base is None:
            return
        self._desenhar_imagem()
        self._desenhar_area_temp()
        self._desenhar_plantulas()
        self._desenhar_pontos_temp()

    def _desenhar_imagem(self):
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        # região visível da imagem (em coordenadas de imagem)
        ix0 = max(0, int((0 - self.ox) / self.zoom))
        iy0 = max(0, int((0 - self.oy) / self.zoom))
        ix1 = min(self.img_w, int((cw - self.ox) / self.zoom) + 1)
        iy1 = min(self.img_h, int((ch - self.oy) / self.zoom) + 1)
        if ix1 <= ix0 or iy1 <= iy0:
            return
        recorte = self.pil_base.crop((ix0, iy0, ix1, iy1))
        nw = max(1, int((ix1 - ix0) * self.zoom))
        nh = max(1, int((iy1 - iy0) * self.zoom))
        metodo = Image.NEAREST if self.zoom > 1 else Image.BILINEAR
        recorte = recorte.resize((nw, nh), metodo)
        self._tk_img = ImageTk.PhotoImage(recorte)
        px = self.ox + ix0 * self.zoom
        py = self.oy + iy0 * self.zoom
        self.canvas.create_image(px, py, anchor="nw", image=self._tk_img)

    def _desenhar_plantulas(self):
        for p in self.plantulas:
            if len(p.caminho) < 2:
                continue
            sel = (p is self.selecionada)
            ie = max(0, min(p.idx_estrangulamento, len(p.caminho) - 1))
            larg = 4 if sel else 2

            pts1 = []
            for i in range(0, ie + 1):
                cx, cy = self.img_para_canvas(*p.caminho[i])
                pts1 += [cx, cy]
            if len(pts1) >= 4:
                self.canvas.create_line(*pts1, fill=COR_SEG1, width=larg,
                                        capstyle="round", joinstyle="round")
            pts2 = []
            for i in range(ie, len(p.caminho)):
                cx, cy = self.img_para_canvas(*p.caminho[i])
                pts2 += [cx, cy]
            if len(pts2) >= 4:
                self.canvas.create_line(*pts2, fill=COR_SEG2, width=larg,
                                        capstyle="round", joinstyle="round")

            # alças
            self._alca(p.topo, COR_TOPO, sel)
            self._alca(p.estrangulamento, COR_ESTR, sel)
            self._alca(p.ponta, COR_PONTA, sel)

            # rótulo
            tx, ty = self.img_para_canvas(*p.topo)
            self.canvas.create_text(tx + 10, ty - 10, text=p.rotulo or f"P{p.id}",
                                    fill="#ffffff", anchor="w",
                                    font=("Segoe UI", 10, "bold"))

    def _alca(self, ponto, cor, selecionada=False):
        if ponto is None:
            return
        cx, cy = self.img_para_canvas(*ponto)
        r = RAIO_ALCA + (2 if selecionada else 0)
        contorno = COR_SEL if selecionada else "#ffffff"
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=cor, outline=contorno, width=2)

    def _desenhar_area_temp(self):
        if self._retangulo_temp is not None:
            x, y, w, h = self._retangulo_temp
            cx0, cy0 = self.img_para_canvas(x, y)
            cx1, cy1 = self.img_para_canvas(x + w, y + h)
            self.canvas.create_rectangle(cx0, cy0, cx1, cy1,
                                         outline=COR_AREA, width=2, dash=(6, 4))

    def _desenhar_pontos_temp(self):
        if not self._pontos_temp:
            return
        # linha do traçado/calibração em andamento
        pts = []
        for (x, y) in self._pontos_temp:
            cx, cy = self.img_para_canvas(x, y)
            pts += [cx, cy]
            self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                                    fill=COR_SEL, outline="#ffffff")
        if len(pts) >= 4:
            cor = "#ffffff" if self.modo == MODO_CALIBRAR else COR_SEG2
            self.canvas.create_line(*pts, fill=cor, width=2, dash=(4, 3))

    # ------------------------------------------------------------------ #
    #  Modos                                                              #
    # ------------------------------------------------------------------ #
    def set_modo(self, modo: str):
        self.modo = modo
        self._pontos_temp = []
        self._retangulo_temp = None
        self._arrasto = None
        self._area_inicio = None
        cursores = {MODO_NAVEGAR: "arrow", MODO_CALIBRAR: "tcross",
                    MODO_AREA: "tcross", MODO_TRACAR: "pencil"}
        self.canvas.configure(cursor=cursores.get(modo, "arrow"))
        self._status_do_modo()
        self.redesenhar()

    def _status_do_modo(self):
        if not self.ao_status:
            return
        msg = {
            MODO_NAVEGAR: "Modo seleção: clique numa plântula para selecioná-la; "
                          "arraste os pontos para ajustar. Roda do mouse = zoom, "
                          "botão direito = mover.",
            MODO_CALIBRAR: "Calibração: clique em dois pontos de distância conhecida "
                           "na régua. Depois informe a distância real.",
            MODO_AREA: "Área de trabalho: arraste um retângulo sobre o papel "
                       "(dentro da caixa) para limitar a detecção.",
            MODO_TRACAR: "Traçado manual: clique ao longo do filamento, do topo até "
                         "a ponta. Pressione Enter para concluir, Esc para cancelar.",
        }.get(self.modo, "")
        self.ao_status(msg)

    # ------------------------------------------------------------------ #
    #  Eventos                                                            #
    # ------------------------------------------------------------------ #
    def _bind_eventos(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self._press1)
        c.bind("<B1-Motion>", self._move1)
        c.bind("<ButtonRelease-1>", self._release1)
        c.bind("<Double-Button-1>", self._duplo)
        # pan com botão direito (e botão do meio)
        for b in ("3", "2"):
            c.bind(f"<ButtonPress-{b}>", self._pan_press)
            c.bind(f"<B{b}-Motion>", self._pan_move)
            c.bind(f"<ButtonRelease-{b}>", self._pan_release)
        # zoom
        c.bind("<MouseWheel>", self._wheel)          # Windows / Mac
        c.bind("<Button-4>", lambda e: self._zoom_em(e.x, e.y, 1.2))   # Linux
        c.bind("<Button-5>", lambda e: self._zoom_em(e.x, e.y, 1/1.2))
        # teclas
        c.bind("<Return>", lambda e: self._concluir_tracado())
        c.bind("<Escape>", lambda e: self.set_modo(MODO_NAVEGAR))
        c.bind("<Delete>", lambda e: self._deletar_selecionada())
        c.configure(takefocus=True)
        c.bind("<Enter>", lambda e: c.focus_set())

    # ---- botão esquerdo ----
    def _press1(self, e):
        if self.pil_base is None:
            return
        ix, iy = self.canvas_para_img(e.x, e.y)

        if self.modo == MODO_NAVEGAR:
            # tentar pegar uma alça da plântula selecionada (ou de qualquer uma)
            alvo = self._alca_no_ponto(e.x, e.y)
            if alvo is not None:
                self.selecionada = alvo[0]
                self._arrasto = {"plantula": alvo[0], "tipo": alvo[1]}
                if self.ao_mudar_selecao:
                    self.ao_mudar_selecao()
                self.redesenhar()
                return
            # senão, selecionar a plântula mais próxima do clique
            p = self._plantula_no_ponto(ix, iy)
            self.selecionada = p
            if self.ao_mudar_selecao:
                self.ao_mudar_selecao()
            self.redesenhar()

        elif self.modo == MODO_CALIBRAR:
            self._pontos_temp.append((ix, iy))
            if len(self._pontos_temp) == 2:
                p1, p2 = self._pontos_temp
                self._pontos_temp = []
                if self.ao_calibrar:
                    self.ao_calibrar(p1, p2)
                self.set_modo(MODO_NAVEGAR)
            self.redesenhar()

        elif self.modo == MODO_AREA:
            self._area_inicio = (ix, iy)
            self._retangulo_temp = (ix, iy, 0, 0)

        elif self.modo == MODO_TRACAR:
            self._pontos_temp.append((ix, iy))
            self.redesenhar()

    def _move1(self, e):
        if self.pil_base is None:
            return
        ix, iy = self.canvas_para_img(e.x, e.y)

        if self.modo == MODO_NAVEGAR and self._arrasto:
            p = self._arrasto["plantula"]
            tipo = self._arrasto["tipo"]
            if tipo == "estr":
                p.mover_estrangulamento_para((ix, iy))
            elif tipo == "topo":
                if p.caminho:
                    p.caminho[0] = (ix, iy)
            elif tipo == "ponta":
                if p.caminho:
                    p.caminho[-1] = (ix, iy)
            if self.ao_editar:
                self.ao_editar()
            self.redesenhar()

        elif self.modo == MODO_AREA and self._area_inicio is not None:
            x0, y0 = self._area_inicio
            x = min(x0, ix); y = min(y0, iy)
            w = abs(ix - x0); h = abs(iy - y0)
            self._retangulo_temp = (x, y, w, h)
            self.redesenhar()

    def _release1(self, e):
        if self.modo == MODO_NAVEGAR:
            self._arrasto = None
        elif self.modo == MODO_AREA and self._retangulo_temp is not None:
            x, y, w, h = self._retangulo_temp
            if w > 10 and h > 10 and self.ao_definir_area:
                self.ao_definir_area(int(x), int(y), int(w), int(h))
            self.set_modo(MODO_NAVEGAR)

    def _duplo(self, e):
        if self.modo == MODO_TRACAR:
            self._concluir_tracado()

    def _concluir_tracado(self):
        if self.modo == MODO_TRACAR and len(self._pontos_temp) >= 2:
            caminho = list(self._pontos_temp)
            self._pontos_temp = []
            if self.ao_criar_plantula:
                self.ao_criar_plantula(caminho)
            self.set_modo(MODO_NAVEGAR)

    def _deletar_selecionada(self):
        if self.selecionada is not None and self.selecionada in self.plantulas:
            self.plantulas.remove(self.selecionada)
            self.selecionada = None
            if self.ao_mudar_selecao:
                self.ao_mudar_selecao()
            if self.ao_editar:
                self.ao_editar()
            self.redesenhar()

    # ---- pan ----
    def _pan_press(self, e):
        self._pan_inicio = (e.x, e.y)
        self.canvas.configure(cursor="fleur")

    def _pan_move(self, e):
        if self._pan_inicio is None:
            return
        dx = e.x - self._pan_inicio[0]
        dy = e.y - self._pan_inicio[1]
        self._pan_inicio = (e.x, e.y)
        self.ox += dx
        self.oy += dy
        self.redesenhar()

    def _pan_release(self, e):
        self._pan_inicio = None
        cursores = {MODO_NAVEGAR: "arrow", MODO_CALIBRAR: "tcross",
                    MODO_AREA: "tcross", MODO_TRACAR: "pencil"}
        self.canvas.configure(cursor=cursores.get(self.modo, "arrow"))

    # ---- zoom ----
    def _wheel(self, e):
        fator = 1.2 if e.delta > 0 else 1 / 1.2
        self._zoom_em(e.x, e.y, fator)

    def _zoom_em(self, cx, cy, fator):
        if self.pil_base is None:
            return
        novo = self.zoom * fator
        novo = max(0.02, min(8.0, novo))
        fator = novo / self.zoom
        # manter o ponto sob o cursor fixo
        self.ox = cx - (cx - self.ox) * fator
        self.oy = cy - (cy - self.oy) * fator
        self.zoom = novo
        self.redesenhar()

    # ------------------------------------------------------------------ #
    #  Utilidades de seleção                                              #
    # ------------------------------------------------------------------ #
    def _alca_no_ponto(self, cx, cy):
        """Retorna (plantula, tipo) se houver uma alça perto de (cx,cy) na tela."""
        candidatos = []
        ordem = ([self.selecionada] if self.selecionada else []) + \
                [p for p in self.plantulas if p is not self.selecionada]
        for p in ordem:
            if not p or len(p.caminho) < 2:
                continue
            for tipo, ponto in (("topo", p.topo), ("estr", p.estrangulamento),
                                ("ponta", p.ponta)):
                hx, hy = self.img_para_canvas(*ponto)
                d = (hx - cx) ** 2 + (hy - cy) ** 2
                if d <= TOLERANCIA_CLIQUE ** 2:
                    candidatos.append((d, p, tipo))
        if not candidatos:
            return None
        candidatos.sort(key=lambda t: t[0])
        return candidatos[0][1], candidatos[0][2]

    def _plantula_no_ponto(self, ix, iy, tol_px=25):
        """Retorna a plântula cujo caminho passa mais perto de (ix,iy) na imagem."""
        melhor, melhor_d = None, (tol_px / max(self.zoom, 1e-6)) ** 2
        for p in self.plantulas:
            for (x, y) in p.caminho:
                d = (x - ix) ** 2 + (y - iy) ** 2
                if d < melhor_d:
                    melhor_d = d
                    melhor = p
        return melhor
