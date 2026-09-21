# -*- coding: utf-8 -*-
"""Janela principal do Atualiza Arrecadacao: barra lateral, cabecalho e conteudo.

A casca nao sabe ler folha nem montar layout. Ela guarda o estado
compartilhado, roteia entre as telas e cuida do trabalho em andamento -- que
pertence ao aplicativo, e nao a tela, para que ir ate o cadastro de fontes
pagadoras nao interrompa a leitura de um PDF de 225 paginas.

O desenho segue o AtualizaPrev: nada encosta na moldura da janela. Sobre um
fundo cinza-nuvem flutuam tres pecas -- a barra lateral escura arredondada, o
cabecalho branco com o titulo da tela, e o conteudo em cartoes. O titulo deixou
de ser desenhado por cada tela: quem o pinta e o cabecalho, a partir de
`Tela.titulo` e `Tela.subtitulo`, como o AppHeader faz com a rota.
"""

from __future__ import annotations

import base64
import getpass
import logging
import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional

import tkinter as tk
from tkinter import messagebox, ttk

from .componentes import Balao, Superficie, chip, desenhar_arredondado, divisor
from .estado import Estado, Trabalho
from .identidade import (APP_NOME, APP_SUB, APP_VERSAO,
                         registrar_no_windows)
from .indice import Indice
from .preferencias import Preferencias, preparar_pasta_de_dados
from .tema import (COR_ACENTO_CLARO, COR_BARRA, COR_BARRA_ATIVO,
                   COR_BARRA_DESLIGADO, COR_BARRA_FORTE, COR_BARRA_FRACO,
                   COR_BARRA_HOVER, COR_BARRA_LINHA, COR_BARRA_PAINEL,
                   COR_BARRA_TEXTO, COR_CARTAO, COR_CHIP, COR_CHIP_TEXTO,
                   COR_DICA, COR_FUNDO, COR_MUDO, COR_TITULO, GAP, RAIO_BARRA,
                   RAIO_ITEM, T_LEGENDA, T_MARCA, T_MINI, T_TELA,
                   aplicar_estilo, fonte, fonte_icone, icone)

_log = logging.getLogger(__name__)

# 250, e nao os 236 do AutoArial: "Atualiza Arrecadacao" e quatro letras mais
# longo que "Atualiza Atuarial" e saia cortado na marca da barra.
LARGURA_BARRA = 250
LARGURA_BARRA_RECOLHIDA = 76
# Abaixo desta largura de janela a barra recolhe sozinha, como o
# COLLAPSE_BREAKPOINT do AppSidebar.
LARGURA_PARA_RECOLHER = 1140
ALTURA_CABECALHO = 72
LADO_LOGO = 48                 # um dos tamanhos que existem dentro do .ico


def png_do_icone(caminho: Path, lado: int) -> Optional[bytes]:
    """O PNG de `lado` px que esta dentro do `.ico`, ou o mais proximo.

    O `.ico` do aplicativo traz sete tamanhos, de 16 a 256 px, cada um reduzido
    com filtro de verdade por quem desenhou o icone. Reduzir o `logo.png` de
    1254 px com o `subsample` do Tk -- que joga linhas e colunas fora, sem
    media alguma -- desmanchava o desenho: era daí que vinha a logo serrilhada
    na barra lateral. Ler o `.ico` e so recortar bytes: cada entrada moderna
    ja e um PNG completo, que o Tk 8.6 carrega direto.
    """
    try:
        dados = caminho.read_bytes()
        _reservado, _tipo, quantas = struct.unpack("<HHH", dados[:6])
        entradas = []
        passo = 6
        for _ in range(quantas):
            (largura, _altura, _cores, _res, _planos, _bpp, tamanho,
             inicio) = struct.unpack("<BBBBHHII", dados[passo:passo + 16])
            passo += 16
            entradas.append((largura or 256, inicio, tamanho))
        if not entradas:
            return None
        # o exato, ou o menor que ainda seja maior do que o pedido
        entradas.sort(key=lambda e: (abs(e[0] - lado), -e[0]))
        _largura, inicio, tamanho = entradas[0]
        bruto = dados[inicio:inicio + tamanho]
        return bruto if bruto[:8] == b"\x89PNG\r\n\x1a\n" else None
    except Exception:                  # .ico ausente, truncado ou antigo
        return None


def _quem_esta_usando() -> "tuple[str, str]":
    """(nome legivel, iniciais) da conta do Windows que abriu o programa.

    `getpass.getuser()` devolve o login cru -- "joao.goncalves", "maria_silva".
    Na tela isso vira "Joao Goncalves": separa nos pontos, tracos e sublinhados
    e capitaliza cada parte. As iniciais alimentam o circulo do avatar.
    """
    try:
        bruto = (getpass.getuser() or "").strip()
    except Exception:                  # sem HOME nem USERNAME no ambiente
        bruto = ""
    if not bruto:
        return ("Usuário", "?")

    partes = [p for p in bruto.replace("_", " ").replace("-", " ")
              .replace(".", " ").split() if p]
    nome = " ".join(p[:1].upper() + p[1:] for p in partes) or bruto
    iniciais = "".join(p[:1].upper() for p in partes[:2]) or bruto[:1].upper()
    return (nome, iniciais)


