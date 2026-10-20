# -*- coding: utf-8 -*-
"""Pecas visuais reaproveitadas pelas telas: cartao, metrica, linha, chip.

O Tk nao arredonda widget nenhum -- nem Frame, nem Labelframe. O canto
arredondado que da o ar do AtualizaPrev e desenhado num Canvas COLOCADO ATRAS
do conteudo (`place`), enquanto o conteudo continua num Frame comum, empacotado
(`pack`). A divisao importa por dois motivos:

* `place` nao entra no calculo de tamanho do pai, entao o cartao continua
  crescendo conforme o conteudo -- que e como um Frame se comporta;
* o widget de dentro e um Frame de verdade, e nao um item de Canvas, entao
  Treeview, Entry e arrastar-e-soltar funcionam como sempre.

O recheio (`padding`) precisa ser >= raio: e a faixa de recheio que deixa a
curva a vista. Com recheio menor, o Frame retangular de dentro cobriria o
canto -- invisivel no cartao branco, obvio na barra escura.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .tema import (COR_ACENTO_CLARO, COR_BORDA, COR_BORDA_CAMPO, COR_CARTAO,
                   COR_CARTAO_FRACO, COR_CHIP, COR_CHIP_TEXTO, COR_DICA,
                   COR_FUNDO, COR_LINK, COR_MUDO, COR_OK, COR_PRIMARIA,
                   COR_PRIMARIA_ESCURA, COR_ROTULO, COR_SECUNDARIA,
                   COR_SECUNDARIA_ATIVA, COR_SECUNDARIA_BORDA,
                   COR_SOBRE_PRIMARIA, COR_TEXTO, COR_TITULO, PAD_CARTAO,
                   RAIO_CAMPO, RAIO_CARTAO, RAIO_ITEM, RAIO_LINHA, T_CARTAO,
                   T_LEGENDA, T_METRICA, T_MINI, fonte, fonte_icone, icone)


# ---------------------------------------------------------------------- #
# desenho
# ---------------------------------------------------------------------- #
AMOSTRAS = 4          # subdivisoes por pixel ao suavizar um canto
_cantos_prontos: dict = {}


def _rgb(cor: str, tela: tk.Misc) -> Tuple[int, int, int]:
    """(r, g, b) de uma cor, seja "#rrggbb" ou nome do X11."""
    if cor.startswith("#") and len(cor) == 7:
        return (int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16))
    r, g, b = tela.winfo_rgb(cor)          # devolve 16 bits por canal
    return (r // 257, g // 257, b // 257)


def _misturar(partes: Sequence[Tuple[Tuple[int, int, int], float]]) -> str:
    total = sum(peso for _cor, peso in partes) or 1.0
    canais = [sum(cor[i] * peso for cor, peso in partes) / total
              for i in range(3)]
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(round(c))))
                                          for c in canais))


def _canto_suave(tela: tk.Canvas, raio: int, preenchimento: str, contorno: str,
                 cor_fora: str, espessura: int, quadrante: str) -> tk.PhotoImage:
    """Um canto arredondado como IMAGEM, com a borda suavizada.

    O Canvas do Tk desenha arco sem suavizacao alguma: o canto de um cartao ou
    de um botao sai em degraus, e e disso que vem a impressao de "pixelado" --
    o texto, esse sim, o Tk entrega suavizado pelo Windows.

    A saida aqui e uma imagem de `raio` x `raio` pixels em que cada pixel e
    medido por AMOSTRAS x AMOSTRAS pontos: conta-se quantos caem dentro do
    circulo, quantos na faixa da borda e quantos fora, e a cor do pixel e a
    mistura dos tres na proporcao encontrada. Como o fundo por tras e conhecido
    (o cartao sobre a pagina, a pilula sobre a barra), a mistura pode ser feita
    de antemao, sem canal de transparencia -- que o PhotoImage nao aceita em
    `put`.

    As imagens ficam em cache pelos parametros: um cartao branco de canto 14
    sobre a pagina cinza e desenhado uma vez e reaproveitado por todos.
    """
    chave = (raio, preenchimento, contorno, cor_fora, espessura, quadrante)
    if chave in _cantos_prontos:
        return _cantos_prontos[chave]

    dentro = _rgb(preenchimento or cor_fora, tela)
    borda = _rgb(contorno or preenchimento or cor_fora, tela)
    fora = _rgb(cor_fora, tela)
    limite_dentro = max(0.0, raio - (espessura if contorno else 0))

    # O centro do arco e o canto do quadro que aponta para dentro da forma:
    # no canto noroeste ele fica embaixo e a direita do quadradinho.
    centro_x = float(raio) if quadrante in ("no", "so") else 0.0
    centro_y = float(raio) if quadrante in ("no", "ne") else 0.0

    linhas = []
    for y in range(raio):
        pixels = []
        for x in range(raio):
            conta = {"dentro": 0, "borda": 0, "fora": 0}
            for sy in range(AMOSTRAS):
                for sx in range(AMOSTRAS):
                    px = x + (sx + 0.5) / AMOSTRAS
                    py = y + (sy + 0.5) / AMOSTRAS
                    distancia = ((px - centro_x) ** 2
                                 + (py - centro_y) ** 2) ** 0.5
                    if distancia <= limite_dentro:
                        conta["dentro"] += 1
                    elif distancia <= raio:
                        conta["borda"] += 1
                    else:
                        conta["fora"] += 1
            pixels.append(_misturar(((dentro, conta["dentro"]),
                                     (borda, conta["borda"]),
                                     (fora, conta["fora"]))))
        linhas.append("{" + " ".join(pixels) + "}")

    imagem = tk.PhotoImage(master=tela._root(), width=raio, height=raio)
    imagem.put(" ".join(linhas))
    _cantos_prontos[chave] = imagem
    return imagem


def desenhar_arredondado(tela: tk.Canvas, x1: float, y1: float, x2: float,
                         y2: float, raio: int, preenchimento: str = "",
                         contorno: str = "", espessura: int = 1,
                         tracejado: bool = False,
                         cor_fora: str = "") -> List[int]:
    """Retangulo de cantos arredondados.

    Com `cor_fora` -- a cor que esta ATRAS da forma --, os quatro cantos saem
    de `_canto_suave`, suavizados. Sem ela nao ha como misturar as cores de
    antemao, e o desenho cai nos quatro arcos do Canvas, que serrilham; e o que
    acontece tambem no contorno tracejado, onde a imagem nao serve.
    """
    itens: List[int] = []
    raio = max(0, min(int(raio), int((x2 - x1) / 2), int((y2 - y1) / 2)))
    tracos = (4, 3) if tracejado else ()

    if cor_fora and raio >= 3 and not tracejado:
        return _arredondado_suave(tela, x1, y1, x2, y2, raio, preenchimento,
                                  contorno, cor_fora, espessura)

    if preenchimento:
        if raio:
            itens.append(tela.create_rectangle(
                x1 + raio, y1, x2 - raio, y2,
                fill=preenchimento, outline=preenchimento))
            itens.append(tela.create_rectangle(
                x1, y1 + raio, x2, y2 - raio,
                fill=preenchimento, outline=preenchimento))
            for canto, (cx, cy) in _cantos(x1, y1, x2, y2, raio).items():
                itens.append(tela.create_arc(
                    cx, cy, cx + 2 * raio, cy + 2 * raio, start=canto,
                    extent=90, style="pieslice", fill=preenchimento,
                    outline=preenchimento))
        else:
            itens.append(tela.create_rectangle(
                x1, y1, x2, y2, fill=preenchimento, outline=preenchimento))

    if contorno:
        if raio:
            for canto, (cx, cy) in _cantos(x1, y1, x2, y2, raio).items():
                itens.append(tela.create_arc(
                    cx, cy, cx + 2 * raio, cy + 2 * raio, start=canto,
                    extent=90, style="arc", outline=contorno,
                    width=espessura, dash=tracos))
            for coordenadas in ((x1 + raio, y1, x2 - raio, y1),
                                (x1 + raio, y2, x2 - raio, y2),
                                (x1, y1 + raio, x1, y2 - raio),
                                (x2, y1 + raio, x2, y2 - raio)):
                itens.append(tela.create_line(
                    *coordenadas, fill=contorno, width=espessura, dash=tracos))
        else:
            itens.append(tela.create_rectangle(
                x1, y1, x2, y2, outline=contorno, width=espessura,
                dash=tracos))
    return itens


def _arredondado_suave(tela: tk.Canvas, x1: float, y1: float, x2: float,
                       y2: float, raio: int, preenchimento: str,
                       contorno: str, cor_fora: str,
                       espessura: int) -> List[int]:
    """A forma montada com os quatro cantos em imagem e o meio em retangulo."""
    itens: List[int] = []
    if preenchimento:
        itens.append(tela.create_rectangle(
            x1 + raio, y1, x2 - raio + 1, y2 + 1,
            fill=preenchimento, outline=preenchimento))
        itens.append(tela.create_rectangle(
            x1, y1 + raio, x2 + 1, y2 - raio + 1,
            fill=preenchimento, outline=preenchimento))

    for quadrante, (cx, cy) in (("no", (x1, y1)), ("ne", (x2 - raio + 1, y1)),
                                ("se", (x2 - raio + 1, y2 - raio + 1)),
                                ("so", (x1, y2 - raio + 1))):
        imagem = _canto_suave(tela, raio, preenchimento, contorno, cor_fora,
                              espessura, quadrante)
        itens.append(tela.create_image(cx, cy, image=imagem, anchor="nw"))

    if contorno:
        for coordenadas in ((x1 + raio, y1, x2 - raio, y1),
                            (x1 + raio, y2, x2 - raio, y2),
                            (x1, y1 + raio, x1, y2 - raio),
                            (x2, y1 + raio, x2, y2 - raio)):
            itens.append(tela.create_line(*coordenadas, fill=contorno,
                                          width=espessura))
    return itens


def _cantos(x1: float, y1: float, x2: float, y2: float,
            raio: int) -> dict:
    """Angulo inicial de cada arco -> canto superior esquerdo do seu quadrado."""
    return {
        90: (x1, y1),                       # noroeste
        0: (x2 - 2 * raio, y1),             # nordeste
        270: (x2 - 2 * raio, y2 - 2 * raio),  # sudeste
        180: (x1, y2 - 2 * raio),           # sudoeste
    }


# ---------------------------------------------------------------------- #
# superficies
# ---------------------------------------------------------------------- #
class Superficie(tk.Frame):
    """Painel de canto arredondado. O conteudo vai em `self.corpo`."""

    def __init__(self, dono: tk.Misc, cor: str = COR_CARTAO,
                 cor_fora: str = COR_FUNDO, contorno: str = COR_BORDA,
                 raio: int = RAIO_CARTAO,
                 padding: Tuple[int, int] = PAD_CARTAO,
                 tracejado: bool = False, espessura: int = 1) -> None:
        super().__init__(dono, bg=cor_fora, highlightthickness=0, bd=0)
        self.cor = cor
        self._cor_fora = cor_fora
        self._contorno = contorno
        self._raio = raio
        self._tracejado = tracejado
        self._espessura = espessura
        self._medida = (0, 0)

        self.fundo = tk.Canvas(self, bg=cor_fora, highlightthickness=0, bd=0,
                               takefocus=0)
        self.fundo.place(x=0, y=0, relwidth=1, relheight=1)
        self.corpo = tk.Frame(self, bg=cor, highlightthickness=0, bd=0)
        self.corpo.pack(fill="both", expand=True,
                        padx=padding[0], pady=padding[1])
        self.bind("<Configure>", self._ao_medir)

    # ------------------------------------------------------------------ #
    def _ao_medir(self, evento) -> None:
        if (evento.width, evento.height) == self._medida:
            return
        self._medida = (evento.width, evento.height)
        self.redesenhar()

    def redesenhar(self) -> None:
        largura, altura = self._medida
        if largura < 4 or altura < 4:
            return
        self.fundo.delete("fundo")
        for item in desenhar_arredondado(
                self.fundo, 1, 1, largura - 2, altura - 2, self._raio,
                preenchimento=self.cor, contorno=self._contorno,
                espessura=self._espessura, tracejado=self._tracejado,
                cor_fora=self._cor_fora):
            self.fundo.itemconfigure(item, tags="fundo")
        self.fundo.tag_lower("fundo")
        self.desenhar_extra(largura, altura)

    def desenhar_extra(self, largura: int, altura: int) -> None:
        """Gancho para quem desenha algo mais no fundo (veja `Metrica`)."""

    def pintar(self, cor: str) -> None:
        self.cor = cor
        self.corpo.configure(bg=cor)
        self.redesenhar()


def caixa_de_marcar(dono: tk.Misc, marcada: bool) -> tk.PhotoImage:
    """O check da tabela da folha e da revisao de sugestoes, pixel a pixel.

    O Treeview nao aceita widget na celula, so imagem -- e o "☑" de texto
    saia do tamanho da letra, pequeno demais para acertar o clique. A revisao
    usa a mesma imagem, para os dois checks serem um so.
    """
    lado = 16
    imagem = tk.PhotoImage(master=dono, width=lado, height=lado)
    imagem.put(COR_BORDA_CAMPO if not marcada else COR_PRIMARIA,
               to=(0, 0, lado, lado))
    imagem.put("#ffffff" if not marcada else COR_PRIMARIA,
               to=(1, 1, lado - 1, lado - 1))
    if marcada:
        # o "v" do check, em duas pernas de 2 pixels de espessura
        for i in range(4):
            imagem.put("#ffffff", to=(3 + i, 7 + i, 5 + i, 9 + i))
        for i in range(7):
            imagem.put("#ffffff", to=(6 + i, 10 - i, 8 + i, 12 - i))
    return imagem


def chip(dono: tk.Misc, glifo: str, lado: int = 40,
         cor: str = COR_PRIMARIA, cor_glifo: str = COR_SOBRE_PRIMARIA,
         cor_fora: str = COR_CARTAO, raio: int = RAIO_ITEM,
         tamanho: int = 18, fonte_glifo: Optional[tuple] = None) -> tk.Canvas:
    """O quadradinho arredondado com o icone -- o `.ds-section__icon` da web.

    `fonte_glifo` troca a fonte de simbolos pela de texto, para o chip que
    carrega um numero de passo em vez de um icone.
    """
    tela = tk.Canvas(dono, width=lado, height=lado, bg=cor_fora,
                     highlightthickness=0, bd=0, takefocus=0)
    desenhar_arredondado(tela, 0, 0, lado - 1, lado - 1, raio,
                         preenchimento=cor, contorno=cor, cor_fora=cor_fora)
    tela.create_text(lado / 2, lado / 2 + 1, text=glifo, fill=cor_glifo,
                     font=fonte_glifo or fonte_icone(tamanho))
    return tela


class Cartao(Superficie):
    """Cartao branco com cabecalho de chip + titulo + legenda.

    O conteudo vai em `self.conteudo`; acoes do cabecalho, em `self.acoes`.
    """

    def __init__(self, dono: tk.Misc, titulo: str = "", legenda: str = "",
                 glifo: str = "", **kwargs) -> None:
        super().__init__(dono, **kwargs)
        self.cabeca: Optional[tk.Frame] = None
        self.acoes: Optional[tk.Frame] = None
        self.rotulo_titulo: Optional[tk.Label] = None
        self.rotulo_legenda: Optional[tk.Label] = None

        if titulo:
            self.cabeca = tk.Frame(self.corpo, bg=self.cor)
            self.cabeca.pack(fill="x")

            if glifo:
                chip(self.cabeca, icone(glifo), cor_fora=self.cor, lado=32,
                     tamanho=15).pack(side="left", padx=(0, 10))

            self.acoes = tk.Frame(self.cabeca, bg=self.cor)
            self.acoes.pack(side="right")

            textos = tk.Frame(self.cabeca, bg=self.cor)
            textos.pack(side="left", fill="x", expand=True)
            self.rotulo_titulo = tk.Label(
                textos, text=titulo, bg=self.cor, fg=COR_TITULO,
                font=fonte(T_CARTAO, True), anchor="w")
            self.rotulo_titulo.pack(fill="x")
            # guardado porque ha cartao cuja legenda e viva -- a origem do
            # passo 2 muda conforme a conferencia
            self.rotulo_legenda = tk.Label(
                textos, text=legenda, bg=self.cor, fg=COR_MUDO,
                font=fonte(T_LEGENDA), anchor="w", justify="left")
            if legenda:
                self.rotulo_legenda.pack(fill="x")
                acompanhar_largura(self.rotulo_legenda)

        self.conteudo = tk.Frame(self.corpo, bg=self.cor)
        self.conteudo.pack(fill="both", expand=True,
                           pady=(12, 0) if titulo else 0)


class Linha(Superficie):
    """Linha-cartao: titulo, texto e um lugar para acoes -- o `.entity-card`.

    Serve de item de lista, de opcao clicavel e de area de soltura (com
    `tracejado=True`, o `.ds-empty`).
    """

    def __init__(self, dono: tk.Misc, titulo: str = "", texto: str = "",
                 glifo: str = "", largura_texto: int = 620,
                 raio: int = RAIO_LINHA, contorno: str = COR_BORDA,
                 padding: Tuple[int, int] = (14, 12), **kwargs) -> None:
        super().__init__(dono, raio=raio, contorno=contorno, padding=padding,
                         **kwargs)
        self.acoes = tk.Frame(self.corpo, bg=self.cor)
        self.acoes.pack(side="right", padx=(12, 0))

        if glifo:
            self.chip = chip(self.corpo, icone(glifo), cor=COR_CHIP,
                             cor_glifo=COR_CHIP_TEXTO, cor_fora=self.cor)
            self.chip.pack(side="left", padx=(0, 12))

        self.textos = tk.Frame(self.corpo, bg=self.cor)
        self.textos.pack(side="left", fill="x", expand=True)
        self.rotulo_titulo = tk.Label(
            self.textos, text=titulo, bg=self.cor, fg=COR_TITULO,
            font=fonte(T_CARTAO, True), anchor="w")
        self.rotulo_titulo.pack(fill="x")
        self.rotulo_texto = tk.Label(
            self.textos, text=texto, bg=self.cor, fg=COR_MUDO,
            font=fonte(T_LEGENDA), anchor="w", justify="left",
            wraplength=largura_texto)
        if texto:
            self.rotulo_texto.pack(fill="x", pady=(2, 0))

    def definir(self, titulo: Optional[str] = None,
                texto: Optional[str] = None) -> None:
        if titulo is not None:
            self.rotulo_titulo.configure(text=titulo)
        if texto is not None:
            self.rotulo_texto.configure(text=texto)
            if texto and not self.rotulo_texto.winfo_ismapped():
                self.rotulo_texto.pack(fill="x", pady=(2, 0))


class Metrica(Superficie):
    """Numero grande com um acento colorido na esquerda -- o `DashStatCard`."""

    def __init__(self, dono: tk.Misc, valor: str = "-", rotulo: str = "",
                 cor_acento: str = COR_PRIMARIA, **kwargs) -> None:
        super().__init__(dono, padding=(16, 10), **kwargs)
        self._acento = cor_acento
        self.var_valor = tk.StringVar(value=valor)
        self.var_rotulo = tk.StringVar(value=rotulo)

        tk.Label(self.corpo, textvariable=self.var_valor, bg=self.cor,
                 fg=COR_TITULO, font=fonte(T_METRICA, True, titulo=True),
                 anchor="w").pack(fill="x")
        tk.Label(self.corpo, textvariable=self.var_rotulo, bg=self.cor,
                 fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w").pack(fill="x")

    def desenhar_extra(self, largura: int, altura: int) -> None:
        # O acento acompanha a parte RETA da borda: entrando na curva, ele
        # apareceria por fora do contorno do cartao.
        self.fundo.delete("acento")
        recuo = max(2, self._raio // 2)
        self.fundo.create_rectangle(
            1, 1 + recuo, 5, altura - 2 - recuo,
            fill=self._acento, outline=self._acento, tags="acento")

    def definir(self, valor: str, rotulo: Optional[str] = None,
                cor_acento: Optional[str] = None) -> None:
        self.var_valor.set(valor)
        if rotulo is not None:
            self.var_rotulo.set(rotulo)
        if cor_acento and cor_acento != self._acento:
            self._acento = cor_acento
            self.redesenhar()


# ---------------------------------------------------------------------- #
# campos
# ---------------------------------------------------------------------- #
class CaixaCampo(Superficie):
    """Moldura arredondada de um campo. O widget de entrada vai em `corpo`.

    O ttk desenha o campo com canto vivo e uma borda de um pixel que quase nao
    aparece -- tres retangulos magros em cima do cartao branco, que foi
    exatamente a reclamacao. Aqui a moldura e desenhada (canto de 10, borda de
    verdade, realce navy no foco) e o widget de dentro fica sem borda alguma,
    entao o que se ve e a moldura.
    """

    def __init__(self, dono: tk.Misc, cor_fora: str = COR_CARTAO,
                 raio: int = 10, padding: Tuple[int, int] = (11, 7)) -> None:
        super().__init__(dono, cor_fora=cor_fora, contorno=COR_BORDA_CAMPO,
                         raio=raio, padding=padding)
        self._focado = False
        self._sob_o_mouse = False

    def acompanhar(self, *widgets: tk.Misc) -> None:
        """Liga o realce da moldura ao foco e ao mouse do widget de dentro."""
        for widget in widgets:
            widget.bind("<FocusIn>", lambda _e: self._marcar(foco=True), add="+")
            widget.bind("<FocusOut>", lambda _e: self._marcar(foco=False), add="+")
            widget.bind("<Enter>", lambda _e: self._marcar(mouse=True), add="+")
            widget.bind("<Leave>", lambda _e: self._marcar(mouse=False), add="+")

    def _marcar(self, foco: Optional[bool] = None,
                mouse: Optional[bool] = None) -> None:
        if foco is not None:
            self._focado = foco
        if mouse is not None:
            self._sob_o_mouse = mouse
        if self._focado:
            cor = COR_PRIMARIA
        elif self._sob_o_mouse:
            cor = "#aab3bd"
        else:
            cor = COR_BORDA_CAMPO
        if cor != self._contorno:
            self._contorno = cor
            self.redesenhar()

    def desligar(self, desligado: bool) -> None:
        """Campo desabilitado: moldura apagada e fundo acinzentado."""
        self._contorno = COR_BORDA if desligado else COR_BORDA_CAMPO
        self.pintar(COR_CARTAO_FRACO if desligado else COR_CARTAO)


def campo_texto(dono: tk.Misc, variavel: tk.StringVar, largura: int = 20,
                cor_fora: str = COR_CARTAO,
                padding: Tuple[int, int] = (11, 7),
                **kwargs) -> Tuple[CaixaCampo, tk.Entry]:
    """Campo de texto dentro da moldura arredondada.

    E um `tk.Entry`, e nao um `ttk.Entry`: o ttk insiste em desenhar a propria
    borda, e aqui quem desenha e a moldura.
    """
    caixa = CaixaCampo(dono, cor_fora=cor_fora, padding=padding)
    entrada = tk.Entry(caixa.corpo, textvariable=variavel, width=largura,
                       relief="flat", bd=0, highlightthickness=0,
                       bg=COR_CARTAO, fg=COR_TEXTO, font=fonte(),
                       insertbackground=COR_TEXTO,
                       selectbackground=COR_PRIMARIA,
                       selectforeground=COR_SOBRE_PRIMARIA,
                       disabledbackground=COR_CARTAO_FRACO,
                       disabledforeground=COR_DICA, **kwargs)
    entrada.pack(fill="x", expand=True)
    caixa.acompanhar(entrada)
    return (caixa, entrada)


def moldura_de_lista(dono: tk.Misc, cor_fora: str = COR_CARTAO) -> CaixaCampo:
    """Moldura para os widgets que trazem a propria seta (combo e spinbox).

    Recheio menor do que o do campo de texto: a seta do ttk ja vem com folga
    interna, e a lista de sugestoes se posiciona pelo widget de dentro -- com
    recheio grande ela abriria deslocada da moldura.
    """
    return CaixaCampo(dono, cor_fora=cor_fora, padding=(5, 4))


# ---------------------------------------------------------------------- #
# botao
# ---------------------------------------------------------------------- #
class Botao(tk.Canvas):
    """Botao desenhado a mao, de canto arredondado.

    Existe porque o ttk nao arredonda nada: o tema `clam` desenha um retangulo
    de canto vivo, e no meio de uma tela de cartoes redondos o botao aparecia
    como um bloco cinza. Aqui o fundo, a borda, o realce do mouse, o foco e o
    estado desligado sao desenhados no Canvas, na paleta do resto do sistema.

    A interface e a fatia da `ttk.Button` que as telas usam --
    `configure(text=..., state=...)`, `pack`, `grid` --, para que a troca de
    uma pela outra nao mexa em mais nada.
    """

    ALTURA = 34
    RECUO = 18                  # respiro dos lados do rotulo
    LARGURA_GLIFO = 22          # o icone, mais o espaco ate o texto

    def __init__(self, dono: tk.Misc, text: str = "", command=None,
                 primario: bool = False, sutil: bool = False,
                 cor_fora: str = COR_CARTAO, state: str = "normal",
                 largura_minima: int = 0, glifo: str = "",
                 altura: Optional[int] = None, **kwargs) -> None:
        self._altura = altura or self.ALTURA
        super().__init__(dono, highlightthickness=0, bd=0, bg=cor_fora,
                         takefocus=1, height=self._altura, **kwargs)
        self._glifo = icone(glifo) if glifo else ""
        self._texto = text
        self._comando = command
        self._primario = primario
        self._sutil = sutil
        self._cor_fora = cor_fora
        self._estado = state
        self._largura_minima = largura_minima
        self._sob_o_mouse = False
        self._pressionado = False
        self._com_foco = False

        self._medir()
        self.bind("<Enter>", self._ao_entrar, add="+")
        self.bind("<Leave>", self._ao_sair, add="+")
        self.bind("<ButtonPress-1>", self._ao_apertar, add="+")
        self.bind("<ButtonRelease-1>", self._ao_soltar, add="+")
        self.bind("<FocusIn>", self._ao_focar, add="+")
        self.bind("<FocusOut>", self._ao_desfocar, add="+")
        # teclado: botao que so responde ao mouse tira a tela do alcance do Tab
        for tecla in ("<Return>", "<KP_Enter>", "<space>"):
            self.bind(tecla, lambda _e: self.acionar(), add="+")

    # ------------------------------------------------------------------ #
    @property
    def _ativo(self) -> bool:
        return self._estado not in ("disabled", "disable")

    @staticmethod
    def _fonte() -> tuple:
        return fonte(T_LEGENDA, True)

    def _medir(self) -> None:
        """Largura pelo texto, com o mesmo respiro dos botoes da web."""
        try:
            largura_texto = tkfont.Font(font=self._fonte()).measure(self._texto)
        except Exception:                     # sem root, ou fonte ausente
            largura_texto = 7 * len(self._texto)
        if self._glifo:
            largura_texto += self.LARGURA_GLIFO if self._texto else 0
        largura = max(self._largura_minima, largura_texto + 2 * self.RECUO)
        if self._glifo and not self._texto:   # botao so de icone: quadrado
            largura = max(self._largura_minima, self._altura)
        self.configure(width=largura,
                       cursor="hand2" if self._ativo else "arrow")
        self._pintar()

    def _cores(self) -> Tuple[str, str, str]:
        """(fundo, borda, tinta) para o estado de agora."""
        if not self._ativo:
            if self._primario:
                return ("#dfe3ea", "#dfe3ea", "#9aa4b4")
            return (COR_CARTAO_FRACO, COR_BORDA, COR_DICA)
        if self._primario:
            fundo = ("#233049" if self._pressionado
                     else COR_PRIMARIA_ESCURA if self._sob_o_mouse
                     else COR_PRIMARIA)
            return (fundo, fundo, COR_SOBRE_PRIMARIA)
        if self._sutil:
            fundo = (COR_CHIP if (self._sob_o_mouse or self._pressionado)
                     else self._cor_fora)
            return (fundo, fundo, COR_LINK)
        fundo = (COR_SECUNDARIA_BORDA if self._pressionado
                 else COR_SECUNDARIA_ATIVA if self._sob_o_mouse
                 else COR_SECUNDARIA)
        borda = "#cbd0da" if self._sob_o_mouse else COR_SECUNDARIA_BORDA
        return (fundo, borda, COR_TITULO if self._sob_o_mouse else COR_TEXTO)

    def _pintar(self) -> None:
        largura = int(self["width"])
        altura = int(self["height"])
        fundo, borda, tinta = self._cores()

        self.delete("all")
        desenhar_arredondado(self, 1, 1, largura - 2, altura - 2, RAIO_CAMPO,
                             preenchimento=fundo, contorno=borda,
                             cor_fora=self._cor_fora)
        if self._com_foco and self._ativo:
            desenhar_arredondado(self, 3, 3, largura - 4, altura - 4,
                                 max(2, RAIO_CAMPO - 2),
                                 contorno=COR_ACENTO_CLARO,
                                 preenchimento=fundo, cor_fora=fundo)

        # O glifo acompanha a altura do botao: num botao compacto de 26 px, o
        # icone em 15 pontos preenchia quase tudo e ficava desproporcional ao
        # lado de um rotulo de 9.
        tamanho_glifo = 11 if altura <= 28 else 14
        if self._glifo and not self._texto:
            self.create_text(largura / 2, altura / 2 + 1, text=self._glifo,
                             fill=tinta, font=fonte_icone(tamanho_glifo))
            return
        if self._glifo:
            # icone colado a esquerda do rotulo, os dois centrados no conjunto
            meio = largura / 2 - self.LARGURA_GLIFO / 2
            self.create_text(meio - 4, altura / 2 + 1, text=self._glifo,
                             fill=tinta, font=fonte_icone(tamanho_glifo),
                             anchor="e")
            self.create_text(meio + 6, altura / 2 + 1, text=self._texto,
                             fill=tinta, font=self._fonte(), anchor="w")
            return
        self.create_text(largura / 2, altura / 2 + 1, text=self._texto,
                         fill=tinta, font=self._fonte())

    # ------------------------------------------------------------------ #
    def acionar(self) -> None:
        if self._ativo and callable(self._comando):
            self._comando()

    def _ao_entrar(self, _evento=None) -> None:
        self._sob_o_mouse = True
        self._pintar()

    def _ao_sair(self, _evento=None) -> None:
        self._sob_o_mouse = False
        self._pressionado = False
        self._pintar()

    def _ao_apertar(self, _evento=None) -> None:
        if not self._ativo:
            return
        self._pressionado = True
        self.focus_set()
        self._pintar()

    def _ao_soltar(self, _evento=None) -> None:
        # So aciona se o mouse ainda estiver sobre o botao: arrastar para fora
        # antes de soltar e como se desiste do clique.
        estava = self._pressionado
        self._pressionado = False
        self._pintar()
        if estava and self._sob_o_mouse:
            self.acionar()

    def _ao_focar(self, _evento=None) -> None:
        self._com_foco = True
        self._pintar()

    def _ao_desfocar(self, _evento=None) -> None:
        self._com_foco = False
        self._pintar()

    # ------------------------------------------------------------------ #
    # a fatia da interface da ttk.Button que as telas usam
    # ------------------------------------------------------------------ #
    def configure(self, cnf=None, **kwargs):      # type: ignore[override]
        if isinstance(cnf, dict):
            kwargs.update(cnf)
        texto = kwargs.pop("text", None)
        estado = kwargs.pop("state", None)
        comando = kwargs.pop("command", None)
        # `glifo` e nome desta classe, nao opcao de Canvas: sem tirar daqui, a
        # troca do icone (tela cheia <-> restaurar) morria em TclError.
        glifo = kwargs.pop("glifo", None)
        if comando is not None:
            self._comando = comando
        if estado is not None:
            self._estado = str(estado)
        if texto is not None:
            self._texto = texto
        if glifo is not None:
            self._glifo = icone(glifo) if glifo else ""
        resposta = super().configure(**kwargs) if kwargs else None
        if texto is not None or estado is not None or glifo is not None:
            self._medir()
        return resposta

    config = configure

    def cget(self, chave):                        # type: ignore[override]
        if chave == "text":
            return self._texto
        if chave == "state":
            return self._estado
        return super().cget(chave)

    def __getitem__(self, chave):
        if chave in ("text", "state"):
            return self.cget(chave)
        return super().__getitem__(chave)


# ---------------------------------------------------------------------- #
# passos
# ---------------------------------------------------------------------- #
class Passos(tk.Canvas):
    """Trilha de etapas: pastilha com o icone, trilho ligando, rotulo embaixo.

    Antes as quatro etapas eram Frames lado a lado com uma flecha "→" solta
    entre eles: cada bloco media o seu texto, nada se alinhava e as flechas
    ficavam pequenas e apagadas. Num Canvas so, os centros sao calculados por
    divisao da largura -- entao tudo fica alinhado, o trilho e uma linha reta e
    o texto pode ser centrado sob cada pastilha.

    Cada etapa entra como `(titulo, detalhe, glifo)`. O numero da etapa vai no
    rotulo ("1 · Base + folhas", como na barra lateral), e a pastilha fica com
    o icone: um desenho diz o que a etapa faz, um algarismo so diz a ordem --
    que o trilho ja mostra.
    """

    LADO_PASTILHA = 34
    ALTURA = 84

    # Cada etapa pode dizer onde o trabalho esta: "feita" (verde, com o
    # certo), "atual" (navy) ou "pendente" (apagada). Sem estado, todas saem
    # navy -- o desenho do Inicio, que mostra o caminho e nao o progresso.
    FEITA, ATUAL, PENDENTE = "feita", "atual", "pendente"

    def __init__(self, dono: tk.Misc,
                 etapas: Sequence[Tuple[str, str, str]],
                 cor_fora: str = COR_CARTAO,
                 ao_clicar=None) -> None:
        super().__init__(dono, bg=cor_fora, highlightthickness=0, bd=0,
                         takefocus=0, height=self.ALTURA)
        self.etapas = list(etapas)
        self.estados: List[str] = []
        self._cor_fora = cor_fora
        self._largura = 0
        self._ao_clicar = ao_clicar
        self.bind("<Configure>", self._ao_medir, add="+")
        if ao_clicar is not None:
            self.configure(cursor="hand2")
            self.bind("<Button-1>", self._clique, add="+")

    def marcar(self, estados: Sequence[str],
               detalhes: Optional[Sequence[str]] = None) -> None:
        """Pinta o estado de cada etapa; `detalhes` troca a segunda linha."""
        self.estados = list(estados)
        if detalhes is not None:
            self.etapas = [(titulo, detalhe or antigo, glifo)
                           for (titulo, antigo, glifo), detalhe
                           in zip(self.etapas, detalhes)]
        self._pintar()

    def _clique(self, evento) -> None:
        if self._largura < 40 or not self.etapas:
            return
        indice = int(evento.x // (self._largura / len(self.etapas)))
        self._ao_clicar(max(0, min(indice, len(self.etapas) - 1)))

    def _cores(self, indice: int) -> Tuple[str, str, str]:
        """(pastilha, glifo, titulo) da etapa, conforme o estado dela."""
        estado = self.estados[indice] if indice < len(self.estados) else ""
        if estado == self.FEITA:
            return (COR_OK, COR_SOBRE_PRIMARIA, COR_TITULO)
        if estado == self.PENDENTE:
            return (COR_CHIP, COR_DICA, COR_MUDO)
        return (COR_PRIMARIA, COR_SOBRE_PRIMARIA, COR_TITULO)

    def _ao_medir(self, evento) -> None:
        if evento.width == self._largura:
            return
        self._largura = evento.width
        self._pintar()

    def _pintar(self) -> None:
        largura = self._largura
        quantas = len(self.etapas)
        if largura < 40 or not quantas:
            return
        self.delete("all")

        fatia = largura / quantas
        centros = [fatia * (i + 0.5) for i in range(quantas)]
        meio = 2 + self.LADO_PASTILHA / 2

        # o trilho passa ATRAS das pastilhas, de ponta a ponta
        self.create_line(centros[0], meio, centros[-1], meio,
                         fill=COR_BORDA, width=2)

        for indice, (titulo, detalhe, glifo) in enumerate(self.etapas):
            centro = centros[indice]
            metade = self.LADO_PASTILHA / 2
            pastilha, tinta, cor_titulo = self._cores(indice)
            feita = (indice < len(self.estados)
                     and self.estados[indice] == self.FEITA)
            desenhar_arredondado(
                self, centro - metade, meio - metade, centro + metade,
                meio + metade, RAIO_ITEM, preenchimento=pastilha,
                contorno=pastilha, cor_fora=self._cor_fora)
            self.create_text(centro, meio + 1,
                             text=icone("certo" if feita else glifo),
                             fill=tinta, font=fonte_icone(16))
            self.create_text(centro, meio + metade + 10,
                             text="{} · {}".format(indice + 1, titulo),
                             fill=cor_titulo, font=fonte(T_LEGENDA, True),
                             anchor="n", width=fatia - 16, justify="center")
            self.create_text(centro, meio + metade + 28, text=detalhe,
                             fill=COR_MUDO, font=fonte(T_MINI), anchor="n",
                             width=fatia - 16, justify="center")


# ---------------------------------------------------------------------- #
# miudezas
# ---------------------------------------------------------------------- #
def acompanhar_largura(rotulo: tk.Misc, folga: int = 0,
                       minimo: int = 160) -> None:
    """Faz o `wraplength` do rotulo seguir a largura de quem o contem.

    Sem isto o texto quebra num numero fixo de pixels: no cartao largo sobra
    faixa branca a direita, e no estreito a frase e cortada. O limite so muda
    quando a diferenca passa de alguns pixels, para o ajuste nao entrar em
    laco com o proprio calculo de tamanho do pai.
    """
    def ajustar(evento) -> None:
        nova = max(minimo, evento.width - folga)
        try:
            atual = int(rotulo.cget("wraplength") or 0)
        except Exception:
            atual = 0
        if abs(atual - nova) > 8:
            rotulo.configure(wraplength=nova)

    dono = rotulo.master
    if dono is not None:
        dono.bind("<Configure>", ajustar, add="+")


def rotulo_campo(dono: tk.Misc, texto: str, **kwargs) -> ttk.Label:
    """Rotulo acima do campo, em maiusculas pequenas."""
    return ttk.Label(dono, text=texto.upper(), style="Rotulo.TLabel", **kwargs)


def divisor(dono: tk.Misc, cor: str = COR_BORDA, **kwargs) -> tk.Frame:
    linha = tk.Frame(dono, bg=cor, height=1)
    linha.pack(fill="x", **kwargs)
    return linha


def grade_igual(dono: tk.Misc, colunas: int, folga: int = 0) -> None:
    """Colunas de mesma largura -- a linha de metricas e a de cartoes."""
    for coluna in range(colunas):
        dono.columnconfigure(coluna, weight=1, uniform="grade", pad=folga)


class Balao:
    """Dica que aparece ao pousar o mouse.

    Existe por causa da barra lateral recolhida: sem o rotulo ao lado do
    icone, so o balao diz para onde o item leva.
    """

    ATRASO = 420

    def __init__(self, alvo: tk.Misc, texto: str = "") -> None:
        self.alvo = alvo
        self.texto = texto
        self._janela: Optional[tk.Toplevel] = None
        self._rotulo: Optional[tk.Label] = None
        self._agendado: Optional[str] = None
        alvo.bind("<Enter>", self._ao_entrar, add="+")
        alvo.bind("<Leave>", self._ao_sair, add="+")
        alvo.bind("<Button-1>", self._ao_sair, add="+")

    def definir(self, texto: str) -> None:
        self.texto = texto

    def mostrar_em(self, texto: str, x: int, y: int) -> None:
        """Mostra o balao com este texto, nesta posicao da tela.

        Serve a quem nao tem um widget fixo para apontar -- a celula de uma
        tabela, que muda a cada movimento do mouse. Reaproveita a janela
        aberta, em vez de destruir e recriar: recriar a cada pixel piscava.
        """
        self.texto = texto
        if self._janela is None:
            self._criar()
        if self._rotulo is not None:
            self._rotulo.configure(text=texto)
        if self._janela is not None:
            self._janela.geometry("+{}+{}".format(x, y))
            self._janela.deiconify()
            self._janela.lift()

    def esconder(self) -> None:
        self._cancelar()
        if self._janela is not None:
            self._janela.withdraw()

    def _ao_entrar(self, _evento=None) -> None:
        self._cancelar()
        if self.texto:
            self._agendado = self.alvo.after(self.ATRASO, self._mostrar)

    def _ao_sair(self, _evento=None) -> None:
        self.esconder()

    def _cancelar(self) -> None:
        if self._agendado is not None:
            try:
                self.alvo.after_cancel(self._agendado)
            except Exception:
                pass
            self._agendado = None

    def _criar(self) -> None:
        """A janelinha do balao, criada uma vez e depois so reposicionada."""
        janela = tk.Toplevel(self.alvo)
        janela.withdraw()
        janela.overrideredirect(True)
        janela.attributes("-topmost", True)
        janela.configure(bg=COR_BORDA_CAMPO)
        self._rotulo = tk.Label(janela, text=self.texto, bg=COR_TITULO,
                                fg="#ffffff", font=fonte(T_LEGENDA), padx=9,
                                pady=5, justify="left", wraplength=560)
        self._rotulo.pack(padx=1, pady=1)
        self._janela = janela

    def _mostrar(self) -> None:
        self._agendado = None
        if not self.texto:
            return
        if self._janela is None:
            self._criar()
        if self._rotulo is not None:
            self._rotulo.configure(text=self.texto)
        janela = self._janela
        if janela is None:
            return
        janela.update_idletasks()
        largura, altura = janela.winfo_width(), janela.winfo_height()
        x = self.alvo.winfo_rootx() + self.alvo.winfo_width() + 10
        y = self.alvo.winfo_rooty() + max(0, (self.alvo.winfo_height()
                                              - altura) // 2)

        # Sem isto o balao de um alvo largo abre fora da tela -- ou, pior, em
        # cima da janela do vizinho, onde ninguem entende de onde ele veio. Se
        # nao couber a direita, vai para a esquerda do alvo; se nem assim,
        # encosta na borda.
        na_tela_x = self.alvo.winfo_screenwidth()
        na_tela_y = self.alvo.winfo_screenheight()
        if x + largura > na_tela_x - 8:
            a_esquerda = self.alvo.winfo_rootx() - largura - 10
            x = a_esquerda if a_esquerda >= 8 else max(8, na_tela_x - largura - 8)
        y = max(8, min(y, na_tela_y - altura - 8))
        janela.geometry("+{}+{}".format(x, y))
        janela.deiconify()
        janela.lift()


# ---------------------------------------------------------------------- #
def tornar_pesquisavel(combo: ttk.Combobox, todos) -> None:
    """Deixa a caixa aceitar o que se digita e filtrar a lista.

    Sao 29 municipios: achar o certo rolando a lista e mais trabalhoso que
    escrever "ros". A caixa deixa de ser `readonly` e passa a filtrar a cada
    tecla -- por pedaco do nome, em qualquer posicao e sem acento, para
    "cabacal" achar "RESERVA DO CABAÇAL".

    `todos` e uma FUNCAO que devolve a lista completa, e nao a lista: ela muda
    quando um catalogo e importado (a marca do municipio vira "✓"), e guardar
    uma copia aqui deixaria a busca mostrando a lista de antes.

    O valor so e aceito se existir na lista. Texto solto -- "ros" sem escolher
    nada, ou um nome que nao existe -- volta ao que estava quando a caixa perde
    o foco: municipio errado escolhido por engano e o comeco de creditar a
    arrecadacao na fonte errada, e meio nome digitado nao e uma escolha.
    """
    combo.configure(state="normal")
    ultimo = {"valor": combo.get()}

    def sem_acento(texto: str) -> str:
        import unicodedata
        plano = unicodedata.normalize("NFKD", str(texto or ""))
        return "".join(c for c in plano if not unicodedata.combining(c)).upper()

    def filtrar(evento) -> None:
        if evento.keysym in ("Up", "Down", "Return", "Escape", "Tab",
                             "Left", "Right", "Home", "End"):
            return
        procurado = sem_acento(combo.get()).strip()
        lista = todos()
        if procurado:
            lista = [r for r in lista if procurado in sem_acento(r)]
        combo.configure(values=lista or todos())

    def confirmar(_evento=None) -> None:
        atual = combo.get()
        lista = todos()
        if atual in lista:
            ultimo["valor"] = atual
        else:
            # um unico candidato restante conta como escolha; o resto, nao
            candidatos = [r for r in lista
                          if sem_acento(atual).strip() in sem_acento(r)]
            escolhido = candidatos[0] if len(candidatos) == 1 else ultimo["valor"]
            combo.set(escolhido)
            ultimo["valor"] = escolhido
        combo.configure(values=lista)

    def escolhido(_evento=None) -> None:
        ultimo["valor"] = combo.get()
        combo.configure(values=todos())

    combo.bind("<KeyRelease>", filtrar, add="+")
    combo.bind("<FocusOut>", confirmar, add="+")
    combo.bind("<Return>", confirmar, add="+")
    combo.bind("<<ComboboxSelected>>", escolhido, add="+")
