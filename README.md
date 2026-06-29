# Medidor de Plântulas

Programa para **medir o comprimento de plântulas de alface a partir de fotos**,
desenvolvido em Python com OpenCV para a disciplina de Computação Gráfica.

Cada plântula é medida em **dois segmentos**, seguindo o caminho real da
estrutura (acompanhando curvas, não em linha reta):

- **Segmento 1 – hipocótilo:** do topo da estrutura branca até o estrangulamento
  (o ponto de transição, no meio da raiz branca — não confundir com a semente
  escura no topo).
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

Isso instala o OpenCV, o NumPy, o Pillow e o pillow-heif (para suporte a fotos de iPhone).

> **Interface gráfica (Tkinter):** o Tkinter já vem junto com o Python na maioria
> das instalações, e **não** é instalado pelo `pip`. Se ao abrir o programa
> aparecer um aviso de que o Tkinter não foi encontrado:
> - **Windows / macOS:** reinstale o Python pelo site oficial
>   (https://www.python.org) deixando marcada a opção "tcl/tk".
> - **Linux (Ubuntu/Debian):** `sudo apt install python3-tk`
> - **Linux (Fedora):** `sudo dnf install python3-tkinter`

---

## 2. Como usar (interface gráfica)

Inicie o programa com:

```
python run.py
```

Uma janela vai abrir. O fluxo recomendado é:

1. **Abrir imagem** — escolha a foto das plântulas.
2. **Calibrar escala** — clique em dois pontos de distância conhecida na régua
   (por exemplo, o começo e o fim de 10 cm) e informe quantos centímetros há
   entre eles. A partir daí as medidas saem na unidade real.
3. **Medir manualmente** — clique ao longo do filamento de cada plântula, do
   topo até a ponta da raiz, acompanhando as curvas. **No ponto de
   estrangulamento (a transição no meio da raiz branca), segure `Shift` e
   clique:** esse ponto é marcado como estrangulamento e o traçado já aparece
   dividido na hora — verde até ali (hipocótilo) e azul depois (raiz), com a
   marca em magenta. Pressione **Enter** para concluir (ou **Esc** para cancelar).
4. **Ajustar o estrangulamento** — o ponto **magenta** pode ser movido a
   qualquer momento, de duas formas: arrastando-o (ele gruda no nó mais próximo)
   ou com as **setas ← → (↑ ↓)** do teclado, que o passam de nó em nó. O botão
   **Ajustar estrangulamento** simplesmente coloca o ponto num nó central da
   plântula selecionada, útil quando ele está fora de vista ou você quer
   recomeçar o ajuste.
5.  **Remover:** selecione uma plântula e clique em **Remover** (ou tecla
     Delete) para apagar medições erradas.
6. **Exportar CSV** e **Exportar imagem** — salva a tabela com as medidas e a
   foto com as marcações. O CSV exige escala calibrada para registrar valores em
   centímetros ou milímetros.


### Navegação na imagem
- **Roda do mouse:** aproximar / afastar (zoom).
- **Botão direito (ou do meio) arrastando:** mover a imagem.

### Cores das marcações
| Cor       | Significado                 |
|-----------|-----------------------------|
| Verde     | Segmento 1 (hipocótilo)     |
| Azul      | Segmento 2 (raiz)           |
| Vermelho  | Topo                        |
| Magenta   | Estrangulamento (transição)  |
| Amarelo   | Ponta da raiz               |

<img width="1195" height="807" alt="plantulas-selecionar-escala" src="https://github.com/user-attachments/assets/0dc56944-5824-45bb-aac5-ea01c935b6e1" />

---

## 3. Critério de medição e calibração

A medição usada no resultado final é **manual**. O usuário traça a plântula com
uma sequência de pontos, e o programa calcula o comprimento somando os trechos
desse caminho em pixels. Assim o comprimento acompanha curvas, em vez de medir
apenas uma reta entre topo e ponta.

A conversão para unidade real é feita pela calibração:

1. O usuário clica dois pontos de distância conhecida na régua visível na foto
   ou em outro objeto de referência.
2. O programa calcula a razão `pixels por unidade real`.
3. Os comprimentos dos segmentos são divididos por essa razão e exportados em
   centímetros ou milímetros.

Sem calibração, os valores exibidos na tela ficam em pixels apenas para
conferência durante o trabalho. A exportação CSV do resultado final exige
calibração.

---

## 4. Como funciona (resumo técnico)

1. A imagem é exibida em um canvas com zoom e deslocamento.
2. O usuário traça manualmente cada plântula do topo até a ponta da raiz.
3. O programa soma as distâncias entre os pontos traçados para obter o
   comprimento digital em pixels.
4. O **estrangulamento** é definido pelo usuário: marcado durante o traçado
   (`Shift`+clique no ponto de transição) ou ajustado depois arrastando o ponto
   magenta / usando as setas do teclado para percorrer os nós. O botão **Ajustar
   estrangulamento** apenas o reposiciona num nó central. Não há detecção
   automática por análise de imagem.
5. Os comprimentos são convertidos para unidade real usando a calibração feita
   na régua da imagem ou em outra referência conhecida.
   
<img width="1195" height="807" alt="image" src="https://github.com/user-attachments/assets/b92c1ca4-c713-42f8-9f8b-0d0ce43882f8" />

---

## 5. Estrutura do projeto

```
medidor_plantulas/
├── run.py               Inicia a interface gráfica
├── requirements.txt     Dependências
├── imagens_exemplo/     Imagens pré-selecionadas
├── nucleo/              Processamento de imagem (sem interface)
│   ├── modelos.py         Plântula, Calibração, Projeto
│   ├── imagem.py          Abrir e salvar imagens (inclui HEIC opcional)
│   ├── tracado.py         Utilidades de caminho (escala, simplificação)
│   └── exportar.py        Gera a tabela CSV e a imagem anotada
└── interface/           Interface gráfica (Tkinter)
    ├── canvas_imagem.py   Área de visualização (zoom, edição, traçado)
    └── janela.py          Janela principal e controles
    
```

O `nucleo` não depende da interface: toda a parte de medição pode ser usada
sozinha (pela linha de comando) e foi testada de forma independente.

---

## 6. Autores do projeto

- Gabriel Fontanari
- Lucas Souza da Silva
- Rodrigo Hammes Waechter
