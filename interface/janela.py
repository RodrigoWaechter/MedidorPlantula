"""
Janela principal da interface gráfica.

Reúne a barra de ferramentas, o canvas interativo e o painel de resultados,
e coordena as ações: abrir imagem, calibrar, medir manualmente, ajustar e exportar.
"""

from __future__ import annotations
import math
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image

from nucleo import imagem as nimg
from nucleo import exportar, tracado
from nucleo.modelos import Projeto, Calibracao

from interface.canvas_imagem import (
    CanvasImagem, MODO_NAVEGAR, MODO_CALIBRAR, MODO_AREA, MODO_TRACAR,
)


class Aplicacao(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Medidor de Plântulas")
        self.geometry("1200x780")
        self.minsize(900, 600)

        self.projeto = Projeto()
        self.img_bgr = None
        self.roi_retangulo = None

        self._construir_estilo()
        self._construir_barra()
        self._construir_corpo()
        self._construir_status()
        self._ligar_callbacks()

        self.bind_all("<Control-o>", lambda e: self.abrir_imagem())

    def _construir_estilo(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Treeview", rowheight=24)
        s.configure("Toolbutton", padding=6)

    def _construir_barra(self):
        barra = tk.Frame(self, bg="#e8e8e8", padx=6, pady=6)
        barra.grid(row=0, column=0, columnspan=2, sticky="ew")

        def botao(txt, cmd):
            b = tk.Button(barra, text=txt, command=cmd, relief="groove",
                          bg="#fafafa", padx=8, pady=4)
            b.pack(side="left", padx=2)
            return b

        def sep():
            tk.Frame(barra, width=2, bg="#bbbbbb").pack(side="left", fill="y",
                                                        padx=6, pady=2)

        botao("Abrir imagem", self.abrir_imagem)
        sep()
        botao("Calibrar escala", lambda: self._set_modo(MODO_CALIBRAR))
        sep()
        botao("Medir manualmente", lambda: self._set_modo(MODO_TRACAR))
        botao("Sugerir estrangulamento", self.sugerir_estrangulamento)
        botao("Remover", self.remover_selecionada)
        sep()
        botao("Exportar CSV", self.exportar_csv)
        botao("Exportar imagem", self.exportar_imagem)

    def _construir_corpo(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self.canvas = CanvasImagem(self)
        self.canvas.grid(row=1, column=0, sticky="nsew")

        painel = tk.Frame(self, width=300, bg="#f4f4f4")
        painel.grid(row=1, column=1, sticky="ns")
        painel.grid_propagate(False)

        tk.Label(painel, text="Resultados", bg="#f4f4f4",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 4))

        cols = ("rotulo", "seg1", "seg2", "total")
        self.tabela = ttk.Treeview(painel, columns=cols, show="headings", height=18)
        self.tabela.heading("rotulo", text="Plântula")
        self.tabela.heading("seg1", text="Seg1")
        self.tabela.heading("seg2", text="Seg2")
        self.tabela.heading("total", text="Total")
        self.tabela.column("rotulo", width=70, anchor="center")
        self.tabela.column("seg1", width=70, anchor="e")
        self.tabela.column("seg2", width=70, anchor="e")
        self.tabela.column("total", width=70, anchor="e")
        self.tabela.pack(fill="both", expand=True, padx=10)
        self.tabela.bind("<<TreeviewSelect>>", self._selecionar_na_tabela)

        self.lbl_calib = tk.Label(painel, text="Escala: não calibrada",
                                  bg="#f4f4f4", fg="#a05000", justify="left",
                                  wraplength=280)
        self.lbl_calib.pack(anchor="w", padx=10, pady=(8, 2))

        self.lbl_resumo = tk.Label(painel, text="0 plântula(s)", bg="#f4f4f4")
        self.lbl_resumo.pack(anchor="w", padx=10, pady=(0, 10))

        leg = tk.Frame(painel, bg="#f4f4f4")
        leg.pack(anchor="w", padx=10, pady=(0, 10))
        for cor, txt in [("#3cb43c", "Segmento 1 (hipocótilo)"),
                         ("#2882e6", "Segmento 2 (raiz)"),
                         ("#e60000", "Topo"), ("#c800c8", "Estrangulamento"),
                         ("#e6c800", "Ponta")]:
            linha = tk.Frame(leg, bg="#f4f4f4")
            linha.pack(anchor="w", pady=1)
            tk.Canvas(linha, width=14, height=14, bg=cor,
                      highlightthickness=0).pack(side="left", padx=(0, 6))
            tk.Label(linha, text=txt, bg="#f4f4f4",
                     font=("Segoe UI", 9)).pack(side="left")

    def _construir_status(self):
        self.var_status = tk.StringVar(
            value="Abra uma imagem, calibre a escala pela régua e meça manualmente.")
        self.status = tk.Label(self, textvariable=self.var_status, anchor="w",
                               bg="#dcdcdc", padx=8, pady=4)
        self.status.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _ligar_callbacks(self):
        self.canvas.ao_calibrar = self._ao_calibrar
        self.canvas.ao_definir_area = self._ao_definir_area
        self.canvas.ao_criar_plantula = self._ao_criar_plantula
        self.canvas.ao_reabrir_plantula = self._ao_reabrir_plantula
        self.canvas.ao_mudar_selecao = self._ao_mudar_selecao
        self.canvas.ao_editar = self._ao_editar
        self.canvas.ao_status = self.var_status.set

    def abrir_imagem(self):
        cam = filedialog.askopenfilename(
            title="Escolher imagem",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff "
                                    "*.heic *.heif *.webp"),
                       ("Todos os arquivos", "*.*")])
        if not cam:
            return
        try:
            self.img_bgr = nimg.carregar_bgr(cam)
        except nimg.ErroImagem as e:
            messagebox.showerror("Não foi possível abrir", str(e))
            return

        rgb = self.img_bgr[:, :, ::-1]  # BGR -> RGB para o Pillow
        pil = Image.fromarray(rgb)
        self.projeto = Projeto(caminho_imagem=cam)
        self.roi_retangulo = None
        self.canvas.definir_imagem(pil)
        self.canvas.definir_plantulas(self.projeto.plantulas)
        self._atualizar_tabela()
        self._atualizar_calibracao_label()
        self.var_status.set(
            f"Imagem aberta: {os.path.basename(cam)}. "
            "Calibre a escala pela régua e use Medir manualmente em cada plântula.")

    def sugerir_estrangulamento(self):
        if self.img_bgr is None:
            messagebox.showinfo("Sem imagem", "Abra uma imagem primeiro.")
            return
        plantula = self.canvas.selecionada
        if plantula is None:
            messagebox.showinfo("Selecione uma plântula",
                                "Trace ou selecione uma plântula manual antes.")
            return
        if self._aplicar_sugestao_estrangulamento(plantula):
            self.canvas.redesenhar()
            self._atualizar_tabela()
            self.var_status.set(
                "Estrangulamento sugerido automaticamente. Confira o ponto magenta "
                "e arraste se precisar ajustar.")
        else:
            messagebox.showinfo("Traçado insuficiente",
                                "Trace ao menos dois pontos da plântula antes.")

    def _aplicar_sugestao_estrangulamento(self, plantula):
        amostras, mapa = self._amostrar_caminho(plantula.caminho)
        if len(amostras) < 4:
            return False

        import cv2
        gray = cv2.cvtColor(self.img_bgr, cv2.COLOR_BGR2GRAY)
        idx_amostra = tracado.localizar_estrangulamento(amostras, gray)
        idx_amostra = max(0, min(idx_amostra, len(mapa) - 1))
        seg_i, t, x, y = mapa[idx_amostra]

        # posiciona o estrangulamento num ponto existente ou insere um novo
        # ponto interpolado quando cai no meio de um segmento
        if t <= 0.2:
            plantula.idx_estrangulamento = seg_i
        elif t >= 0.8:
            plantula.idx_estrangulamento = min(seg_i + 1, len(plantula.caminho) - 1)
        else:
            plantula.caminho.insert(seg_i + 1, (x, y))
            plantula.idx_estrangulamento = seg_i + 1
        return True

    def _amostrar_caminho(self, caminho):
        """
        Interpola pontos ao longo do caminho a cada ~2 pixels, devolvendo
        uma lista de (y, x) para o detector e um mapa de volta ao caminho original.
        """
        if self.img_bgr is None or len(caminho) < 2:
            return [], []

        h, w = self.img_bgr.shape[:2]
        amostras = []
        mapa = []
        for i in range(len(caminho) - 1):
            ax, ay = caminho[i]
            bx, by = caminho[i + 1]
            dist = math.hypot(bx - ax, by - ay)
            passos = max(1, int(math.ceil(dist / 2.0)))
            inicio = 0 if i == 0 else 1
            for s in range(inicio, passos + 1):
                t = s / passos
                x = ax + (bx - ax) * t
                y = ay + (by - ay) * t
                px = max(0, min(w - 1, int(round(x))))
                py = max(0, min(h - 1, int(round(y))))
                amostras.append((py, px))
                mapa.append((i, t, x, y))
        return amostras, mapa

    def remover_selecionada(self):
        self.canvas._deletar_selecionada()

    def _set_modo(self, modo):
        if self.img_bgr is None:
            messagebox.showinfo("Sem imagem", "Abra uma imagem primeiro.")
            return
        self.canvas.set_modo(modo)

    def _ao_calibrar(self, p1, p2):
        d_px = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if d_px < 2:
            messagebox.showwarning("Calibração",
                                   "Os dois pontos estão muito próximos. Tente de novo.")
            return
        dlg = DialogoCalibracao(self, d_px)
        self.wait_window(dlg)
        if dlg.resultado is None:
            self.var_status.set("Calibração cancelada.")
            return
        distancia, unidade = dlg.resultado
        self.projeto.calibracao = Calibracao(p1=p1, p2=p2,
                                             distancia_real=distancia,
                                             unidade=unidade)
        self._atualizar_calibracao_label()
        self._atualizar_tabela()
        self.var_status.set("Escala calibrada com sucesso.")

    def _ao_definir_area(self, x, y, w, h):
        self.roi_retangulo = (x, y, w, h)
        self.var_status.set("Área de trabalho definida.")

    def _ao_criar_plantula(self, caminho):
        p = self.projeto.adicionar_plantula(caminho, idx_estrang=0,
                                            automatica=False)
        sugerido = self._aplicar_sugestao_estrangulamento(p)
        self.projeto.renumerar()
        self.canvas.definir_plantulas(self.projeto.plantulas)
        self.canvas.selecionada = p
        self._atualizar_tabela()
        self._ao_mudar_selecao()
        if sugerido:
            self.var_status.set(
                "Plântula medida manualmente. O ponto magenta foi sugerido; "
                "arraste-o se precisar corrigir o estrangulamento.")
        else:
            self.var_status.set(
                "Plântula medida manualmente. Arraste o ponto magenta para o "
                "estrangulamento, onde está a semente.")

    def _ao_reabrir_plantula(self):
        """Chamado quando o usuário reabre e re-finaliza o traçado de uma plântula."""
        plantula = self.canvas.selecionada
        if plantula is not None:
            self._aplicar_sugestao_estrangulamento(plantula)
        self.canvas.redesenhar()
        self._atualizar_tabela()
        self.var_status.set(
            "Traçado corrigido. Confira o ponto magenta e arraste se precisar ajustar.")

    def _ao_mudar_selecao(self):
        sel = self.canvas.selecionada
        self.tabela.selection_remove(self.tabela.selection())
        if sel is not None:
            iid = str(id(sel))
            if self.tabela.exists(iid):
                self.tabela.selection_set(iid)
                self.tabela.see(iid)

    def _ao_editar(self):
        self._atualizar_tabela()

    def _selecionar_na_tabela(self, _evt):
        sel = self.tabela.selection()
        if not sel:
            return
        alvo = None
        for p in self.projeto.plantulas:
            if str(id(p)) == sel[0]:
                alvo = p
                break
        if alvo is not None and alvo is not self.canvas.selecionada:
            self.canvas.selecionada = alvo
            self.canvas.redesenhar()

    def _atualizar_tabela(self):
        cal = self.projeto.calibracao
        unidade = cal.unidade if cal.definida else "px"
        self.tabela.heading("seg1", text=f"Seg1 ({unidade})")
        self.tabela.heading("seg2", text=f"Seg2 ({unidade})")
        self.tabela.heading("total", text=f"Total ({unidade})")

        self.tabela.delete(*self.tabela.get_children())
        for p in self.projeto.plantulas:
            m = p.medidas(cal)
            self.tabela.insert(
                "", "end", iid=str(id(p)),
                values=(m["rotulo"], f"{m['seg1']:.1f}", f"{m['seg2']:.1f}",
                        f"{m['total']:.1f}"))
        self.lbl_resumo.config(text=f"{len(self.projeto.plantulas)} plântula(s)")

    def _atualizar_calibracao_label(self):
        cal = self.projeto.calibracao
        if cal.definida:
            ppu = cal.px_por_unidade
            self.lbl_calib.config(
                text=f"Escala: {ppu:.1f} px/{cal.unidade}  "
                     f"({cal.distancia_real:g} {cal.unidade} de referência)",
                fg="#006000")
        else:
            self.lbl_calib.config(text="Escala: não calibrada (medidas em pixels)",
                                  fg="#a05000")

    def exportar_csv(self):
        if not self.projeto.plantulas:
            messagebox.showinfo("Nada a exportar", "Não há plântulas medidas.")
            return
        if not self.projeto.calibracao.definida:
            messagebox.showinfo(
                "Escala não calibrada",
                "Calibre a escala usando a régua da imagem antes de exportar "
                "as medidas em cm ou mm.")
            return
        cam = filedialog.asksaveasfilename(
            title="Salvar tabela CSV", defaultextension=".csv",
            initialfile=self._nome_saida("medidas.csv"),
            filetypes=[("CSV", "*.csv")])
        if not cam:
            return
        try:
            exportar.exportar_csv(cam, self.projeto.plantulas,
                                  self.projeto.calibracao)
            self.var_status.set(f"Tabela salva: {cam}")
        except Exception as e:
            messagebox.showerror("Erro ao salvar", str(e))

    def exportar_imagem(self):
        if self.img_bgr is None or not self.projeto.plantulas:
            messagebox.showinfo("Nada a exportar",
                                "Abra uma imagem e meça as plântulas primeiro.")
            return
        cam = filedialog.asksaveasfilename(
            title="Salvar imagem anotada", defaultextension=".png",
            initialfile=self._nome_saida("anotada.png"),
            filetypes=[("Imagem PNG", "*.png"), ("JPEG", "*.jpg")])
        if not cam:
            return
        try:
            exportar.exportar_imagem(cam, self.img_bgr, self.projeto.plantulas,
                                     self.projeto.calibracao)
            self.var_status.set(f"Imagem salva: {cam}")
        except Exception as e:
            messagebox.showerror("Erro ao salvar", str(e))

    def _nome_saida(self, sufixo):
        if self.projeto.caminho_imagem:
            base = os.path.splitext(os.path.basename(self.projeto.caminho_imagem))[0]
            return f"{base}_{sufixo}"
        return sufixo


