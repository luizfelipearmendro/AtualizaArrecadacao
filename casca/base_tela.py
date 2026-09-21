# -*- coding: utf-8 -*-
"""Contrato comum das telas hospedadas pela casca."""

from __future__ import annotations

from typing import Any

import tkinter as tk

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
        self.corpo = tk.Frame(self.quadro, bg=COR_FUNDO)
        self.corpo.pack(fill="both", expand=True)
        self.montar()

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
