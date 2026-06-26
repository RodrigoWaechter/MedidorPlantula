# Medidor de Plântulas

Programa para **medir o comprimento de plântulas de alface a partir de fotos**,
desenvolvido em Python com OpenCV para a disciplina de Computação Gráfica.

Cada plântula é medida em **dois segmentos**, seguindo o caminho real da
estrutura (acompanhando curvas, não em linha reta):

- **Segmento 1 – hipocótilo:** do topo da estrutura branca até o estrangulamento
  (onde fica a semente).
- **Segmento 2 – raiz:** do estrangulamento até a ponta da raiz.
- **Total:** a soma dos dois.

A escala é calibrada usando a **régua que aparece na própria foto**, então as
medidas saem em centímetros (ou milímetros), não em pixels.

---

## 1. Instalação

É preciso ter o **Python 3.9 ou mais novo** instalado. Em seguida, abra o
terminal (Prompt de Comando no Windows) na pasta do projeto e rode:

```
pip install -r requirements.txt
```

Isso instala o OpenCV, o NumPy, o SciPy, o scikit-image e o Pillow.

> **Interface gráfica (Tkinter):** o Tkinter já vem junto com o Python na maioria
> das instalações, e **não** é instalado pelo `pip`. Se ao abrir o programa
> aparecer um aviso de que o Tkinter não foi encontrado:
> - **Windows / macOS:** reinstale o Python pelo site oficial
>   (https://www.python.org) deixando marcada a opção "tcl/tk".
> - **Linux (Ubuntu/Debian):** `sudo apt install python3-tk`
> - **Linux (Fedora):** `sudo dnf install python3-tkinter`

> **Fotos HEIC (iPhone):** se quiser abrir arquivos `.heic` diretamente,
> instale também o suporte opcional: `pip install pillow-heif`.
> (Como alternativa, basta converter a foto para `.jpg` ou `.png` antes.)

---

## 2. Como usar (interface gráfica)

Inicie o programa com:

```
python run.py
```

Uma janela vai abrir. O fluxo recomendado é:

1. **Abrir imagem** — escolha a foto das plântulas.
2. **Definir área** — arraste um retângulo sobre o papel branco (dentro da
   caixa). Isso evita que as bordas da caixa sejam confundidas com plântulas.
3. **Calibrar escala** — clique em dois pontos de distância conhecida na régua
   (por exemplo, o começo e o fim de 10 cm) e informe quantos centímetros há
   entre eles. A partir daí as medidas saem na unidade real.
4. **Detectar automaticamente** — o programa traça sozinho as plântulas que
   consegue identificar. Use o controle **Sensibilidade** e clique novamente
   se quiser pegar filamentos mais fracos (valores maiores) ou evitar ruído
   (valores menores).
5. **Ajustar** o que for necessário:
   - **Selecionar:** clique sobre uma plântula.
   - **Mover o estrangulamento:** arraste o ponto **magenta** para o lugar
     onde está a semente (divide hipocótilo e raiz).
   - **Ajustar topo/ponta:** arraste o ponto **vermelho** (topo) ou
     **amarelo** (ponta).
   - **Traçar manual:** quando uma plântula não foi detectada (ou ficou
     incompleta), clique em **Traçar manual** e vá clicando ao longo do
     filamento, do topo até a ponta, acompanhando as curvas. Pressione
     **Enter** para concluir (ou **Esc** para cancelar). Depois arraste o
     ponto magenta para o estrangulamento.
   - **Remover:** selecione uma plântula e clique em **Remover** (ou tecla
     Delete) para apagar detecções erradas.
6. **Exportar CSV** e **Exportar imagem** — salva a tabela com as medidas e a
   foto com as marcações.

### Navegação na imagem
- **Roda do mouse:** aproximar / afastar (zoom).
- **Botão direito (ou do meio) arrastando:** mover a imagem.

### Cores das marcações
| Cor       | Significado                 |
|-----------|-----------------------------|
| Verde     | Segmento 1 (hipocótilo)     |
| Azul      | Segmento 2 (raiz)           |
| Vermelho  | Topo                        |
| Magenta   | Estrangulamento (semente)   |
| Amarelo   | Ponta da raiz               |

---

## 3. Modo linha de comando (opcional)

Para analisar uma foto sem abrir a janela (útil para processar várias de uma
vez ou para conferência rápida):

```
python analisar_cli.py FOTO.png
```

Opções úteis:

```
python analisar_cli.py FOTO.png --sensibilidade 60 --saida resultados
python analisar_cli.py FOTO.png --escala-px 500 --escala-real 10 --unidade cm
```

- `--sensibilidade` (0 a 100): quanto maior, mais filamentos fracos são pegos.
- `--saida`: pasta onde salvar os resultados.
- `--escala-px` e `--escala-real`: calibração pela linha de comando — a
  distância em pixels e a distância real correspondente.

O programa gera, na pasta de saída, uma imagem `*_anotada.png` com as marcações
e uma tabela `*_medidas.csv`.

> Sem calibração, as medidas saem em pixels. A interface gráfica é o jeito mais
> fácil de calibrar (basta clicar dois pontos na régua).

---

## 4. Como funciona (resumo técnico)

1. A imagem é reduzida para uma resolução de trabalho e a área do papel é
   isolada (papel claro e pouco colorido).
2. O filamento branco — quase invisível sobre o papel branco — é realçado com um
   **filtro de vasos (filtro de Sato / vesselness)** do scikit-image, que
   destaca estruturas finas e alongadas.
3. Cada plântula vira uma máscara, que é **esqueletizada** (reduzida a uma linha
   de 1 pixel). O **caminho mais longo** desse esqueleto é encontrado com o
   algoritmo de **Dijkstra**, com peso maior para passos na diagonal — assim o
   comprimento medido segue o caminho real, acompanhando curvas.
4. O **estrangulamento** é localizado pelo ponto mais escuro perto do topo (a
   semente), separando hipocótilo e raiz.
5. Os comprimentos são convertidos de pixels para a unidade real usando a
   calibração feita na régua.

A detecção automática serve como um **rascunho**: ela acerta a maioria das
plântulas bem visíveis, e a interface permite **ajustar ou traçar manualmente**
os casos difíceis (filamentos muito fracos, plântulas sobrepostas, etc.),
garantindo medidas confiáveis.

---

## 5. Estrutura do projeto

```
medidor_plantulas/
├── run.py               Inicia a interface gráfica
├── analisar_cli.py      Modo linha de comando (em lote)
├── requirements.txt     Dependências
├── nucleo/              Processamento de imagem (sem interface)
│   ├── modelos.py         Plântula, Calibração, Projeto
│   ├── imagem.py          Abrir e salvar imagens (inclui HEIC opcional)
│   ├── segmentacao.py     Realce do filamento e separação das estruturas
│   ├── tracado.py         Esqueleto, caminho real e estrangulamento
│   ├── analise.py         Junta tudo: foto -> lista de plântulas
│   └── exportar.py        Gera a tabela CSV e a imagem anotada
└── interface/           Interface gráfica (Tkinter)
    ├── canvas_imagem.py   Área de visualização (zoom, edição, traçado)
    └── janela.py          Janela principal e controles
```

O `nucleo` não depende da interface: toda a parte de medição pode ser usada
sozinha (pela linha de comando) e foi testada de forma independente.