class DialogoCalibracao(tk.Toplevel):
    """Pede a distância real entre os dois pontos clicados e a unidade."""
    def __init__(self, parent, distancia_px):
        super().__init__(parent)
        self.withdraw()
        self.title("Calibrar escala")
        self.resizable(False, False)
        self.resultado = None
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        tk.Label(self, text=f"Você marcou uma distância de {distancia_px:.0f} pixels.",
                 padx=14).grid(row=0, column=0, columnspan=3, sticky="w",
                               pady=(14, 4))
        tk.Label(self, text="Qual a distância real correspondente?",
                 padx=14).grid(row=1, column=0, columnspan=3, sticky="w")

        self.var_valor = tk.StringVar(value="10")
        self.var_unidade = tk.StringVar(value="cm")
        self.ent_valor = tk.Entry(self, textvariable=self.var_valor, width=10)
        self.ent_valor.grid(row=2, column=0, padx=(14, 4), pady=10, sticky="w")
        tk.Radiobutton(self, text="cm", variable=self.var_unidade,
                       value="cm").grid(row=2, column=1)
        tk.Radiobutton(self, text="mm", variable=self.var_unidade,
                       value="mm").grid(row=2, column=2, padx=(0, 14))

        botoes = tk.Frame(self)
        botoes.grid(row=3, column=0, columnspan=3, pady=(0, 12))
        tk.Button(botoes, text="Cancelar", width=10,
                  command=self._cancelar).pack(side="right", padx=6)
        tk.Button(botoes, text="OK", width=10,
                  command=self._ok).pack(side="right")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancelar())
        self._mostrar_modal(parent)

    def _mostrar_modal(self, parent):
        self.update_idletasks()
        parent.update_idletasks()
        largura = self.winfo_reqwidth()
        altura = self.winfo_reqheight()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - largura) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - altura) // 2)
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift(parent)
        self.wait_visibility()
        self.grab_set()
        self.ent_valor.focus_set()
        self.ent_valor.select_range(0, "end")

    def _ok(self):
        txt = self.var_valor.get().replace(",", ".").strip()
        try:
            v = float(txt)
            if v <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Valor inválido",
                                   "Digite um número positivo.", parent=self)
            return
        self.resultado = (v, self.var_unidade.get())
        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()


def iniciar():
    app = Aplicacao()
    app.mainloop()