# -*- coding: utf-8 -*-
"""O catalogo de fontes pagadoras: importar o arquivo do SISPREVWEB e conferir.

Aqui nao se digita fonte a fonte. O SISPREVWEB exporta o cadastro inteiro em
duas colunas -- FONTE_PAG_ID e NOME --, e sao 1.215 fontes so em Aripuana:
digitar isso a mao nao e trabalho, e erro esperando acontecer. O arquivo entra
de uma vez, por municipio, e a tela da folha casa sozinha o que der.

O municipio e escolhido ANTES de importar, e nao lido do arquivo, porque o
arquivo nao diz de qual prefeitura ele e -- e os nomes se repetem entre as 29.
Importar o de uma cidade sobre o cadastro de outra casaria tudo, sem erro
nenhum, creditando a arrecadacao inteira na fonte errada.

O que esta tela mostra do catalogo e uma amostra com busca, e nao as 1.215
linhas: ninguem confere mil e duzentas fontes numa tela: o que se quer saber e
"o arquivo entrou?" e "esta fonte esta aqui?".
"""

from __future__ import annotations

from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .base_tela import Tela
from .componentes import (Botao, Cartao, Superficie, acompanhar_largura,
                          campo_texto, chip, moldura_de_lista)
from .identidade import APP_NOME
from .tema import (COR_BORDA, COR_CARTAO, COR_CHIP, COR_CHIP_TEXTO, COR_DICA,
                   COR_MUDO, GAP, RAIO_LINHA, T_LEGENDA, T_MINI, fonte, icone)

# Quantas linhas do catalogo a lista mostra. E' amostra, nao conferencia: o
# campo de busca e que serve para achar uma fonte especifica.
MOSTRAR_ATE = 60


