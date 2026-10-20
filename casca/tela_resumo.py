# -*- coding: utf-8 -*-
"""Resumo para o cliente: o que foi arrecadado, por fonte pagadora.

Sai do export do Lancamento do SISPREVWEB, e nao da folha: e la que esta o
PATRONAL, que o arquivo de importacao leva zerado e o SISPREVWEB calcula. O
resumo e o documento que se manda -- ao cliente, ao conselho --, e por isso
sai nos tres formatos: .xlsx para quem vai mexer, .csv para quem vai importar
em outro lugar, .pdf para quem so vai ler.

O export e o mesmo da Validacao, guardado no estado: anexado numa tela, vale
na outra.
"""

from __future__ import annotations

import os
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox

from .base_tela import Tela
from .componentes import Botao, Cartao
from .identidade import APP_NOME
from .preferencias import pasta_gravavel
from .tema import COR_CARTAO, COR_MUDO, GAP, T_LEGENDA, fonte
from .tela_validacao import (_moeda, anexar_lancamentos,
                             descrever_lancamentos, tabela_com_rolagem)

COLUNAS = (
    ("fonte", "Fonte pagadora", 300, "w"),
    ("segurados", "Segurados", 80, "center"),
    ("remuneracao", "Remuneração de contribuição", 170, "e"),
    ("segurado", "Contribuição do segurado", 160, "e"),
    ("patronal", "Patronal", 120, "e"),
    ("custo", "Custo especial", 120, "e"),
    ("total", "Total", 130, "e"),
)


class TelaResumo(Tela):
    chave = "resumo"
    titulo = "Resumo"
    subtitulo = ("o que foi arrecadado, por fonte pagadora — para mandar ao "
                 "cliente")

    def montar(self) -> None:
        cartao = Cartao(self.corpo, titulo="Export do Lançamento do SISPREVWEB",
                        glifo="baixar",
                        legenda="O mesmo da Validação. O patronal vem dele: o "
                                "arquivo de importação leva zero.")
        cartao.pack(fill="x", pady=(0, GAP))
        self.var_lancamentos = tk.StringVar()
        linha = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        linha.pack(fill="x")
        tk.Label(linha, textvariable=self.var_lancamentos, bg=COR_CARTAO,
                 fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w",
                 justify="left").pack(side="left", fill="x", expand=True)
        Botao(linha, text="ANEXAR OUTRO EXPORT",
              command=self._anexar).pack(side="right")

        self.cartao_tabela = Cartao(
            self.corpo, titulo="Por fonte pagadora", glifo="grafico",
            legenda="Só as fontes com valor no mês. A última linha é o total.",
            padding=(14, 14))
        acoes = tk.Frame(self.cartao_tabela.conteudo, bg=COR_CARTAO)
        acoes.pack(side="bottom", fill="x", pady=(12, 0))
        Botao(acoes, text="EXPORTAR PDF", primario=True,
              command=lambda: self._exportar("pdf")).pack(side="right")
        Botao(acoes, text="EXPORTAR CSV",
              command=lambda: self._exportar("csv")).pack(side="right", padx=8)
        Botao(acoes, text="EXPORTAR XLSX",
              command=lambda: self._exportar("xlsx")).pack(side="right")
        moldura, self.tabela = tabela_com_rolagem(self.cartao_tabela.conteudo,
                                                  COLUNAS, 14)
        moldura.pack(fill="both", expand=True)
        self.tabela.tag_configure("total", font=fonte(T_LEGENDA, True))

    def _anexar(self) -> None:
        if anexar_lancamentos(self):
            self._pintar()

    def _pintar(self) -> None:
        self.var_lancamentos.set(
            descrever_lancamentos(self.estado) or
            "Nenhum export anexado. No SISPREVWEB: Arrecadação › Lançamento, "
            "filtre o mês e o órgão, Consultar e Exportar.")
        self.tabela.delete(*self.tabela.get_children())
        if self.estado.lancamentos_sisprev is None:
            self.cartao_tabela.pack_forget()
            self.repensar_rolagem()
            return
        from arrecadacao.relatorios import montar_resumo
        _caminho, lidos = self.estado.lancamentos_sisprev
        linhas, total = montar_resumo(lidos)
        for indice, linha in enumerate(list(linhas) + [total]):
            self.tabela.insert(
                "", "end", iid=str(indice),
                tags=("total",) if linha is total else (),
                values=(linha.fonte, linha.segurados, _moeda(linha.remuneracao),
                        _moeda(linha.segurado), _moeda(linha.orgao),
                        _moeda(linha.custo), _moeda(linha.total)))
        if not self.cartao_tabela.winfo_manager():
            self.cartao_tabela.pack(fill="both", expand=True)
        self.repensar_rolagem()

    def _exportar(self, extensao: str) -> None:
        if self.estado.lancamentos_sisprev is None:
            return
        from arrecadacao import relatorios
        _caminho, lidos = self.estado.lancamentos_sisprev
        municipio = self.estado.municipio
        pasta, _ = pasta_gravavel(self.janela.prefs.destino(None))
        destino = filedialog.asksaveasfilename(
            title="Exportar o resumo ({})".format(extensao.upper()),
            initialdir=str(pasta),
            initialfile=relatorios.nome_do_resumo(municipio, lidos, extensao),
            defaultextension="." + extensao,
            filetypes=[(extensao.upper(), "*." + extensao)])
        if not destino:
            return
        try:
            if extensao == "xlsx":
                relatorios.gravar_resumo_xlsx(lidos, Path(destino), municipio)
            elif extensao == "csv":
                relatorios.gravar_resumo_csv(lidos, Path(destino))
            else:
                relatorios.gravar_resumo_pdf(lidos, Path(destino), municipio)
        except PermissionError:
            messagebox.showerror(
                APP_NOME, "O arquivo está aberto em outro programa:\n\n{}\n\n"
                "Feche-o e exporte de novo.".format(destino))
            return
        except (OSError, RuntimeError) as erro:
            messagebox.showerror(APP_NOME,
                                 "Não foi possível gravar:\n\n{}".format(erro))
            return
        from arrecadacao.validacao import competencia_dos_lancamentos
        self.janela.indice.registrar(
            destino, extensao, "{} · {} · resumo por fonte pagadora".format(
                municipio or "sem município",
                competencia_dos_lancamentos(lidos)))
        self.janela.status("Exportado: {}".format(destino))
        if messagebox.askyesno(APP_NOME, "Arquivo gerado:\n\n{}\n\nAbrir "
                               "agora?".format(destino)):
            try:
                os.startfile(destino)      # type: ignore[attr-defined]
            except OSError:
                pass

    def ao_entrar(self) -> None:
        self._pintar()
        if self.estado.lancamentos_sisprev is None:
            self.janela.status("Anexe o export do Lançamento do SISPREVWEB.")