def pasta_do_aplicativo() -> Path:
    """Onde ficam config, cache, logs e o indice de relatorios."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def pasta_de_recursos() -> Path:
    """Onde ficam os arquivos embutidos no programa (a pasta `assets`).

    NAO e a mesma de `pasta_do_aplicativo()`, e confundir as duas custou o
    icone da janela: o PyInstaller descompacta os dados em `_internal`
    (`sys._MEIPASS`),
    enquanto config, cache e logs ficam ao lado do executavel, onde o usuario
    os acha. Procurar `assets` ao lado do exe nao achava nada, e como a falha
    era silenciosa a janela ficava com o icone padrao do Tk.
    """
    embutida = getattr(sys, "_MEIPASS", None)
    if embutida:
        return Path(embutida)
    return Path(__file__).resolve().parent.parent


class ItemBarra(tk.Canvas):
    """Uma linha clicavel da barra lateral.

    E um Canvas, e nao um Frame com Labels dentro, por causa da pilula do item
    ativo: o Tk nao arredonda widget, e desenhar a pilula, o icone e os dois
    textos no mesmo Canvas deixa o realce, o modo recolhido e a linha de
    detalhe em um unico lugar -- um `_pintar()` que redesenha tudo.
    """

    ALTURA_SIMPLES = 38
    ALTURA_DUPLA = 50

    def __init__(self, dono: tk.Misc, chave: str, rotulo: str, descricao: str,
                 ao_clicar, numero: str = "", glifo: str = "") -> None:
        super().__init__(dono, bg=COR_BARRA, highlightthickness=0, bd=0,
                         takefocus=0, cursor="hand2")
        self.chave = chave
        self.rotulo = "{} · {}".format(numero, rotulo) if numero else rotulo
        self.descricao = descricao
        self.glifo = icone(glifo or chave)
        self._ao_clicar = ao_clicar
        self._ativo = False
        self._habilitado = True
        self._sob_o_mouse = False
        self._recolhido = False
        self._largura = 0

        self.balao = Balao(self, "")
        self._ajustar_altura()

        # `add="+"`: o Balao ja ouve Enter e Leave deste mesmo Canvas, e um
        # bind sem o "+" apagaria o dele.
        self.bind("<Configure>", self._ao_medir, add="+")
        self.bind("<Button-1>", self._clique, add="+")
        self.bind("<Enter>", lambda _e: self._realcar(True), add="+")
        self.bind("<Leave>", lambda _e: self._realcar(False), add="+")

    # ------------------------------------------------------------------ #
    def _ao_medir(self, evento) -> None:
        if evento.width == self._largura:
            return
        self._largura = evento.width
        self._pintar()

    def _ajustar_altura(self) -> None:
        dupla = bool(self.descricao) and not self._recolhido
        self.configure(height=self.ALTURA_DUPLA if dupla else self.ALTURA_SIMPLES)

    def _clique(self, _evento=None) -> None:
        if self._habilitado:
            self._ao_clicar(self.chave)

    def _realcar(self, dentro: bool) -> None:
        self._sob_o_mouse = dentro
        self._pintar()

    # ------------------------------------------------------------------ #
    def _pintar(self) -> None:
        largura = self._largura or self.winfo_width()
        altura = int(self["height"])
        if largura < 4:
            return

        self.delete("all")
        if self._ativo:
            realce = COR_BARRA_ATIVO
        elif self._sob_o_mouse and self._habilitado:
            realce = COR_BARRA_HOVER
        else:
            realce = ""
        if realce:
            desenhar_arredondado(self, 1, 1, largura - 2, altura - 2,
                                 RAIO_ITEM, preenchimento=realce,
                                 contorno=realce, cor_fora=COR_BARRA)

        if not self._habilitado:
            cor = COR_BARRA_DESLIGADO
        elif self._ativo:
            cor = COR_BARRA_FORTE
        else:
            cor = COR_BARRA_TEXTO

        if self._recolhido:
            self.create_text(largura / 2, altura / 2, text=self.glifo,
                             fill=cor, font=fonte_icone(16))
            return

        self.create_text(17, altura / 2, text=self.glifo, fill=cor,
                         anchor="w", font=fonte_icone(15))
        if self.descricao:
            self.create_text(43, altura / 2 - 8, text=self.rotulo, fill=cor,
                             anchor="w", font=fonte(T_LEGENDA, self._ativo))
            self.create_text(43, altura / 2 + 9, text=self.descricao,
                             fill=COR_BARRA_FRACO, anchor="w",
                             font=fonte(T_MINI), width=max(60, largura - 55))
        else:
            self.create_text(43, altura / 2, text=self.rotulo, fill=cor,
                             anchor="w", font=fonte(T_LEGENDA, self._ativo))

    # ------------------------------------------------------------------ #
    # a mesma interface de antes: a casca chama estes tres
    # ------------------------------------------------------------------ #
    def marcar_ativo(self, ativo: bool) -> None:
        self._ativo = ativo
        self._pintar()

    def definir_estado(self, habilitado: bool,
                       descricao: Optional[str] = None) -> None:
        self._habilitado = habilitado
        self.configure(cursor="hand2" if habilitado else "arrow")
        if descricao is not None and descricao != self.descricao:
            self.descricao = descricao
            self._ajustar_altura()
        self._atualizar_balao()
        self._pintar()

    def definir_recolhido(self, recolhido: bool) -> None:
        self._recolhido = recolhido
        self._ajustar_altura()
        self._atualizar_balao()
        self._pintar()

    def _atualizar_balao(self) -> None:
        # Recolhida, a barra mostra so o icone: sem o balao nao ha como saber
        # para onde o item leva.
        if not self._recolhido:
            self.balao.definir("")
            return
        texto = self.rotulo
        if self.descricao:
            texto += "  —  {}".format(self.descricao)
        self.balao.definir(texto)


class Janela(tk.Frame):
    """Casca: monta a barra lateral, hospeda as telas e drena os eventos."""

    def __init__(self, raiz: tk.Misc) -> None:
        super().__init__(raiz, bg=COR_FUNDO)
        self.raiz = raiz
        self.pack(fill="both", expand=True)

        raiz.title(APP_NOME)
        self._dimensionar(raiz)
        raiz.configure(bg=COR_FUNDO)

        # Duas pastas, de proposito: `pasta` e onde o programa mora (e de onde
        # sai o que vem embutido, como o config_diario.json), e `pasta_dados` e
        # onde ficam as coisas do usuario -- indice de relatorios e cache. A do
        # programa e substituida inteira a cada versao nova.
        self.pasta = pasta_do_aplicativo()
        self.pasta_dados = preparar_pasta_de_dados(self.pasta)
        self._definir_icone()
        self.estado = Estado(pasta_base=self.pasta_dados)
        self.trabalho = Trabalho()
        self.indice = Indice(self.pasta_dados)
        self.prefs = Preferencias.carregar()
        # O de/para das fontes pagadoras e carregado UMA vez, aqui: a tela de
        # cadastro edita este mesmo objeto e a tela da folha le dele na hora de
        # montar as linhas. Duas copias divergiriam no instante em que alguem
        # cadastrasse um codigo sem sair da tela.
        from arrecadacao.fontes import Cadastro
        self.cadastro = Cadastro.carregar(self.pasta_dados)

        aplicar_estilo()
        self.telas: Dict[str, object] = {}
        self.itens: Dict[str, ItemBarra] = {}
        # a navegacao guarda a ordem em que foi montada: recolher esconde os
        # rotulos de secao, e expandir tem de devolve-los ao lugar certo
        self._navegaveis: List[tk.Misc] = []
        self._secoes: List[tk.Label] = []
        self.atual = ""
        self.recolhida = False
        self._recolheu_pela_largura = False

        self._montar_barra()
        self._montar_direita()
        self._registrar_telas()

        self.ir_para("inicio")
        self.raiz.after(120, self._drenar)
        # add="+": o ComboBusca tambem ouve o Configure do toplevel
        self.raiz.bind("<Configure>", self._ao_redimensionar, add="+")
        self.raiz.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    # ------------------------------------------------------------------ #
    # construcao
    # ------------------------------------------------------------------ #
    @staticmethod
    def _dimensionar(raiz: tk.Misc) -> None:
        """Tamanho inicial que CABE na tela, e centrado nela.

        A medida era fixa em 1240x800, com minimo de 680 de altura. Num monitor
        de 1366x768 -- o do notebook do escritorio -- o rodape ficava abaixo da
        area visivel e a janela nao podia ser encolhida ate caber: o minimo era
        maior do que a tela util.
        """
        na_tela_x = raiz.winfo_screenwidth()
        na_tela_y = raiz.winfo_screenheight()
        largura = min(1320, na_tela_x - 80)
        altura = min(860, na_tela_y - 110)      # desconta a barra de tarefas
        raiz.geometry("{}x{}+{}+{}".format(
            largura, altura, max(0, (na_tela_x - largura) // 2),
            max(0, (na_tela_y - altura - 60) // 2)))
        raiz.minsize(min(980, largura), min(600, altura))

    def _definir_icone(self) -> None:
        """Icone da janela E da barra de tarefas.

        `iconbitmap(caminho)` sozinho nao basta no Windows: a janela ficava com
        a logo certa e a BARRA DE TAREFAS mostrava a pena do Tk. Duas coisas
        faltavam:

        * `default=` -- marca o icone como padrao da aplicacao, e nao apenas
          desta janela, o que substitui o icone de classe que o Tk registra;
        * um AppUserModelID proprio (`registrar_no_windows`), sem o qual a
          barra agrupa o processo pelo host e usa o icone dele.
        """
        # Ja foi feito no ponto de entrada, antes da janela existir; repetir
        # aqui e barato e cobre quem instancia a Janela direto (testes).
        falha = registrar_no_windows()
        if falha and sys.platform.startswith("win"):
            _log.warning("AppUserModelID nao definido: %s", falha)

        icone_arquivo = pasta_de_recursos() / "assets" / "favicon.ico"
        if not icone_arquivo.exists():
            _log.warning("icone nao encontrado em %s", icone_arquivo)
            return
        try:
            self.raiz.iconbitmap(default=str(icone_arquivo))
        except tk.TclError as erro:
            _log.warning("icone recusado pelo Tk: %s", erro)
            try:
                self.raiz.iconbitmap(str(icone_arquivo))   # ao menos a janela
            except tk.TclError:
                pass

    # ------------------------------------------------------------------ #
    def _montar_barra(self) -> None:
        self.barra = Superficie(self, cor=COR_BARRA, contorno="",
                                raio=RAIO_BARRA, padding=(10, 14))
        self.barra.pack(side="left", fill="y", padx=(GAP, 0), pady=GAP)
        self.barra.configure(width=LARGURA_BARRA)
        self.barra.pack_propagate(False)
        corpo = self.barra.corpo

        self._montar_marca(corpo)
        divisor(corpo, COR_BARRA_LINHA, padx=4, pady=(12, 10))
        self._montar_usuario(corpo)
        divisor(corpo, COR_BARRA_LINHA, padx=4, pady=(10, 8))

        self.navegacao = tk.Frame(corpo, bg=COR_BARRA)
        self.navegacao.pack(fill="both", expand=True)

        self._item("inicio", "Início", "", glifo="inicio")
        self._secao("FLUXO")
        self._item("folha", "Folha de pagamento", "nenhuma folha lida", "1",
                   glifo="diario")
        self._secao("CADASTRO")
        self._item("fontes", "Fontes pagadoras", "catálogo do SISPREVWEB",
                   glifo="engrenagem")
        self._item("exportacoes", "Exportações", "o que já foi gerado",
                   glifo="relatorios")

        # progresso do trabalho em andamento, visivel de qualquer tela
        self._montar_trabalho(corpo)
        self._montar_pe_da_barra(corpo)

    def _montar_marca(self, dono: tk.Misc) -> None:
        self.marca = tk.Frame(dono, bg=COR_BARRA)
        self.marca.pack(fill="x", padx=4)

        self._logo = self._carregar_logo()
        self.marca_logo = tk.Label(self.marca, bg=COR_BARRA, image=self._logo,
                                   text="" if self._logo else "AA",
                                   fg=COR_BARRA_FORTE,
                                   font=fonte(T_MARCA, True))
        self.marca_logo.pack(side="left")

        self.marca_texto = tk.Frame(self.marca, bg=COR_BARRA)
        self.marca_texto.pack(side="left", padx=(10, 0))
        tk.Label(self.marca_texto, text=APP_NOME, bg=COR_BARRA,
                 fg=COR_BARRA_FORTE, font=fonte(T_MARCA, True, titulo=True),
                 anchor="w").pack(fill="x")
        tk.Label(self.marca_texto, text=APP_SUB, bg=COR_BARRA,
                 fg=COR_BARRA_FRACO, font=fonte(T_MINI), anchor="w").pack(
            fill="x")

    def _carregar_logo(self, lado: int = LADO_LOGO) -> Optional[tk.PhotoImage]:
        """A logo do tamanho pedido, tirada de dentro do proprio `.ico`."""
        recursos = pasta_de_recursos() / "assets"
        bruto = png_do_icone(recursos / "favicon.ico", lado)
        if bruto:
            try:
                return tk.PhotoImage(
                    master=self.raiz,
                    data=base64.b64encode(bruto).decode("ascii"))
            except Exception as erro:
                _log.warning("PNG do .ico recusado pelo Tk: %s", erro)

        # Plano B: o PNG grande reduzido por inteiros. Serrilha -- e o motivo
        # de o caminho principal ser o .ico --, mas aparece.
        arquivo = recursos / "logo.png"
        if not arquivo.exists():
            return None
        try:
            cheia = tk.PhotoImage(master=self.raiz, file=str(arquivo))
            fator = max(1, round(cheia.width() / lado))
            return cheia.subsample(fator, fator)
        except Exception as erro:      # PNG recusado por um Tk antigo
            _log.warning("logo nao carregada: %s", erro)
            return None

    def _montar_usuario(self, dono: tk.Misc) -> None:
        """Quem esta usando -- o bloco de usuario da lateral do AtualizaPrev.

        NAO ha login neste aplicativo. O nome vem de `getpass.getuser()`, que
        no Windows le `%USERNAME%`: e a conta de quem abriu o programa, e muda
        de maquina para maquina -- que e justamente o que se quer, cada um ve o
        proprio nome. Nada disso e enviado para lugar nenhum, nem gravado nos
        relatorios; e so o rotulo da barra. A segunda linha diz "usuário do
        Windows" para ninguem supor uma conta do sistema que nao existe.
        """
        nome, iniciais = _quem_esta_usando()

        self.usuario = tk.Frame(dono, bg=COR_BARRA)
        self.usuario.pack(fill="x", padx=4)

        self.usuario_avatar = tk.Canvas(self.usuario, width=34, height=34,
                                        bg=COR_BARRA, highlightthickness=0,
                                        bd=0, takefocus=0)
        self.usuario_avatar.pack(side="left")
        # circulo desenhado com o canto suavizado: `create_oval` do Tk sai
        # em degraus, e um avatar serrilhado e o tipo de detalhe que faz a
        # tela parecer malfeita
        desenhar_arredondado(self.usuario_avatar, 1, 1, 32, 32, 16,
                             preenchimento="#252c40", contorno="#39415a",
                             cor_fora=COR_BARRA)
        self.usuario_avatar.create_text(
            17, 18, text=iniciais, fill="#cfd6e6", font=fonte(T_LEGENDA, True))

        self.usuario_nome = tk.Frame(self.usuario, bg=COR_BARRA)
        self.usuario_nome.pack(side="left", padx=(10, 0))
        tk.Label(self.usuario_nome, text=nome, bg=COR_BARRA, fg="#d9dde6",
                 font=fonte(T_LEGENDA, True), anchor="w").pack(fill="x")
        tk.Label(self.usuario_nome, text="usuário do Windows", bg=COR_BARRA,
                 fg=COR_BARRA_FRACO, font=fonte(T_MINI), anchor="w").pack(
            fill="x")

    def _secao(self, texto: str) -> None:
        rotulo = tk.Label(self.navegacao, text=texto, bg=COR_BARRA,
                          fg=COR_BARRA_FRACO, font=fonte(T_MINI, True),
                          anchor="w")
        self._secoes.append(rotulo)
        self._navegaveis.append(rotulo)
        self._empacotar_navegavel(rotulo)

    def _item(self, chave: str, rotulo: str, descricao: str,
              numero: str = "", glifo: str = "") -> None:
        item = ItemBarra(self.navegacao, chave, rotulo, descricao,
                         self.ir_para, numero, glifo)
        self.itens[chave] = item
        self._navegaveis.append(item)
        self._empacotar_navegavel(item)

    def _empacotar_navegavel(self, widget: tk.Misc) -> None:
        if isinstance(widget, ItemBarra):
            widget.pack(fill="x", pady=1)
        else:                                  # rotulo de secao
            widget.pack(fill="x", padx=14, pady=(14, 4))

    def _montar_trabalho(self, dono: tk.Misc) -> None:
        self.area_trabalho = tk.Frame(dono, bg=COR_BARRA)
        self.area_trabalho.pack(fill="x")

        self.painel_trabalho = Superficie(
            self.area_trabalho, cor=COR_BARRA_PAINEL, cor_fora=COR_BARRA,
            contorno="", raio=12, padding=(12, 10))
        self.var_trabalho = tk.StringVar(value="")
        self.rotulo_trabalho = tk.Label(
            self.painel_trabalho.corpo, textvariable=self.var_trabalho,
            bg=COR_BARRA_PAINEL, fg="#cfe0ff", font=fonte(T_MINI), anchor="w",
            wraplength=LARGURA_BARRA - 60, justify="left")
        self.rotulo_trabalho.pack(fill="x")
        self.barra_trabalho = ttk.Progressbar(
            self.painel_trabalho.corpo, style="Barra.Horizontal.TProgressbar")
        self.barra_trabalho.pack(fill="x", pady=(8, 2))

    def _montar_pe_da_barra(self, dono: tk.Misc) -> None:
        pe = tk.Frame(dono, bg=COR_BARRA)
        pe.pack(fill="x", pady=(12, 0))

        self.botao_recolher = tk.Canvas(pe, width=30, height=30, bg=COR_BARRA,
                                        highlightthickness=0, bd=0,
                                        takefocus=0, cursor="hand2")
        self.botao_recolher.pack(side="right")
        self.botao_recolher.bind("<Button-1>", lambda _e: self.alternar_barra(),
                                 add="+")
        self.balao_recolher = Balao(self.botao_recolher, "Recolher o menu")

        self.versao = tk.Label(pe, text="v" + APP_VERSAO, bg=COR_BARRA,
                               fg=COR_BARRA_DESLIGADO, font=fonte(T_MINI),
                               anchor="w")
        self.versao.pack(side="left", padx=(10, 0))
        self._pintar_botao_recolher()

    def _pintar_botao_recolher(self) -> None:
        tela = self.botao_recolher
        tela.delete("all")
        desenhar_arredondado(tela, 1, 1, 28, 28, 14,
                             preenchimento=COR_BARRA_HOVER,
                             contorno=COR_BARRA_HOVER, cor_fora=COR_BARRA)
        tela.create_text(15, 15,
                         text=icone("seta" if self.recolhida else "esquerda"),
                         fill=COR_BARRA_TEXTO, font=fonte_icone(11))

    # ------------------------------------------------------------------ #
    def _montar_direita(self) -> None:
        self.direita = tk.Frame(self, bg=COR_FUNDO)
        self.direita.pack(side="left", fill="both", expand=True, padx=GAP,
                          pady=GAP)

        self._montar_cabecalho()
        self._montar_rodape()
        self.conteudo = tk.Frame(self.direita, bg=COR_FUNDO)
        self.conteudo.pack(fill="both", expand=True)

    def _montar_cabecalho(self) -> None:
        """O cabecalho branco: titulo da tela e para onde vao os relatorios."""
        self.cabecalho = Superficie(self.direita, padding=(20, 12))
        self.cabecalho.pack(fill="x", pady=(0, GAP))
        self.cabecalho.configure(height=ALTURA_CABECALHO)
        self.cabecalho.pack_propagate(False)
        corpo = self.cabecalho.corpo

        destino = tk.Frame(corpo, bg=COR_CARTAO, cursor="hand2")
        destino.pack(side="right")
        pasta = chip(destino, icone("pasta"), cor=COR_CHIP,
                     cor_glifo=COR_CHIP_TEXTO, lado=34, tamanho=14)
        pasta.pack(side="left")
        textos_destino = tk.Frame(destino, bg=COR_CARTAO)
        textos_destino.pack(side="left", padx=(10, 0))
        tk.Label(textos_destino, text="Exportações em", bg=COR_CARTAO,
                 fg=COR_TITULO, font=fonte(T_LEGENDA, True), anchor="e").pack(
            fill="x")
        self.var_destino = tk.StringVar(value="")
        tk.Label(textos_destino, textvariable=self.var_destino, bg=COR_CARTAO,
                 fg=COR_DICA, font=fonte(T_MINI), anchor="e").pack(fill="x")
        for widget in (destino, pasta, textos_destino,
                       *textos_destino.winfo_children()):
            widget.bind("<Button-1>", lambda _e: self.ir_para("exportacoes"))

        textos = tk.Frame(corpo, bg=COR_CARTAO)
        textos.pack(side="left", fill="both", expand=True)
        self.var_titulo = tk.StringVar(value=APP_NOME)
        tk.Label(textos, textvariable=self.var_titulo, bg=COR_CARTAO,
                 fg=COR_TITULO, font=fonte(T_TELA, True, titulo=True),
                 anchor="w").pack(fill="x", pady=(2, 0))
        self.var_subtitulo = tk.StringVar(value="")
        tk.Label(textos, textvariable=self.var_subtitulo, bg=COR_CARTAO,
                 fg=COR_DICA, font=fonte(T_LEGENDA), anchor="w").pack(fill="x")

    def _montar_rodape(self) -> None:
        faixa = tk.Frame(self.direita, bg=COR_FUNDO)
        faixa.pack(side="bottom", fill="x", pady=(GAP, 0))

        ponto = tk.Canvas(faixa, width=8, height=8, bg=COR_FUNDO,
                          highlightthickness=0, bd=0, takefocus=0)
        desenhar_arredondado(ponto, 0, 0, 7, 7, 4,
                             preenchimento=COR_ACENTO_CLARO,
                             contorno=COR_ACENTO_CLARO, cor_fora=COR_FUNDO)
        ponto.pack(side="left", padx=(4, 8))

        self.var_rodape = tk.StringVar(value="Pronto.")
        tk.Label(faixa, textvariable=self.var_rodape, bg=COR_FUNDO,
                 fg=COR_MUDO, font=fonte(T_MINI), anchor="w").pack(
            side="left", fill="x", expand=True)

    def _registrar_telas(self) -> None:
        # importadas aqui para evitar dependencia circular com a casca
        from .tela_exportacoes import TelaExportacoes
        from .tela_folha import TelaFolha
        from .tela_fontes import TelaFontes
        from .tela_inicio import TelaInicio

        for chave, classe in (("inicio", TelaInicio), ("folha", TelaFolha),
                              ("fontes", TelaFontes),
                              ("exportacoes", TelaExportacoes)):
            self.telas[chave] = classe(self.conteudo, self)

    # ------------------------------------------------------------------ #
    # navegacao
    # ------------------------------------------------------------------ #
    def ir_para(self, chave: str) -> None:
        if chave not in self.telas or chave == self.atual:
            if chave in self.telas:
                self.telas[chave].ao_entrar()
            return

        if self.atual:
            self.telas[self.atual].quadro.pack_forget()
            self.itens[self.atual].marcar_ativo(False)

        self.atual = chave
        self._pintar_cabecalho(self.telas[chave])
        self.telas[chave].quadro.pack(fill="both", expand=True)
        self.itens[chave].marcar_ativo(True)
        self.telas[chave].ao_entrar()

    def _pintar_cabecalho(self, tela) -> None:
        self.var_titulo.set(getattr(tela, "titulo", "") or APP_NOME)
        self.var_subtitulo.set(getattr(tela, "subtitulo", "") or APP_SUB)
        self.atualizar_destino()

    def atualizar_destino(self) -> None:
        r"""O texto do bloco de destino, no canto direito do cabecalho.

        O caminho inteiro nao cabe, e cortado pela esquerda ("...ntos\AutoArial")
        nao se le. Das duas ultimas pastas -- "Documentos\AutoArial" -- se
        reconhece o lugar; o caminho completo continua na tela Exportacoes.
        """
        if self.prefs.ao_lado_da_origem:
            self.var_destino.set(self.prefs.descricao())
            return
        pasta = Path(self.prefs.pasta_relatorios)
        partes = [p for p in (pasta.parent.name, pasta.name) if p]
        self.var_destino.set("\\".join(partes) or str(pasta))

    def status(self, texto: str) -> None:
        self.var_rodape.set(texto)

    # ------------------------------------------------------------------ #
    # barra recolhida
    # ------------------------------------------------------------------ #
    def alternar_barra(self, recolhida: Optional[bool] = None) -> None:
        alvo = (not self.recolhida) if recolhida is None else recolhida
        if alvo == self.recolhida:
            return
        self.recolhida = alvo

        self.barra.configure(
            width=LARGURA_BARRA_RECOLHIDA if alvo else LARGURA_BARRA)
        if alvo:
            self.marca_texto.pack_forget()
            self.usuario_nome.pack_forget()
            self.versao.pack_forget()
            self.marca.pack_configure(padx=0)
            self.marca_logo.pack_configure(expand=True)
            self.usuario.pack_configure(padx=0)
            self.usuario_avatar.pack_configure(expand=True)
        else:
            self.marca.pack_configure(padx=4)
            self.marca_logo.pack_configure(expand=False)
            self.marca_texto.pack(side="left", padx=(10, 0))
            self.usuario.pack_configure(padx=4)
            self.usuario_avatar.pack_configure(expand=False)
            self.usuario_nome.pack(side="left", padx=(10, 0))
            self.versao.pack(side="left", padx=(10, 0))

        # Recolhida, a barra fica so com os icones: os rotulos de secao saem.
        # Reempacotar tudo na ordem guardada e o que evita que eles voltem
        # depois dos itens ao expandir.
        for widget in self._navegaveis:
            widget.pack_forget()
        for widget in self._navegaveis:
            if alvo and widget in self._secoes:
                continue
            self._empacotar_navegavel(widget)

        for item in self.itens.values():
            item.definir_recolhido(alvo)

        self.rotulo_trabalho.configure(
            wraplength=(LARGURA_BARRA_RECOLHIDA - 40) if alvo
            else (LARGURA_BARRA - 60))
        self._pintar_botao_recolher()
        self.balao_recolher.definir(
            "Expandir o menu" if alvo else "Recolher o menu")

    def _ao_redimensionar(self, evento) -> None:
        """Janela estreita recolhe a barra sozinha, e larga a devolve."""
        if evento.widget is not self.raiz:
            return
        estreita = evento.width < LARGURA_PARA_RECOLHER
        if estreita and not self.recolhida:
            self.alternar_barra(True)
            self._recolheu_pela_largura = True
        elif not estreita and self.recolhida and self._recolheu_pela_largura:
            self.alternar_barra(False)
            self._recolheu_pela_largura = False

    # ------------------------------------------------------------------ #
    # trabalho em andamento
    # ------------------------------------------------------------------ #
    def iniciar_trabalho(self, dono: str, rotulo: str, tarefa, cancelar=None) -> bool:
        """Dispara a tarefa. Avisa e recusa se ja houver outra rodando."""
        if not self.trabalho.iniciar(dono, rotulo, tarefa, cancelar):
            messagebox.showinfo(
                APP_NOME,
                "Já há um trabalho em andamento:\n\n{}\n\nEspere terminar ou "
                "cancele antes de iniciar outro.".format(self.trabalho.rotulo))
            return False
        self.painel_trabalho.pack(fill="x", pady=(12, 0))
        self.var_trabalho.set(rotulo)
        self.barra_trabalho.configure(mode="indeterminate")
        self.barra_trabalho.start(12)
        self.status(rotulo)
        return True

    def _drenar(self) -> None:
        """Entrega os eventos da thread a tela que pediu o trabalho."""
        for evento in self.trabalho.eventos():
            tela = self.telas.get(evento.dono)
            if evento.tipo == "progresso":
                feitos, total, texto = evento.dado
                self._pintar_progresso(feitos, total, texto)
                if tela is not None:
                    tela.ao_progresso(feitos, total, texto)
            else:
                self._encerrar_progresso()
                if tela is None:
                    continue
                if evento.tipo == "fim":
                    tela.ao_concluir(evento.dado)
                else:
                    tela.ao_falhar(evento.dado)
        self.raiz.after(120, self._drenar)

    def _pintar_progresso(self, feitos: int, total: int, texto: str) -> None:
        if total > 0:
            if str(self.barra_trabalho["mode"]) != "determinate":
                self.barra_trabalho.stop()
                self.barra_trabalho.configure(mode="determinate", maximum=total)
            self.barra_trabalho["value"] = feitos
            self.var_trabalho.set("{}\n{}/{}".format(self.trabalho.rotulo, feitos, total))
        if texto:
            self.status(texto)

    def _encerrar_progresso(self) -> None:
        self.barra_trabalho.stop()
        self.barra_trabalho.configure(mode="determinate", maximum=100)
        self.barra_trabalho["value"] = 0
        self.painel_trabalho.pack_forget()

    # ------------------------------------------------------------------ #
    def atualizar_barra(self) -> None:
        """Reflete na barra lateral o que ja esta disponivel."""
        self.itens["folha"].definir_estado(True, self.estado.descrever_folha())

        # Quantas fontes desta folha ainda estao sem codigo. E o unico aviso
        # que aparece de QUALQUER tela: quem esta conferindo a tabela precisa
        # ver que faltam codigos antes de chegar ao botao de exportar.
        pendentes = self.fontes_pendentes()
        if pendentes:
            descricao = "{} fonte(s) sem código".format(len(pendentes))
        elif self.estado.municipio:
            descricao = "{} · {} fonte(s)".format(
                self.estado.municipio,
                len(self.cadastro.fontes_de(self.estado.municipio)))
        else:
            descricao = "catálogo do SISPREVWEB"
        self.itens["fontes"].definir_estado(True, descricao)

    def rotulos_de_municipio(self, com_contagem: bool = False) -> tuple:
        """Os 29 municipios com uma marca em quem ja tem catalogo importado.

        Devolve (rotulos, {rotulo: municipio}). A marca existe porque a lista
        e sempre a mesma, com e sem cadastro: sem ela, escolher um municipio
        que nunca foi importado da uma tela de 59 pendencias, e a causa --
        "este municipio ainda nao tem catalogo" -- so aparece depois. Com a
        marca, isso se ve antes de escolher.

        Mora na janela porque as duas telas mostram a MESMA lista, e a fonte da
        verdade e o cadastro, que e da janela.
        """
        from arrecadacao.municipios import MUNICIPIOS

        rotulos, de_rotulo = [], {}
        for municipio in MUNICIPIOS:
            quantas = len(self.cadastro.fontes_de(municipio))
            if not com_contagem:
                rotulo = "{}  {}".format("✓" if quantas else "·", municipio)
            elif quantas:
                rotulo = "✓  {}  —  {} fontes".format(
                    municipio, "{:,}".format(quantas).replace(",", "."))
            else:
                rotulo = "·  {}  —  sem catálogo".format(municipio)
            rotulos.append(rotulo)
            de_rotulo[rotulo] = municipio
        return (rotulos, de_rotulo)

    def casar_fontes(self) -> dict:
        """Refaz o casamento das fontes da folha com o catalogo do municipio.

        Mora na janela, e nao na tela da folha, porque as duas telas precisam
        do mesmo resultado: a da folha para montar as linhas, a de fontes para
        dizer o que falta. Guardado no estado para nao recasar 59 fontes contra
        1.215 a cada tecla digitada.
        """
        if not self.estado.tem_folha():
            self.estado.correspondencias = {}
            return self.estado.correspondencias
        self.estado.correspondencias = self.cadastro.casar_todas(
            self.estado.municipio, self.estado.folha.fontes)
        return self.estado.correspondencias

    def fontes_pendentes(self) -> List:
        """As fontes da folha carregada que ainda estao sem codigo."""
        return [c for c in self.estado.correspondencias.values()
                if not c.resolvida]

    def codigo_da_fonte(self, fonte) -> tuple:
        """(codigo, origem) de uma fonte da folha. Passado ao `layout.montar`."""
        if fonte is None:
            return ("", "")
        achado = self.estado.correspondencias.get(fonte.chave)
        return (achado.codigo, achado.origem) if achado else ("", "")

    def _ao_fechar(self) -> None:
        if self.trabalho.ocupado:
            if not messagebox.askyesno(
                    APP_NOME,
                    "Há um trabalho em andamento:\n\n{}\n\nEncerrar mesmo assim?"
                    .format(self.trabalho.rotulo)):
                return
            self.trabalho.pedir_cancelamento()
        self.raiz.destroy()
