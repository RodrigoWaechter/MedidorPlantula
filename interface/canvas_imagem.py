"""
Canvas interativo da interface gráfica.

Responsável por exibir a imagem com zoom e pan, desenhar as plântulas,
e gerenciar os modos de interação: calibração, traçado manual e edição
de pontos (arrastar topo, estrangulamento e ponta).

A conversão entre coordenadas de tela e da imagem original fica centralizada
em `img_para_canvas` e `canvas_para_img`.
"""

from __future__ import annotations
from typing import Callable, List, Optional, Tuple
import tkinter as tk
from PIL import Image, ImageTk

from nucleo.modelos import Plantula

MODO_NAVEGAR = "navegar"
MODO_CALIBRAR = "calibrar"
MODO_AREA = "area"
MODO_TRACAR = "tracar"

# Cores dos elementos desenhados (hexadecimal, padrão Tkinter)
COR_SEG1 = "#3cb43c"   # verde  - hipocótilo
COR_SEG2 = "#2882e6"   # azul   - raiz
COR_TOPO = "#e60000"   # vermelho
COR_ESTR = "#c800c8"   # magenta - estrangulamento
COR_PONTA = "#e6c800"  # amarelo
COR_SEL = "#ff8000"    # laranja - seleção / traçado em andamento
COR_AREA = "#00b0b0"   # ciano  - área de trabalho

RAIO_ALCA = 6           # raio dos pontos de controle em pixels de tela
TOLERANCIA_CLIQUE = 12  # distância máxima (px de tela) para "pegar" um ponto