class TelaFontes(Tela):
    chave = "fontes"
    titulo = "Fontes pagadoras"
    subtitulo = "o catálogo do SISPREVWEB, importado por município"

    def montar(self) -> None:
        # A caixa guarda o ROTULO ("✓  ARIPUANÃ  —  1.215 fontes"), e nao o
        # nome puro: e a lista fechada que responde "de quais municipios ja
        # importei o arquivo?". `_escolhido` desfaz.
        self.var_municipio = tk.StringVar()
        self._de_rotulo: dict = {}
        self.var_busca = tk.StringVar()
        self._silencio = False

        self._montar_municipio()
        self._montar_importacao()
        self._montar_lista()

        self.var_municipio.trace_add("write", lambda *_a: self._trocar())
        self.var_busca.trace_add("write", lambda *_a: self._pintar_lista())

    # ------------------------------------------------------------------ #
    # o municipio
    # ------------------------------------------------------------------ #
    def _montar_municipio(self) -> None:
        cartao = Cartao(
            self.corpo, titulo="Município", glifo="globo",
            legenda="Cada município tem o seu catálogo. O da folha aberta vem "
                    "escolhido pelo cabeçalho do PDF.")
        cartao.pack(fill="x", pady=(0, GAP))

        linha = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        linha.pack(fill="x")

        moldura = moldura_de_lista(linha)
        moldura.pack(side="left")
        self.combo_municipio = ttk.Combobox(
            moldura.corpo, state="readonly", textvariable=self.var_municipio,
            width=40, style="Plano.TCombobox")
        self.combo_municipio.pack()
        moldura.acompanhar(self.combo_municipio)
        self.combo_municipio.bind("<MouseWheel>", lambda e: "break")

        self.var_situacao = tk.StringVar(value="")
        tk.Label(linha, textvariable=self.var_situacao, bg=COR_CARTAO,
                 fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w",
                 justify="left").pack(side="left", fill="x", expand=True,
                                      padx=(GAP, 0))

    # ------------------------------------------------------------------ #
    # a importacao
    # ------------------------------------------------------------------ #
    def _montar_importacao(self) -> None:
        cartao = Cartao(
            self.corpo, titulo="Importar o arquivo do SISPREVWEB",
            glifo="planilha",
            legenda="Exporte as fontes pagadoras no SISPREVWEB e traga o "
                    "arquivo aqui. Ele substitui o catálogo deste município.")
        cartao.pack(fill="x", pady=(0, GAP))
        self.cartao_importacao = cartao

        # O formato exigido, escrito. E' a primeira coisa que alguem erra --
        # exporta com outras colunas, ou renomeia "NOME" para "DESCRICAO" -- e
        # a mensagem de erro depois do fato custa uma ida ao SISPREVWEB.
        exigencia = Superficie(cartao.conteudo, raio=RAIO_LINHA,
                               contorno=COR_BORDA, padding=(14, 12))
        exigencia.pack(fill="x")
        chip(exigencia.corpo, icone("informacao"), cor=COR_CHIP,
             cor_glifo=COR_CHIP_TEXTO, cor_fora=COR_CARTAO, lado=30,
             tamanho=14).pack(side="left", padx=(0, 12))
        texto = tk.Label(
            exigencia.corpo,
            text="O arquivo precisa ser .csv ou .xlsx e ter duas colunas, com "
                 "estes nomes na primeira linha:\n"
                 "      FONTE_PAG_ID  —  o código de integração (5085)\n"
                 "      NOME  —  o nome da fonte (001 - 2002 -GABINETE "
                 "EFETIVOS F 1.500)\n"
                 "A ordem das colunas não importa; outras colunas são "
                 "ignoradas.",
            bg=COR_CARTAO, fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w",
            justify="left")
        texto.pack(side="left", fill="x", expand=True)
        acompanhar_largura(texto, folga=80)

        acao = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        acao.pack(fill="x", pady=(12, 0))
        self.btn_importar = Botao(acao, text="IMPORTAR ARQUIVO...",
                                  primario=True, command=self._importar)
        self.btn_importar.pack(side="right")
        self.btn_esquecer = Botao(acao, text="APAGAR ESTE CATÁLOGO",
                                  command=self._esquecer)
        self.btn_esquecer.pack(side="right", padx=(0, 8))

        self.var_ultima = tk.StringVar(value="")
        tk.Label(acao, textvariable=self.var_ultima, bg=COR_CARTAO,
                 fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w",
                 justify="left").pack(side="left", fill="x", expand=True)

    def _escolhido(self) -> str:
        return self._de_rotulo.get(self.var_municipio.get(), "")

    def _recarregar_municipios(self) -> None:
        """Refaz a lista com a marca e a contagem, sem perder a escolha."""
        rotulos, self._de_rotulo = self.janela.rotulos_de_municipio(
            com_contagem=True)
        self.combo_municipio.configure(values=rotulos)
        alvo = next((r for r, m in self._de_rotulo.items()
                     if m == self.estado.municipio), "")
        self._silencio = True
        try:
            self.var_municipio.set(alvo)
        finally:
            self._silencio = False

    def _importar(self) -> None:
        municipio = self._escolhido()
        if not municipio:
            messagebox.showwarning(
                APP_NOME, "Escolha o município antes de importar o arquivo.")
            return

        caminho = filedialog.askopenfilename(
            title="Fontes pagadoras exportadas do SISPREVWEB ({})".format(
                municipio),
            filetypes=[("Planilha ou CSV", "*.csv;*.xlsx;*.xlsm"),
                       ("CSV", "*.csv"), ("Excel", "*.xlsx;*.xlsm"),
                       ("Todos os arquivos", "*.*")])
        if not caminho:
            return

        from arrecadacao import fontes as modulo_fontes
        cadastro = self.janela.cadastro
        havia = len(cadastro.fontes_de(municipio))
        if havia and not messagebox.askyesno(
                APP_NOME,
                "{} já tem {} fonte(s) cadastradas.\n\nO arquivo SUBSTITUI "
                "esse catálogo — o que não estiver nele deixa de existir "
                "aqui.\n\nImportar mesmo assim?".format(municipio, havia)):
            return

        try:
            lidas, avisos = modulo_fontes.ler_arquivo(Path(caminho))
        except modulo_fontes.ArquivoInvalido as erro:
            messagebox.showerror(
                APP_NOME, "Não deu para importar:\n\n{}".format(erro))
            return
        except Exception as erro:                       # arquivo corrompido
            messagebox.showerror(
                APP_NOME,
                "Não deu para ler o arquivo:\n\n{}: {}".format(
                    type(erro).__name__, erro))
            return

        cadastro.definir_catalogo(municipio, lidas)
        if not cadastro.salvar():
            messagebox.showerror(
                APP_NOME,
                "O catálogo vale nesta sessão, mas não pôde ser gravado "
                "em:\n\n{}".format(cadastro.caminho))

        self.var_ultima.set("{}: {} fonte(s) importadas de {}.".format(
            municipio, len(lidas), Path(caminho).name))
        if avisos:
            messagebox.showinfo(
                APP_NOME,
                "{} fonte(s) importadas para {}.\n\n{}".format(
                    len(lidas), municipio, "\n\n".join(avisos)))

        self._recasar()
        self._recarregar_municipios()
        self._pintar()

    def _esquecer(self) -> None:
        municipio = self._escolhido()
        cadastro = self.janela.cadastro
        quantas = len(cadastro.fontes_de(municipio))
        if not quantas:
            return
        if not messagebox.askyesno(
                APP_NOME,
                "Apagar as {} fonte(s) de {}, e também os códigos que você "
                "escolheu à mão para este município?\n\nIsto não pode ser "
                "desfeito — só reimportando o arquivo.".format(
                    quantas, municipio)):
            return
        cadastro.esquecer(municipio)
        cadastro.salvar()
        self.var_ultima.set("Catálogo de {} apagado.".format(municipio))
        self._recasar()
        self._recarregar_municipios()
        self._pintar()

    # ------------------------------------------------------------------ #
    # a lista
    # ------------------------------------------------------------------ #
    def _montar_lista(self) -> None:
        cartao = Cartao(
            self.corpo, titulo="Fontes cadastradas", glifo="planilha",
            legenda="Amostra do catálogo. Use a busca para conferir uma fonte "
                    "específica.")
        cartao.pack(fill="both", expand=True)
        self.cartao_lista = cartao

        caixa, _entrada = campo_texto(cartao.acoes, self.var_busca, largura=26)
        caixa.pack(side="right")

        quadro = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        quadro.pack(fill="both", expand=True)

        self.tabela = ttk.Treeview(quadro, columns=("codigo", "nome"),
                                   show="headings", height=6,
                                   selectmode="browse")
        self.tabela.column("codigo", width=90, minwidth=60, anchor="e",
                           stretch=False)
        self.tabela.column("nome", width=520, minwidth=200, anchor="w",
                           stretch=True)
        self.tabela.heading("codigo", text="FONTE_PAG_ID")
        self.tabela.heading("nome", text="NOME")
        self.tabela.grid(row=0, column=0, sticky="nsew")
        self.tabela.tag_configure("zebra", background="#f6f7f9")

        barra = ttk.Scrollbar(quadro, orient="vertical",
                              command=self.tabela.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.tabela.configure(yscrollcommand=barra.set)
        quadro.rowconfigure(0, weight=1)
        quadro.columnconfigure(0, weight=1)

        self.var_contagem = tk.StringVar(value="")
        tk.Label(cartao.conteudo, textvariable=self.var_contagem,
                 bg=COR_CARTAO, fg=COR_DICA, font=fonte(T_MINI),
                 anchor="w").pack(fill="x", pady=(8, 0))

    def _pintar_lista(self) -> None:
        for item in self.tabela.get_children():
            self.tabela.delete(item)

        from arrecadacao.fontes import normalizar
        municipio = self._escolhido()
        todas = self.janela.cadastro.fontes_de(municipio)
        busca = normalizar(self.var_busca.get())
        achadas = [f for f in todas
                   if not busca or busca in normalizar(f.nome)
                   or busca in normalizar(f.codigo)]

        for indice, fonte_ in enumerate(achadas[:MOSTRAR_ATE]):
            self.tabela.insert("", "end", values=(fonte_.codigo, fonte_.nome),
                               tags=("zebra",) if indice % 2 else ())

        if not todas:
            self.var_contagem.set(
                "Nenhuma fonte cadastrada para este município — importe o "
                "arquivo do SISPREVWEB.")
        elif len(achadas) > MOSTRAR_ATE:
            self.var_contagem.set(
                "Mostrando {} de {} fonte(s) encontradas, em {} cadastradas.".
                format(MOSTRAR_ATE, len(achadas), len(todas)))
        else:
            self.var_contagem.set(
                "{} fonte(s) encontradas, em {} cadastradas.".format(
                    len(achadas), len(todas)))

    # ------------------------------------------------------------------ #
    def _trocar(self) -> None:
        if self._silencio:
            return
        self.estado.municipio = self._escolhido()
        self._recasar()
        self._pintar()

    def _recasar(self) -> None:
        """Refaz o casamento da folha aberta e atualiza a barra lateral."""
        self.janela.casar_fontes()
        self.janela.atualizar_barra()

    def _pintar(self) -> None:
        municipio = self._escolhido()
        cadastro = self.janela.cadastro
        quantas = len(cadastro.fontes_de(municipio))
        escolhas = len(cadastro.escolhas.get(municipio, {}))

        if not municipio:
            self.var_situacao.set("Escolha o município.")
        elif not quantas:
            self.var_situacao.set(
                "Nenhuma fonte cadastrada. Importe o arquivo exportado do "
                "SISPREVWEB.")
        else:
            texto = "{} fonte(s) no catálogo".format(quantas)
            if escolhas:
                texto += "  ·  {} código(s) escolhidos à mão".format(escolhas)
            pendentes = self.janela.fontes_pendentes()
            if self.estado.tem_folha():
                texto += "  ·  folha aberta: {}".format(
                    "{} fonte(s) sem código".format(len(pendentes))
                    if pendentes else "todas as fontes com código")
            self.var_situacao.set(texto)

        self.btn_esquecer.configure(state="normal" if quantas else "disabled")
        self._pintar_lista()

    # ------------------------------------------------------------------ #
    def ao_entrar(self) -> None:
        self._recarregar_municipios()
        self._pintar()

        pendentes = self.janela.fontes_pendentes()
        if pendentes:
            self.janela.status(
                "{} fonte(s) da folha aberta ainda sem código.".format(
                    len(pendentes)))
        else:
            self.janela.status("Catálogo de fontes pagadoras.")
