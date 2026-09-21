# -*- coding: utf-8 -*-
"""Lista dos arquivos que o programa gerou, e onde ele os grava.

A escolha da pasta vive aqui, e nao numa tela de configuracoes propria: quem
quer mudar onde as exportacoes caem esta, quase sempre, procurando uma
exportacao.

Entradas cujo arquivo nao existe mais continuam na lista, marcadas. Saber que
a competencia 07/2026 foi exportada -- e que alguem moveu o arquivo -- e
informacao; a lista que esconde isso faz parecer que o mes nunca foi gerado.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .base_tela import Tela
from .componentes import Botao, Cartao, CaixaCampo, campo_texto
from .identidade import APP_NOME
from .ordenacao import Ordenador
from .tema import COR_CARTAO, COR_DICA, COR_ERRO, GAP

COLUNAS = (("quando", "Gerado em", 130), ("tipo", "Formato", 80),
           ("arquivo", "Arquivo", 300), ("resumo", "Conteúdo", 300),
           ("situacao", "Situação", 110))


class TelaExportacoes(Tela):
    chave = "exportacoes"
    titulo = "Exportações"
    subtitulo = "o que já foi gerado, e onde os próximos arquivos serão gravados"

    def montar(self) -> None:
        self._montar_pasta()
        self._montar_lista()

    # ------------------------------------------------------------------ #
    def _montar_pasta(self) -> None:
        prefs = self.janela.prefs
        cartao = Cartao(
            self.corpo, titulo="Onde salvar", glifo="pasta",
            legenda="A pasta sugerida ao exportar. O nome do arquivo continua "
                    "confirmável na hora de salvar.")
        cartao.pack(fill="x", pady=(0, GAP))

        self.var_modo = tk.StringVar(
            value="origem" if prefs.ao_lado_da_origem else "fixa")
        self.var_pasta = tk.StringVar(value=str(prefs.pasta_relatorios))

        alto = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        alto.pack(fill="x")
        ttk.Radiobutton(alto, text="Nesta pasta:", value="fixa",
                        variable=self.var_modo,
                        command=self._trocar_modo).pack(side="left")
        Botao(alto, text="ABRIR", command=self._abrir_destino).pack(side="right")
        self.btn_alterar = Botao(alto, text="ALTERAR...",
                                 command=self._escolher_pasta)
        self.btn_alterar.pack(side="right", padx=8)
        self.caixa_pasta, self.campo_pasta = campo_texto(alto, self.var_pasta)
        self.campo_pasta.configure(state="readonly")
        self.caixa_pasta.pack(side="left", fill="x", expand=True, padx=10)

        ttk.Radiobutton(
            cartao.conteudo,
            text="Ao lado do PDF lido — cada exportação na pasta de onde veio "
                 "a folha",
            value="origem", variable=self.var_modo,
            command=self._trocar_modo).pack(anchor="w", pady=(10, 0))

        self._pintar_modo()

    def _trocar_modo(self) -> None:
        prefs = self.janela.prefs
        prefs.ao_lado_da_origem = self.var_modo.get() == "origem"
        prefs.salvar()
        self._pintar_modo()
        self.janela.atualizar_destino()

    def _pintar_modo(self) -> None:
        fixa = self.var_modo.get() == "fixa"
        self.caixa_pasta.desligar(not fixa)
        self.btn_alterar.configure(state="normal" if fixa else "disabled")

    def _escolher_pasta(self) -> None:
        escolhida = filedialog.askdirectory(
            title="Pasta das exportações", initialdir=self.var_pasta.get())
        if not escolhida:
            return
        self.var_pasta.set(escolhida)
        self.janela.prefs.pasta_relatorios = Path(escolhida)
        self.janela.prefs.salvar()
        self.janela.atualizar_destino()

    def _abrir_destino(self) -> None:
        destino = Path(self.var_pasta.get())
        try:
            destino.mkdir(parents=True, exist_ok=True)
            os.startfile(str(destino))     # type: ignore[attr-defined]
        except OSError as erro:
            messagebox.showerror(
                APP_NOME, "Não foi possível abrir a pasta:\n\n{}".format(erro))

    # ------------------------------------------------------------------ #
    def _montar_lista(self) -> None:
        cartao = Cartao(
            self.corpo, titulo="Arquivos gerados", glifo="relatorios",
            legenda="Clique num título para ordenar. Clique duplo abre o "
                    "arquivo.", padding=(14, 14))
        cartao.pack(fill="both", expand=True)

        # A linha de botoes e montada ANTES da tabela e ancorada embaixo: o
        # pack serve os widgets na ordem em que os recebe, e a tabela cresce
        # (`expand`) -- vindo depois, os botoes seriam cortados na janela baixa.
        acoes = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        acoes.pack(side="bottom", fill="x", pady=(12, 0))
        Botao(acoes, text="ABRIR", primario=True,
              command=self._abrir).pack(side="right", padx=(8, 0))
        Botao(acoes, text="ABRIR A PASTA",
              command=self._abrir_pasta_do_arquivo).pack(side="right")
        Botao(acoes, text="TIRAR DA LISTA", sutil=True,
              command=self._remover).pack(side="left")

        moldura = CaixaCampo(cartao.conteudo, padding=(1, 1))
        moldura.pack(fill="both", expand=True)
        quadro = tk.Frame(moldura.corpo, bg=COR_CARTAO)
        quadro.pack(fill="both", expand=True)

        chaves = [c[0] for c in COLUNAS]
        self.tabela = ttk.Treeview(quadro, columns=chaves, show="headings",
                                   selectmode="browse", height=10)
        for chave, _titulo, largura in COLUNAS:
            self.tabela.column(chave, width=largura, minwidth=60, anchor="w",
                               stretch=(chave in ("arquivo", "resumo")))
        self.tabela.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(quadro, orient="vertical",
                              command=self.tabela.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.tabela.configure(yscrollcommand=barra.set)
        quadro.rowconfigure(0, weight=1)
        quadro.columnconfigure(0, weight=1)

        self.tabela.tag_configure("sumido", foreground=COR_DICA)
        self.tabela.bind("<Double-1>", lambda _e: self._abrir())

        self.ordenador = Ordenador(self.tabela,
                                   {c[0]: c[1] for c in COLUNAS})
        self.registros: List = []

    # ------------------------------------------------------------------ #
    def _selecionado(self):
        escolha = self.tabela.selection()
        if not escolha:
            return None
        try:
            return self.registros[int(escolha[0])]
        except (ValueError, IndexError):
            return None

    def _abrir(self) -> None:
        registro = self._selecionado()
        if registro is None:
            return
        if not registro.existe:
            messagebox.showinfo(
                APP_NOME,
                "O arquivo não está mais em:\n\n{}".format(registro.caminho))
            return
        try:
            os.startfile(registro.caminho)     # type: ignore[attr-defined]
        except OSError as erro:
            messagebox.showerror(APP_NOME, str(erro))

    def _abrir_pasta_do_arquivo(self) -> None:
        registro = self._selecionado()
        if registro is None:
            return
        pasta = Path(registro.caminho).parent
        try:
            os.startfile(str(pasta))           # type: ignore[attr-defined]
        except OSError as erro:
            messagebox.showerror(APP_NOME, str(erro))

    def _remover(self) -> None:
        """Tira da LISTA, nunca do disco.

        O botao diz "tirar da lista" e faz exatamente isso. Apagar o arquivo
        daqui seria apagar uma exportacao que talvez ja tenha sido enviada.
        """
        registro = self._selecionado()
        if registro is None:
            return
        self.janela.indice.remover(registro.caminho)
        self._recarregar()

    # ------------------------------------------------------------------ #
    def _recarregar(self) -> None:
        self.ordenador.esvaziar()
        self.registros = self.janela.indice.carregar()
        for indice, registro in enumerate(self.registros):
            existe = registro.existe
            self.tabela.insert(
                "", "end", iid=str(indice),
                tags=() if existe else ("sumido",),
                values=(registro.quando, registro.tipo.upper(), registro.nome,
                        registro.resumo,
                        "no lugar" if existe else "movido ou apagado"))
        self.ordenador.reaplicar()

    def ao_entrar(self) -> None:
        self.var_pasta.set(str(self.janela.prefs.pasta_relatorios))
        self.var_modo.set(
            "origem" if self.janela.prefs.ao_lado_da_origem else "fixa")
        self._pintar_modo()
        self._recarregar()
        self.janela.status("{} exportação(ões) no histórico.".format(
            len(self.registros)))