# Máscara do modificador Shift nos eventos do Tkinter (event.state)
SHIFT_MASK = 0x0001


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

        # imagem base e parâmetros de visualização
        self.pil_base: Optional[Image.Image] = None
        self.img_w = 0
        self.img_h = 0
        self.zoom = 1.0
        self.ox = 0.0   # offset em pixels de tela: onde o pixel (0,0) da imagem aparece
        self.oy = 0.0
        self._tk_img = None  # mantém referência viva para o Tkinter não descartar

        # modo de interação e estado do traçado
        self.modo = MODO_NAVEGAR
        self.plantulas: List[Plantula] = []
        self.selecionada: Optional[Plantula] = None
        self._precisa_ajustar = False

        self._pan_inicio = None   # ponto inicial do pan com botão direito
        self._arrasto = None      # alça sendo arrastada no modo navegar
        self._pontos_temp: List[Tuple[float, float]] = []  # pontos do traçado em andamento
        self._idx_estr_temp: Optional[int] = None  # índice marcado como estrangulamento durante o traçado
        self._retangulo_temp = None  # retângulo da área de trabalho sendo desenhado
        self._area_inicio = None
        self._mouse_canvas: Optional[Tuple[float, float]] = None  # posição atual do mouse
        self._plantula_editando: Optional[Plantula] = None  # plântula reaberta para edição

        # callbacks definidos pela janela principal
        self.ao_calibrar: Optional[Callable] = None
        self.ao_definir_area: Optional[Callable] = None
        self.ao_criar_plantula: Optional[Callable] = None
        self.ao_reabrir_plantula: Optional[Callable] = None
        self.ao_mudar_selecao: Optional[Callable] = None
        self.ao_editar: Optional[Callable] = None
        self.ao_status: Optional[Callable] = None

        self._bind_eventos()

    def definir_imagem(self, pil_image: Image.Image):
        self.pil_base = pil_image.convert("RGB")
        self.img_w, self.img_h = self.pil_base.size
        self.selecionada = None
        self._precisa_ajustar = True
        self.after(50, self._tentar_ajuste_inicial)

    def _tentar_ajuste_inicial(self):
        """Espera o canvas ter tamanho definido antes de ajustar o zoom inicial."""
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
        # centraliza a imagem no canvas
        self.ox = (cw - self.img_w * self.zoom) / 2
        self.oy = (ch - self.img_h * self.zoom) / 2
        self.redesenhar()

    def img_para_canvas(self, x: float, y: float) -> Tuple[float, float]:
        """Converte coordenadas da imagem original para pixels de tela."""
        return x * self.zoom + self.ox, y * self.zoom + self.oy

    def canvas_para_img(self, cx: float, cy: float) -> Tuple[float, float]:
        """Converte pixels de tela para coordenadas da imagem original."""
        return (cx - self.ox) / self.zoom, (cy - self.oy) / self.zoom

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
        # recorta apenas a região visível para não renderizar a imagem inteira
        ix0 = max(0, int((0 - self.ox) / self.zoom))
        iy0 = max(0, int((0 - self.oy) / self.zoom))
        ix1 = min(self.img_w, int((cw - self.ox) / self.zoom) + 1)
        iy1 = min(self.img_h, int((ch - self.oy) / self.zoom) + 1)
        if ix1 <= ix0 or iy1 <= iy0:
            return
        recorte = self.pil_base.crop((ix0, iy0, ix1, iy1))
        nw = max(1, int((ix1 - ix0) * self.zoom))
        nh = max(1, int((iy1 - iy0) * self.zoom))
        # NEAREST preserva pixels nítidos ao ampliar; BILINEAR suaviza ao reduzir
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
            larg = 4 if sel else 2  # plântula selecionada aparece mais grossa

            # segmento 1: topo → estrangulamento (verde)
            pts1 = []
            for i in range(0, ie + 1):
                cx, cy = self.img_para_canvas(*p.caminho[i])
                pts1 += [cx, cy]
            if len(pts1) >= 4:
                self.canvas.create_line(*pts1, fill=COR_SEG1, width=larg,
                                        capstyle="round", joinstyle="round")

            # segmento 2: estrangulamento → ponta (azul)
            pts2 = []
            for i in range(ie, len(p.caminho)):
                cx, cy = self.img_para_canvas(*p.caminho[i])
                pts2 += [cx, cy]
            if len(pts2) >= 4:
                self.canvas.create_line(*pts2, fill=COR_SEG2, width=larg,
                                        capstyle="round", joinstyle="round")

            # pontos de controle arrastáveis
            self._alca(p.topo, COR_TOPO, sel)
            self._alca(p.estrangulamento, COR_ESTR, sel)
            self._alca(p.ponta, COR_PONTA, sel)

            tx, ty = self.img_para_canvas(*p.topo)
            self.canvas.create_text(tx + 10, ty - 10, text=p.rotulo or f"P{p.id}",
                                    fill="#ffffff", anchor="w",
                                    font=("Segoe UI", 10, "bold"))

    def _alca(self, ponto, cor, selecionada=False):
        """Desenha um ponto de controle circular (alça) na posição dada."""
        if ponto is None:
            return
        cx, cy = self.img_para_canvas(*ponto)
        r = RAIO_ALCA + (2 if selecionada else 0)
        contorno = COR_SEL if selecionada else "#ffffff"
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=cor, outline=contorno, width=2)

    def _desenhar_area_temp(self):
        """Desenha o retângulo da área de trabalho enquanto está sendo definido."""
        if self._retangulo_temp is not None:
            x, y, w, h = self._retangulo_temp
            cx0, cy0 = self.img_para_canvas(x, y)
            cx1, cy1 = self.img_para_canvas(x + w, y + h)
            self.canvas.create_rectangle(cx0, cy0, cx1, cy1,
                                         outline=COR_AREA, width=2, dash=(6, 4))

    def _desenhar_pontos_temp(self):
        """
        Desenha os pontos já clicados no traçado em andamento e uma linha guia
        do último ponto até o cursor, para indicar o próximo trecho antes de clicar.

        Se um ponto de estrangulamento já foi marcado (Shift+clique), o traçado
        aparece dividido ao vivo: verde até o estrangulamento e azul depois dele,
        com a marca em magenta. Assim os dois segmentos ficam visíveis na hora,
        sem precisar conferir só no fim.
        """
        if not self._pontos_temp:
            return
        pts = [self.img_para_canvas(x, y) for (x, y) in self._pontos_temp]

        tem_marca = (self.modo == MODO_TRACAR and self._idx_estr_temp is not None)
        if tem_marca:
            ie = max(0, min(self._idx_estr_temp, len(pts) - 1))
            # segmento 1: topo -> estrangulamento (verde)
            if ie >= 1:
                seg1 = [c for p in pts[:ie + 1] for c in p]
                self.canvas.create_line(*seg1, fill=COR_SEG1, width=2, dash=(4, 3))
            # segmento 2: estrangulamento -> ponta (azul)
            if ie <= len(pts) - 2:
                seg2 = [c for p in pts[ie:] for c in p]
                self.canvas.create_line(*seg2, fill=COR_SEG2, width=2, dash=(4, 3))
        else:
            flat = [c for p in pts for c in p]
            if len(flat) >= 4:
                cor = "#ffffff" if self.modo == MODO_CALIBRAR else COR_SEG2
                self.canvas.create_line(*flat, fill=cor, width=2, dash=(4, 3))

        # pontos clicados; o ponto marcado aparece maior e em magenta
        for i, (cx, cy) in enumerate(pts):
            if tem_marca and i == self._idx_estr_temp:
                r = RAIO_ALCA
                self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                        fill=COR_ESTR, outline="#ffffff", width=2)
            else:
                self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                                        fill=COR_SEL, outline="#ffffff")

        # linha guia até o cursor
        if self._mouse_canvas and self.modo in (MODO_TRACAR, MODO_CALIBRAR):
            ux, uy = self.img_para_canvas(*self._pontos_temp[-1])
            mx, my = self._mouse_canvas
            self.canvas.create_line(ux, uy, mx, my,
                                    fill="#aaaaaa", width=1, dash=(3, 4))

    def set_modo(self, modo: str):
        """Muda o modo de interação e reinicia o estado temporário."""
        self.modo = modo
        self._pontos_temp = []
        self._idx_estr_temp = None
        self._retangulo_temp = None
        self._arrasto = None
        self._area_inicio = None
        self._plantula_editando = None
        cursores = {MODO_NAVEGAR: "arrow", MODO_CALIBRAR: "tcross",
                    MODO_AREA: "tcross", MODO_TRACAR: "pencil"}
        self.canvas.configure(cursor=cursores.get(modo, "arrow"))
        self._status_do_modo()
        self.redesenhar()

    def _status_do_modo(self):
        """Atualiza a barra de status com a instrução do modo atual."""
        if not self.ao_status:
            return
        msg = {
            MODO_NAVEGAR: "Modo seleção: clique numa plântula para selecioná-la; "
                          "arraste os pontos para ajustar. Setas ← → movem o "
                          "estrangulamento entre os nós. Roda do mouse = zoom, "
                          "botão direito = mover.",
            MODO_CALIBRAR: "Calibração: clique em dois pontos de distância conhecida "
                           "na régua. Depois informe a distância real.",
            MODO_AREA: "Área de trabalho: arraste um retângulo sobre o papel "
                       "(dentro da caixa) para limitar a detecção.",
            MODO_TRACAR: "Medição manual: clique ao longo do filamento, do topo até "
                         "a ponta. No ponto de estrangulamento, segure Shift e clique "
                         "(fica magenta). Enter para concluir, Esc para cancelar.",
        }.get(self.modo, "")
        self.ao_status(msg)

    def _bind_eventos(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self._press1)
        c.bind("<B1-Motion>", self._move1)
        c.bind("<ButtonRelease-1>", self._release1)
        c.bind("<Double-Button-1>", self._duplo)
        c.bind("<Motion>", self._motion)
        # pan: botão direito ou do meio
        for b in ("3", "2"):
            c.bind(f"<ButtonPress-{b}>", self._pan_press)
            c.bind(f"<B{b}-Motion>", self._pan_move)
            c.bind(f"<ButtonRelease-{b}>", self._pan_release)
        # zoom: Windows/Mac usa delta; Linux usa Button-4/5
        c.bind("<MouseWheel>", self._wheel)
        c.bind("<Button-4>", lambda e: self._zoom_em(e.x, e.y, 1.2))
        c.bind("<Button-5>", lambda e: self._zoom_em(e.x, e.y, 1/1.2))
        c.bind("<Return>", lambda e: self._concluir_tracado())
        c.bind("<Escape>", lambda e: self.set_modo(MODO_NAVEGAR))
        c.bind("<Delete>", lambda e: self._deletar_selecionada())
        # setas movem o estrangulamento da plântula selecionada entre os nós
        c.bind("<Left>", lambda e: self._passo_estrangulamento(-1))
        c.bind("<Up>", lambda e: self._passo_estrangulamento(-1))
        c.bind("<Right>", lambda e: self._passo_estrangulamento(1))
        c.bind("<Down>", lambda e: self._passo_estrangulamento(1))
        c.configure(takefocus=True)
        c.bind("<Enter>", lambda e: c.focus_set())

    def _motion(self, e):
        """Atualiza a posição do mouse e redesenha a linha guia durante o traçado."""
        self._mouse_canvas = (e.x, e.y)
        if self.modo in (MODO_TRACAR, MODO_CALIBRAR) and self._pontos_temp:
            self.redesenhar()

    def _press1(self, e):
        if self.pil_base is None:
            return
        ix, iy = self.canvas_para_img(e.x, e.y)

        if self.modo == MODO_NAVEGAR:
            # tenta pegar uma alça (topo, estrangulamento ou ponta)
            alvo = self._alca_no_ponto(e.x, e.y)
            if alvo is not None:
                self.selecionada = alvo[0]
                self._arrasto = {"plantula": alvo[0], "tipo": alvo[1]}
                if self.ao_mudar_selecao:
                    self.ao_mudar_selecao()
                self.redesenhar()
                return
            # tenta clicar no traço de uma plântula para reabrir o traçado
            p = self._plantula_no_ponto(ix, iy)
            if p is not None:
                self._reabrir_tracado(p, (ix, iy))
                return
            # clique em área vazia: deseleciona
            self.selecionada = None
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
            # Shift pressionado: este ponto marca o estrangulamento (transição
            # hipocótilo/raiz). Um novo Shift+clique mais adiante reposiciona a marca.
            if e.state & SHIFT_MASK:
                self._idx_estr_temp = len(self._pontos_temp) - 1
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

    def _reabrir_tracado(self, plantula: Plantula, ponto_img: Tuple[float, float]):
        """
        Reabre o traçado de uma plântula a partir do ponto mais próximo do clique,
        descartando todos os pontos depois dele. O usuário pode então continuar
        clicando normalmente para corrigir o trecho errado.
        """
        if not plantula.caminho:
            return
        melhor_i, melhor_d = 0, float("inf")
        for i, (x, y) in enumerate(plantula.caminho):
            d = (x - ponto_img[0]) ** 2 + (y - ponto_img[1]) ** 2
            if d < melhor_d:
                melhor_d, melhor_i = d, i
        # precisa ter pelo menos 1 ponto antes do corte para formar um traço válido
        if melhor_i == 0:
            return
        plantula.caminho = plantula.caminho[:melhor_i + 1]
        plantula.idx_estrangulamento = min(plantula.idx_estrangulamento,
                                           len(plantula.caminho) - 1)
        self._plantula_editando = plantula
        self.selecionada = plantula
        self._pontos_temp = list(plantula.caminho)
        # preserva a marca de estrangulamento se ela ainda estiver no trecho mantido
        ie = plantula.idx_estrangulamento
        self._idx_estr_temp = ie if 0 < ie < len(self._pontos_temp) - 1 else None
        self.modo = MODO_TRACAR
        self.canvas.configure(cursor="pencil")
        self._status_do_modo()
        self.redesenhar()

    def _concluir_tracado(self):
        if self.modo != MODO_TRACAR or len(self._pontos_temp) < 2:
            return
        caminho = list(self._pontos_temp)
        idx_estr = self._idx_estr_temp
        if idx_estr is not None:
            idx_estr = max(0, min(idx_estr, len(caminho) - 1))
        self._pontos_temp = []
        self._idx_estr_temp = None
        if self._plantula_editando is not None:
            # atualiza a plântula existente em vez de criar uma nova
            self._plantula_editando.caminho = caminho
            self._plantula_editando = None
            if self.ao_reabrir_plantula:
                self.ao_reabrir_plantula(idx_estr)
        else:
            if self.ao_criar_plantula:
                self.ao_criar_plantula(caminho, idx_estr)
        self.set_modo(MODO_NAVEGAR)

    def _passo_estrangulamento(self, delta):
        """Move o estrangulamento da plântula selecionada delta nós (±1)."""
        p = self.selecionada
        if self.modo != MODO_NAVEGAR or p is None or len(p.caminho) < 2:
            return
        novo = max(0, min(p.idx_estrangulamento + delta, len(p.caminho) - 1))
        if novo != p.idx_estrangulamento:
            p.idx_estrangulamento = novo
            if self.ao_editar:
                self.ao_editar()
            self.redesenhar()

    def _deletar_selecionada(self):
        if self.selecionada is not None and self.selecionada in self.plantulas:
            self.plantulas.remove(self.selecionada)
            self.selecionada = None
            if self.ao_mudar_selecao:
                self.ao_mudar_selecao()
            if self.ao_editar:
                self.ao_editar()
            self.redesenhar()

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

    def _wheel(self, e):
        fator = 1.2 if e.delta > 0 else 1 / 1.2
        self._zoom_em(e.x, e.y, fator)

    def _zoom_em(self, cx, cy, fator):
        if self.pil_base is None:
            return
        novo = self.zoom * fator
        novo = max(0.02, min(8.0, novo))
        fator = novo / self.zoom
        # mantém o ponto sob o cursor fixo durante o zoom
        self.ox = cx - (cx - self.ox) * fator
        self.oy = cy - (cy - self.oy) * fator
        self.zoom = novo
        self.redesenhar()

    def _alca_no_ponto(self, cx, cy):
        """Retorna (plantula, tipo) se houver uma alça perto de (cx, cy) na tela."""
        candidatos = []
        # prioriza as alças da plântula selecionada
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
        """Retorna a plântula cujo caminho passa mais perto de (ix, iy) na imagem."""
        # a tolerância em pixels de imagem depende do zoom atual
        melhor, melhor_d = None, (tol_px / max(self.zoom, 1e-6)) ** 2
        for p in self.plantulas:
            for (x, y) in p.caminho:
                d = (x - ix) ** 2 + (y - iy) ** 2
                if d < melhor_d:
                    melhor_d = d
                    melhor = p
        return melhor