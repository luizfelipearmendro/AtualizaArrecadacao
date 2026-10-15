# -*- coding: utf-8 -*-
"""Contrato comum das telas hospedadas pela casca."""

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from .identidade import APP_NOME
from .tema import COR_FUNDO, GAP


class Tela:
    """Base das telas.

    A casca chama `ao_entrar()` toda vez que a tela aparece e entrega os
    eventos do trabalho em andamento por `ao_progresso`, `ao_concluir` e
    `ao_falhar` -- que so chegam se o trabalho tiver sido pedido por esta tela.

    A tela NAO desenha mais o proprio titulo: quem o pinta e o cabecalho da
    janela, lendo `titulo` e `subtitulo`. Antes cada tela repetia a linha de
    titulo e o filete abaixo dela, e o resultado era um titulo por tela em vez
    de um cabecalho do aplicativo -- que e como o AtualizaPrev faz.
    """

    chave = ""
    titulo = ""
    subtitulo = ""

    def __init__(self, dono: tk.Misc, janela) -> None:
        self.janela = janela
        self.estado = janela.estado
        self.quadro = tk.Frame(dono, bg=COR_FUNDO)

        # A pagina ROLA. Sem isso, os cartoes empilhados nao cabiam numa
        # janela de 860 e o `pack` resolvia espremendo o ultimo da fila: a
        # tabela virava um risco de 1 pixel e o titulo dela saia por cima do
        # aviso. Aparar pixel a pixel adiou o problema tres vezes -- com o
        # cartao das fontes aberto E um aviso na tela, a conta simplesmente
        # nao fecha, e a saida honesta e deixar a pagina rolar.
        self._tela = tk.Canvas(self.quadro, bg=COR_FUNDO, highlightthickness=0,
                               bd=0, takefocus=0)
        self._barra_tela = ttk.Scrollbar(self.quadro, orient="vertical",
                                         command=self._tela.yview)
        self._tela.configure(yscrollcommand=self._barra_tela.set)
        self._precisa_rolar = False
        self._tela.pack(side="left", fill="both", expand=True)

        self.corpo = tk.Frame(self._tela, bg=COR_FUNDO)
        self._janela_corpo = self._tela.create_window((0, 0), window=self.corpo,
                                                      anchor="nw")
        self._tela.bind("<Configure>", lambda _e: self._ajustar_rolagem())
        self.corpo.bind("<Configure>", lambda _e: self._ajustar_rolagem())

        self.montar()

    # ------------------------------------------------------------------ #
    # rolagem da pagina
    # ------------------------------------------------------------------ #
    def _ajustar_rolagem(self) -> None:
        """Acerta a largura do corpo e decide se a barra precisa aparecer.

        A altura do corpo e o MAIOR entre o que ele pede e o que a tela tem:
        sobrando espaco, a tabela cresce como sempre cresceu; faltando, o corpo
        fica do tamanho que pede e a pagina rola.
        """
        try:
            largura = self._tela.winfo_width()
            altura = self._tela.winfo_height()
            pedida = self.corpo.winfo_reqheight()
        except tk.TclError:
            return
        if largura <= 1:
            return

        self._tela.itemconfigure(self._janela_corpo, width=largura,
                                 height=max(pedida, altura))
        self._tela.configure(scrollregion=(0, 0, largura, max(pedida, altura)))

        # Quem decide se ha o que rolar e a MEDIDA, e nao o `yscrollcommand`:
        # o canvas nao o dispara de forma confiavel quando o conteudo cresce,
        # e a barra ficava escondida numa pagina que ja nao cabia -- com ela
        # escondida, a roda do mouse tambem desistia de rolar.
        self._precisa_rolar = pedida > altura
        if self._precisa_rolar and not self._barra_tela.winfo_manager():
            self._barra_tela.pack(side="right", fill="y")
        elif not self._precisa_rolar and self._barra_tela.winfo_manager():
            self._barra_tela.pack_forget()
            self._tela.yview_moveto(0)

    def repensar_rolagem(self) -> None:
        """Refaz a conta da rolagem depois de MUDAR o que esta na pagina.

        E' obrigatorio chamar isto, e nao da para confiar no `<Configure>` do
        corpo: a altura do corpo e DITADA pelo canvas, nao pelos filhos dele.
        Acrescentar cartoes faz o corpo PEDIR mais, mas nao muda o tamanho que
        ele tem -- nenhum evento dispara, e a pagina continua decidida pela
        medida de antes.

        Foi esse o defeito: lida a folha, o corpo passava a pedir 1.240 pixels
        numa area de 517 e mesmo assim `_precisa_rolar` seguia falso. Sem
        rolagem, o `pack` resolvia espremendo os ultimos da fila -- a tabela
        virava 1 pixel e o cartao das fontes aparecia cortado no meio da
        legenda, dizendo que falta resolver uma fonte e sem a linha para
        resolve-la. Nos testes nao aparecia porque redimensionar a janela
        dispara o `<Configure>` do canvas e conserta por acidente.

        Na fila de ociosidade porque quem chama acabou de empacotar coisas: a
        medida so vale depois de o Tk refazer o arranjo.
        """
        try:
            self.quadro.after_idle(self._ajustar_rolagem)
        except tk.TclError:
            pass

    def rola_sozinho(self, widget: tk.Misc) -> bool:
        """O ponteiro esta sobre algo que ja rola por conta propria?

        A tabela de 774 linhas e a lista de fontes pendentes tem a sua propria
        barra. Sobre elas, a roda do mouse e delas -- rolar a pagina junto
        faria a tela fugir debaixo de quem so queria descer uma linha.
        """
        atual = widget
        while atual is not None and atual is not self.corpo:
            if isinstance(atual, (ttk.Treeview, ttk.Combobox)) or                     getattr(atual, "rola_sozinho_", False):
                return True
            atual = getattr(atual, "master", None)
        return False

    def rolar(self, evento) -> None:
        """A roda do mouse, vinda da janela, quando esta tela esta visivel.

        O ponteiro pode estar sobre uma janela que o Tk criou por fora do
        Python -- a lista que a caixa de selecao abre e uma dessas, chamada
        `popdown`. `winfo_containing` devolve o nome dela e `nametowidget`
        levanta KeyError, que numa callback de evento vira caixa de erro na
        cara do usuario; pior, a lista aberta fecha escolhendo o item que
        estava sob o cursor -- o municipio trocava sozinho para o primeiro da
        lista. Nao sabendo onde o ponteiro esta, a pagina nao rola e o Tk
        cuida do resto, que e o comportamento certo para a lista aberta.
        """
        try:
            alvo = self.quadro.winfo_containing(evento.x_root, evento.y_root)
        except (tk.TclError, KeyError):
            return
        if alvo is None or self.rola_sozinho(alvo):
            return
        if not self._precisa_rolar:
            return                      # cabe tudo: nao ha o que rolar
        try:
            self._tela.yview_scroll(-1 * (evento.delta // 120), "units")
        except tk.TclError:
            pass

    def espacar(self, dono: tk.Misc = None, altura: int = GAP) -> tk.Frame:
        """Um respiro entre cartoes, do tamanho do gap da pagina."""
        folga = tk.Frame(dono or self.corpo, bg=COR_FUNDO, height=altura)
        folga.pack(fill="x")
        return folga

    # ------------------------------------------------------------------ #
    # ganchos
    # ------------------------------------------------------------------ #
    def montar(self) -> None:
        """Constroi o conteudo da tela em `self.corpo`."""

    def ao_entrar(self) -> None:
        """Chamado sempre que a tela passa a ser exibida."""

    def ao_progresso(self, feitos: int, total: int, texto: str) -> None:
        """Progresso do trabalho pedido por esta tela."""

    def ao_concluir(self, resultado: Any) -> None:
        """Trabalho desta tela terminou com sucesso."""

    def ao_falhar(self, detalhe: str) -> None:
        """Trabalho desta tela terminou com erro."""
        from tkinter import messagebox
        messagebox.showerror(APP_NOME, detalhe[:1500])
        self.janela.status("Falha.")
