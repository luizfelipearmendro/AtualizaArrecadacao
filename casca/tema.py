# -*- coding: utf-8 -*-
"""Identidade visual da casca: paleta, tipografia, icones e estilos ttk.

A referencia e o AtualizaPrev -- o sistema web da casa. O que veio de la, e que
e o que da o "ar de familia":

* fundo da pagina em cinza-nuvem (`#f8f9fa`) e conteudo em cartoes brancos
  flutuantes, de borda fina e canto arredondado, em vez de widgets colados na
  moldura da janela;
* barra lateral em tinta escura, tambem arredondada e destacada do fundo, com
  o item ativo em pilula clara;
* tinta navy (`#344767`) nos titulos, nos botoes de acao e nos chips de icone;
* rotulo de campo em MAIUSCULAS pequenas, cinza-azulado, acima do campo;
* numero em cartao de metrica, com um acento colorido na borda esquerda.

O Tk nao arredonda widget: o canto e desenhado num Canvas atras do conteudo
(veja `componentes.Superficie`). Aqui ficam so as cores, as fontes e os estilos.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional

import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------------- #
# superficies
# ---------------------------------------------------------------------- #
COR_FUNDO = "#f8f9fa"          # --app-bg (o cinza-nuvem da pagina)
COR_CARTAO = "#ffffff"         # --app-content-bg
COR_CARTAO_FRACO = "#f6f7f9"   # cartao desligado, linha zebrada
COR_BORDA = "#e9e9e9"          # --app-border-figma: a borda do cartao
COR_BORDA_CAMPO = "#c7ccd0"    # --color-snow: borda de campo e de tracejado
COR_CHIP = "#eef1f6"           # fundo do chip discreto
COR_CHIP_TEXTO = "#5b6b86"

# ---------------------------------------------------------------------- #
# tinta
# ---------------------------------------------------------------------- #
COR_TEXTO = "#344767"          # --app-text (navy)
COR_TITULO = "#2b3a55"         # navy mais fechado, dos titulos
COR_MUDO = "#6b7a90"           # --app-muted
COR_DICA = "#8a92a3"           # legenda sob o titulo
COR_ROTULO = "#7c8596"         # .field__label
COR_LINK = "#3d5a99"

# ---------------------------------------------------------------------- #
# marca e acoes
# ---------------------------------------------------------------------- #
COR_PRIMARIA = "#344767"
COR_PRIMARIA_CLARA = "#3d527a"   # topo do chip de secao
COR_PRIMARIA_ESCURA = "#2b3a55"
COR_SOBRE_PRIMARIA = "#ffffff"
COR_SECUNDARIA = "#f3f4f7"       # botao secundario do AtualizaPrev
COR_SECUNDARIA_ATIVA = "#e9ebf0"
COR_SECUNDARIA_BORDA = "#d8dce4"
COR_ACENTO_CLARO = "#9fb3cd"     # acento claro da identidade

# ---------------------------------------------------------------------- #
# barra lateral (a tinta escura do AppSidebar)
# ---------------------------------------------------------------------- #
COR_BARRA = "#1b2133"
COR_BARRA_BAIXO = "#171c2c"
COR_BARRA_PAINEL = "#141926"     # painel de progresso, um degrau mais fundo
COR_BARRA_TEXTO = "#b3b3b3"
COR_BARRA_FORTE = "#ffffff"
COR_BARRA_FRACO = "#7e8698"      # secao, legenda e chevron
COR_BARRA_HOVER = "#252b3d"      # rgba(255,255,255,.06) sobre a barra
COR_BARRA_ATIVO = "#313749"      # rgba(255,255,255,.10)
COR_BARRA_LINHA = "#262c3d"      # divisor
COR_BARRA_DESLIGADO = "#5c6479"

# ---------------------------------------------------------------------- #
# semanticas
# ---------------------------------------------------------------------- #
COR_OK = "#1f9d57"
COR_ATENCAO = "#b7791f"
COR_ERRO = "#9b2c2c"

# usadas nas tabelas de evidencia
CORES_RELEVANCIA = {
    "alta": "#1f9d57",
    "media": "#8a6d00",
    "baixa": "#9b2c2c",
    "revisar": "#a2560f",
    "contexto": "#3d5a99",
}

# ---------------------------------------------------------------------- #
# medidas
# ---------------------------------------------------------------------- #
RAIO_BARRA = 20        # a lateral flutua com o canto mais redondo
RAIO_CARTAO = 14
RAIO_LINHA = 12        # .entity-card
RAIO_ITEM = 10         # item da barra lateral, e o chip
RAIO_CAMPO = 8

GAP = 12               # respiro entre cartoes, o gap de 1rem da web
PAD_CARTAO = (18, 14)

# tamanhos de fonte, em pontos
T_MINI = 8             # rotulo de campo, legenda da barra
T_LEGENDA = 9
T_BASE = 10
T_CARTAO = 11          # titulo de cartao
T_MARCA = 13           # nome do aplicativo na barra
T_TELA = 15            # titulo da tela, no cabecalho
T_METRICA = 17         # o numero do cartao de metrica

# ---------------------------------------------------------------------- #
# tipografia
# ---------------------------------------------------------------------- #
# O AtualizaPrev usa Inter. Ela raramente esta instalada no Windows do
# escritorio, e a substituta mais proxima e a Segoe UI Variable (Windows 11);
# a Segoe UI comum e o ultimo degrau, presente em qualquer Windows.
_PREFERIDAS = ("Inter", "Inter Variable", "Segoe UI Variable Text", "Segoe UI")
_PREFERIDAS_TITULO = ("Inter", "Inter Variable", "Segoe UI Variable Display",
                      "Segoe UI Semibold", "Segoe UI")
# Icones: a fonte de simbolos do proprio Windows, para nao embutir imagem
# nenhuma. A Fluent Icons (Windows 11) vem primeiro porque desenha todos os
# glifos deste arquivo; a MDL2 (Windows 10) e a reserva, e nela alguns destes
# codigos caem no retangulo vazio -- se algum dia o programa rodar num
# Windows 10, e aqui que se conferem os glifos.
_PREFERIDAS_ICONE = ("Segoe Fluent Icons", "Segoe MDL2 Assets", "Segoe UI Symbol")

_familias_disponiveis: Optional[frozenset] = None
_resolvidas: Dict[str, str] = {}


def _familias() -> frozenset:
    """Familias instaladas. Exige um root do Tk -- por isso a consulta e tardia."""
    global _familias_disponiveis
    if _familias_disponiveis is None:
        try:
            from tkinter import font
            _familias_disponiveis = frozenset(font.families())
        except Exception:
            _familias_disponiveis = frozenset()
    return _familias_disponiveis


def _primeira(chave: str, candidatas: Iterable[str], reserva: str) -> str:
    if chave not in _resolvidas:
        instaladas = _familias()
        _resolvidas[chave] = next(
            (nome for nome in candidatas if nome in instaladas), reserva)
    return _resolvidas[chave]


def familia() -> str:
    return _primeira("texto", _PREFERIDAS, "Segoe UI")


def familia_titulo() -> str:
    return _primeira("titulo", _PREFERIDAS_TITULO, "Segoe UI")


def familia_icone() -> str:
    return _primeira("icone", _PREFERIDAS_ICONE, "Segoe UI Symbol")


def fonte(tamanho: int = T_BASE, negrito: bool = False,
          titulo: bool = False) -> tuple:
    """A fonte do texto, na familia que existir na maquina."""
    nome = familia_titulo() if titulo else familia()
    return (nome, tamanho, "bold") if negrito else (nome, tamanho)


def fonte_icone(tamanho: int = 16) -> tuple:
    return (familia_icone(), tamanho)


# Glifos da Segoe Fluent Icons / MDL2, com nome em portugues -- e assim que as
# telas os pedem.
ICONES = {
    "inicio": "",        # Home
    "conferir": "",      # CheckList
    "diario": "",        # Document
    "consulta": "",      # Search
    "relatorios": "",    # ReportDocument
    "pasta": "",         # Folder
    "planilha": "",      # DocumentApproval
    "pessoa": "",        # Contact
    "pessoas": "",       # People
    "filtro": "",        # Filter
    "aviso": "",         # Warning
    "informacao": "",    # Info
    "certo": "",         # CheckMark
    "seta": "",          # ChevronRight
    "esquerda": "",      # ChevronLeft
    "baixo": "",         # ChevronDown
    "atualizar": "",     # Refresh
    "lixeira": "",       # Delete
    "nuvem": "",         # Cloud
    "globo": "",         # Globe
    "abrir": "",         # OpenFile
    "engrenagem": "",    # Settings
    "grafico": "",       # BarChart4
    "calendario": "",    # Calendar
    "relogio": "",       # History
    "baixar": "",        # Download
    "tela_cheia": "",    # FullScreen
    "restaurar": "",     # BackToWindow
    "voltar": "",        # Back
    "anterior": "",      # ChevronLeft
    "proxima": "",       # ChevronRight
}


def icone(chave: str) -> str:
    return ICONES.get(chave, ICONES["informacao"])


# ---------------------------------------------------------------------- #
# estilos ttk
# ---------------------------------------------------------------------- #
def aplicar_estilo() -> None:
    """Tema dos widgets ttk.

    O fundo PADRAO e o branco do cartao, e nao o cinza da pagina: depois do
    redesenho quase todo widget ttk vive dentro de um cartao, e um Label de
    fundo cinza sobre o cartao branco aparece como um retangulo sujo. O que
    fica direto sobre a pagina usa os estilos `Fundo.*`.
    """
    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except Exception:
        pass

    estilo.configure(".", background=COR_CARTAO, foreground=COR_TEXTO,
                     font=fonte(), focuscolor=COR_ACENTO_CLARO)

    # --- molduras e rotulos ------------------------------------------- #
    estilo.configure("TFrame", background=COR_CARTAO)
    estilo.configure("Fundo.TFrame", background=COR_FUNDO)
    estilo.configure("Barra.TFrame", background=COR_BARRA)

    estilo.configure("TLabel", background=COR_CARTAO, foreground=COR_TEXTO)
    estilo.configure("Fundo.TLabel", background=COR_FUNDO, foreground=COR_TEXTO)
    estilo.configure("Titulo.TLabel", font=fonte(T_TELA, True, titulo=True),
                     foreground=COR_TITULO)
    estilo.configure("Cartao.TLabel", font=fonte(T_CARTAO, True),
                     foreground=COR_TITULO)
    estilo.configure("Forte.TLabel", font=fonte(T_BASE, True),
                     foreground=COR_TITULO)
    estilo.configure("Dica.TLabel", font=fonte(T_LEGENDA), foreground=COR_MUDO)
    estilo.configure("DicaFundo.TLabel", font=fonte(T_LEGENDA),
                     foreground=COR_MUDO, background=COR_FUNDO)
    estilo.configure("Passo.TLabel", font=fonte(T_MINI), foreground=COR_DICA)
    # rotulo de campo: MAIUSCULAS pequenas, como no wizard do AtualizaPrev
    estilo.configure("Rotulo.TLabel", font=fonte(T_MINI, True),
                     foreground=COR_ROTULO)
    estilo.configure("Sub.TLabel", font=fonte(T_LEGENDA), foreground=COR_DICA)
    estilo.configure("Cabecalho.TLabel", font=fonte(T_TELA, True, titulo=True),
                     foreground=COR_TITULO)
    estilo.configure("Aviso.TLabel", font=fonte(T_LEGENDA), foreground=COR_ATENCAO)
    estilo.configure("Erro.TLabel", font=fonte(T_LEGENDA), foreground=COR_ERRO)

    estilo.configure("TLabelframe", background=COR_CARTAO, bordercolor=COR_BORDA,
                     relief="solid", borderwidth=1)
    estilo.configure("TLabelframe.Label", background=COR_CARTAO,
                     font=fonte(T_CARTAO, True), foreground=COR_TITULO)

    estilo.configure("TSeparator", background=COR_BORDA)

    # --- botoes -------------------------------------------------------- #
    # Secundario: o claro com tinta navy do `.p-button-secondary`.
    estilo.configure("TButton", background=COR_SECUNDARIA,
                     foreground=COR_TEXTO, bordercolor=COR_SECUNDARIA_BORDA,
                     lightcolor=COR_SECUNDARIA, darkcolor=COR_SECUNDARIA,
                     focusthickness=0, focuscolor="none", relief="flat",
                     borderwidth=1, padding=(14, 7), font=fonte(T_LEGENDA, True),
                     anchor="center")
    estilo.map("TButton",
               background=[("disabled", COR_CARTAO_FRACO),
                           ("pressed", COR_SECUNDARIA_BORDA),
                           ("active", COR_SECUNDARIA_ATIVA)],
               bordercolor=[("disabled", COR_BORDA)],
               foreground=[("disabled", COR_DICA), ("active", COR_TITULO)])

    # Acao: o botao cheio, navy, do primario da web.
    estilo.configure("Acao.TButton", background=COR_PRIMARIA,
                     foreground=COR_SOBRE_PRIMARIA, bordercolor=COR_PRIMARIA,
                     lightcolor=COR_PRIMARIA, darkcolor=COR_PRIMARIA,
                     focusthickness=0, focuscolor="none", relief="flat",
                     borderwidth=1, padding=(18, 9), font=fonte(T_LEGENDA, True),
                     anchor="center")
    estilo.map("Acao.TButton",
               background=[("disabled", "#dfe3ea"),
                           ("pressed", "#233049"),
                           ("active", COR_PRIMARIA_ESCURA)],
               bordercolor=[("disabled", "#dfe3ea")],
               lightcolor=[("disabled", "#dfe3ea")],
               darkcolor=[("disabled", "#dfe3ea")],
               foreground=[("disabled", "#9aa4b4")])

    # Sutil: sem moldura, para a acao secundaria dentro do cartao.
    estilo.configure("Sutil.TButton", background=COR_CARTAO,
                     foreground=COR_LINK, bordercolor=COR_CARTAO,
                     lightcolor=COR_CARTAO, darkcolor=COR_CARTAO,
                     focusthickness=0, focuscolor="none",
                     relief="flat", borderwidth=0, padding=(8, 6),
                     font=fonte(T_LEGENDA, True))
    estilo.map("Sutil.TButton",
               background=[("active", COR_CHIP), ("pressed", COR_CHIP)],
               foreground=[("disabled", COR_DICA)])

    # --- campos -------------------------------------------------------- #
    for nome in ("TEntry", "TCombobox", "TSpinbox"):
        estilo.configure(nome, fieldbackground=COR_CARTAO,
                         background=COR_CARTAO, foreground=COR_TEXTO,
                         bordercolor=COR_BORDA_CAMPO, lightcolor=COR_BORDA_CAMPO,
                         darkcolor=COR_BORDA_CAMPO, insertcolor=COR_TEXTO,
                         arrowcolor=COR_MUDO, relief="flat", borderwidth=1,
                         padding=(8, 6), selectbackground=COR_PRIMARIA,
                         selectforeground=COR_SOBRE_PRIMARIA)
        estilo.map(nome,
                   bordercolor=[("focus", COR_PRIMARIA),
                                ("hover", "#aab3bd"),
                                ("disabled", COR_BORDA)],
                   lightcolor=[("focus", COR_PRIMARIA), ("disabled", COR_BORDA)],
                   darkcolor=[("focus", COR_PRIMARIA), ("disabled", COR_BORDA)],
                   fieldbackground=[("disabled", COR_CARTAO_FRACO),
                                    ("readonly", COR_CARTAO)],
                   foreground=[("disabled", COR_DICA)],
                   arrowcolor=[("disabled", COR_BORDA_CAMPO)])

    # Plano: para o combo e o spin que vivem DENTRO de uma moldura desenhada
    # (`componentes.moldura_de_lista`). Quem desenha a borda e a moldura; o
    # widget entra sem nenhuma, senao aparecem duas -- uma dentro da outra.
    for nome in ("Plano.TCombobox", "Plano.TSpinbox"):
        estilo.configure(nome, fieldbackground=COR_CARTAO,
                         background=COR_CARTAO, foreground=COR_TEXTO,
                         bordercolor=COR_CARTAO, lightcolor=COR_CARTAO,
                         darkcolor=COR_CARTAO, insertcolor=COR_TEXTO,
                         arrowcolor=COR_MUDO, relief="flat", borderwidth=0,
                         padding=(4, 2), selectbackground=COR_PRIMARIA,
                         selectforeground=COR_SOBRE_PRIMARIA)
        estilo.map(nome,
                   bordercolor=[("focus", COR_CARTAO)],
                   lightcolor=[("focus", COR_CARTAO)],
                   darkcolor=[("focus", COR_CARTAO)],
                   fieldbackground=[("disabled", COR_CARTAO_FRACO),
                                    ("readonly", COR_CARTAO)],
                   foreground=[("disabled", COR_DICA)],
                   arrowcolor=[("disabled", COR_BORDA_CAMPO)])

    # --- marcadores ---------------------------------------------------- #
    _marcadores_nativos(estilo)

    for nome in ("TCheckbutton", "TRadiobutton"):
        estilo.configure(nome, background=COR_CARTAO, foreground=COR_TEXTO,
                         font=fonte(T_LEGENDA), focuscolor="none",
                         indicatorcolor=COR_CARTAO,
                         indicatorbackground=COR_CARTAO,
                         bordercolor=COR_BORDA_CAMPO,
                         lightcolor=COR_CARTAO, darkcolor=COR_CARTAO,
                         padding=(0, 3))
        estilo.map(nome,
                   background=[("active", COR_CARTAO)],
                   indicatorcolor=[("selected", COR_PRIMARIA),
                                   ("pressed", COR_CHIP),
                                   ("disabled", COR_CARTAO_FRACO)],
                   bordercolor=[("selected", COR_PRIMARIA),
                                ("active", COR_MUDO),
                                ("disabled", COR_BORDA)],
                   foreground=[("disabled", COR_DICA)])

    # --- tabela -------------------------------------------------------- #
    estilo.configure("Treeview", background=COR_CARTAO, fieldbackground=COR_CARTAO,
                     foreground=COR_TEXTO, rowheight=29, borderwidth=0,
                     relief="flat", font=fonte(T_LEGENDA))
    estilo.map("Treeview",
               background=[("selected", "#dfe6f2")],
               foreground=[("selected", COR_TITULO)])
    # cabecalho alinhado a esquerda, como a celula: centralizado, o titulo
    # nao se le em coluna larga e nao aponta para o texto que ele nomeia
    estilo.configure("Treeview.Heading", background=COR_CHIP,
                     foreground=COR_TITULO, font=fonte(T_LEGENDA, True),
                     relief="flat", borderwidth=0, padding=(8, 8), anchor="w")
    estilo.map("Treeview.Heading",
               background=[("active", "#e3e8f1"), ("pressed", "#dbe1ec")])
    # sem a moldura tridimensional que o clam desenha em volta da area
    estilo.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    # --- rolagem, painel e progresso ----------------------------------- #
    for nome in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        estilo.configure(nome, background="#cfd6e0", troughcolor=COR_CARTAO,
                         bordercolor=COR_CARTAO, arrowcolor=COR_MUDO,
                         lightcolor="#cfd6e0", darkcolor="#cfd6e0",
                         gripcount=0, relief="flat", borderwidth=0, width=11)
        estilo.map(nome, background=[("active", "#b6bfcd"),
                                     ("pressed", "#a3adbd")])
    # Sem as duas setas nas pontas: elas sao dois quadradinhos com um
    # triangulo desenhado a mao pelo clam, e a barra fina do AtualizaPrev nao
    # tem seta nenhuma -- e a roda do mouse ja rola tudo.
    estilo.layout("Vertical.TScrollbar",
                  [("Vertical.Scrollbar.trough",
                    {"sticky": "ns", "children": [
                        ("Vertical.Scrollbar.thumb",
                         {"expand": "1", "sticky": "nswe"})]})])
    estilo.layout("Horizontal.TScrollbar",
                  [("Horizontal.Scrollbar.trough",
                    {"sticky": "we", "children": [
                        ("Horizontal.Scrollbar.thumb",
                         {"expand": "1", "sticky": "nswe"})]})])

    estilo.configure("TPanedwindow", background=COR_FUNDO)
    estilo.configure("Sash", sashthickness=GAP, gripcount=0,
                     background=COR_FUNDO, bordercolor=COR_FUNDO,
                     lightcolor=COR_FUNDO, darkcolor=COR_FUNDO)

    estilo.configure("TProgressbar", background=COR_PRIMARIA,
                     troughcolor=COR_CHIP, bordercolor=COR_CHIP,
                     lightcolor=COR_PRIMARIA, darkcolor=COR_PRIMARIA,
                     borderwidth=0, thickness=6)
    # a barra que vive na tinta escura da lateral
    estilo.configure("Barra.Horizontal.TProgressbar",
                     background=COR_ACENTO_CLARO, troughcolor="#232a3d",
                     bordercolor="#232a3d", lightcolor=COR_ACENTO_CLARO,
                     darkcolor=COR_ACENTO_CLARO, borderwidth=0, thickness=5)


def _marcadores_nativos(estilo: ttk.Style) -> None:
    """Troca o indicador do clam pelo do Windows, mantendo o resto do clam.

    O indicador do clam e desenhado a mao e sem suavizacao: a caixa marcada
    sai como um X serrilhado, que era a parte mais tosca da tela. O ttk sabe
    copiar UM elemento de outro tema (`element_create ... from`), mas nao
    aceita sobrescrever um nome que ja existe -- daí o nome novo e o layout
    remontado por cima do estilo padrao, para que toda caixa e todo radio da
    aplicacao herdem o indicador nativo sem mudar uma linha nas telas.

    O tema `vista` so existe no Windows; em qualquer falha fica o indicador do
    clam, que e feio mas funciona.
    """
    for tipo in ("Checkbutton", "Radiobutton"):
        elemento = "Nativo.{}.indicator".format(tipo)
        try:
            estilo.element_create(elemento, "from", "vista")
            estilo.layout("T{}".format(tipo), [
                ("{}.padding".format(tipo), {
                    "sticky": "nswe",
                    "children": [
                        (elemento, {"side": "left", "sticky": ""}),
                        ("{}.focus".format(tipo), {
                            "side": "left", "sticky": "w",
                            "children": [
                                ("{}.label".format(tipo), {"sticky": "nswe"}),
                            ]}),
                    ]}),
            ])
        except tk.TclError:
            pass


def estilizar_menu(menu: tk.Menu) -> tk.Menu:
    """Menu de contexto na mesma tinta das telas.

    O `tk.Menu` e widget nativo: nao le estilo ttk nenhum, e sem isto o menu do
    cabecalho da tabela sai com o cinza tridimensional do Motif.
    """
    try:
        menu.configure(
            background=COR_CARTAO, foreground=COR_TEXTO, font=fonte(T_LEGENDA),
            activebackground=COR_CHIP, activeforeground=COR_TITULO,
            activeborderwidth=0, borderwidth=1, relief="solid",
            selectcolor=COR_PRIMARIA, disabledforeground=COR_DICA)
    except tk.TclError:
        pass
    return menu
