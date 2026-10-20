# -*- coding: utf-8 -*-
"""Validacao: depois de importar, o que entrou no SISPREVWEB bate com a folha?

O usuario exporta o Lancamento do SISPREVWEB depois da importacao e anexa
aqui. A tela cruza com o que foi no arquivo e responde em tres niveis: o total
(bateu ou nao), as fontes pagadoras (ONDE nao bateu -- em Colniza 09/2026, as
quatro fontes que o importador recusou inteiras) e cada segurado, na planilha.

Contra o que se compara: a folha lida nesta sessao, com as matriculas que
foram para o arquivo (as do SISPREVWEB, se a comparacao foi feita). Sem folha
lida -- o programa foi fechado depois de exportar --, o proprio arquivo
importado serve, e e ate mais exato: e o que o importador recebeu.

O export anexado fica no estado do aplicativo e vale tambem para a tela do
Resumo: e o mesmo arquivo, e pedir duas vezes seria pedir para anexar o errado
numa delas.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .base_tela import Tela
from .componentes import Botao, Cartao, CaixaCampo, Metrica
from .identidade import APP_NOME
from .preferencias import pasta_gravavel
from .tema import (COR_ATENCAO, COR_CARTAO, COR_ERRO, COR_MUDO, COR_OK,
                   COR_PRIMARIA, GAP, T_LEGENDA, fonte)

COLUNAS_FONTES = (
    ("fonte", "Fonte no arquivo", 95, "center"),
    ("nome", "Fonte na folha", 230, "w"),
    ("linhas", "Linhas", 60, "center"),
    ("nao", "Não entraram", 90, "center"),
    ("folha", "Base folha", 120, "e"),
    ("sisprev", "Base SISPREVWEB", 120, "e"),
    ("dif", "Diferença", 110, "e"),
    ("onde", "Onde entrou no SISPREVWEB", 300, "w"),
)


def _moeda(valor: float) -> str:
    return "{:,.2f}".format(float(valor or 0)).replace(",", "X") \
        .replace(".", ",").replace("X", ".")


def anexar_lancamentos(tela: Tela) -> bool:
    """Pede o export do Lancamento e guarda no estado. True se anexou."""
    from arrecadacao.validacao import LancamentoInvalido, ler_lancamentos
    caminho = filedialog.askopenfilename(
        title="Export do Lançamento do SISPREVWEB (CSV)",
        filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")])
    if not caminho:
        return False
    try:
        lidos = ler_lancamentos(caminho)
    except (OSError, LancamentoInvalido) as erro:
        messagebox.showerror(APP_NOME, str(erro))
        return False
    tela.estado.lancamentos_sisprev = (caminho, lidos)
    tela.janela.atualizar_barra()
    return True


def descrever_lancamentos(estado) -> str:
    from arrecadacao.validacao import competencia_dos_lancamentos
    if estado.lancamentos_sisprev is None:
        return ""
    caminho, lidos = estado.lancamentos_sisprev
    codigos = {l.codigo for l in lidos if l.tem_valor}
    return "{}  ·  competência {}  ·  {} segurado(s) com valor".format(
        Path(caminho).name, competencia_dos_lancamentos(lidos) or "?",
        len(codigos))


def tabela_com_rolagem(dono: tk.Misc, colunas, altura: int = 10):
    moldura = CaixaCampo(dono, padding=(1, 1))
    quadro = tk.Frame(moldura.corpo, bg=COR_CARTAO)
    quadro.pack(fill="both", expand=True)
    tabela = ttk.Treeview(quadro, columns=[c[0] for c in colunas],
                          show="headings", selectmode="browse", height=altura)
    for chave, titulo, largura, ancora in colunas:
        tabela.heading(chave, text=titulo)
        tabela.column(chave, width=largura, minwidth=50, anchor=ancora,
                      stretch=(ancora == "w"))
    tabela.grid(row=0, column=0, sticky="nsew")
    barra = ttk.Scrollbar(quadro, orient="vertical", command=tabela.yview)
    barra.grid(row=0, column=1, sticky="ns")
    tabela.configure(yscrollcommand=barra.set)
    quadro.rowconfigure(0, weight=1)
    quadro.columnconfigure(0, weight=1)
    return moldura, tabela


class TelaValidacao(Tela):
    chave = "validacao"
    titulo = "Validação"
    subtitulo = ("depois de importar: o que entrou no SISPREVWEB bate com a "
                 "folha?")

    def montar(self) -> None:
        # Um arquivo importado escolhido a mao, quando nao ha folha na
        # sessao -- ou quando se quer validar outro mes.
        self.caminho_importado: str = ""
        self.validacao: Any = None
        self._montar_entradas()
        self._montar_resultado()

    # ------------------------------------------------------------------ #
    def _montar_entradas(self) -> None:
        linha = tk.Frame(self.corpo, bg=self.corpo["bg"])
        linha.pack(fill="x", pady=(0, GAP))
        linha.columnconfigure(0, weight=1, uniform="entrada")
        linha.columnconfigure(1, weight=1, uniform="entrada")

        cartao = Cartao(linha, titulo="1. O que foi importado", glifo="diario",
                        legenda="A folha desta sessão, ou o arquivo gerado.")
        cartao.grid(row=0, column=0, sticky="nsew", padx=(0, GAP // 2))
        self.var_referencia = tk.StringVar()
        self.rotulo_referencia = tk.Label(
            cartao.conteudo, textvariable=self.var_referencia, bg=COR_CARTAO,
            fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w", justify="left",
            wraplength=420)
        self.rotulo_referencia.pack(fill="x", pady=(0, 10))
        botoes = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        botoes.pack(fill="x")
        Botao(botoes, text="USAR O ARQUIVO IMPORTADO (.CSV)",
              command=self._escolher_importado).pack(side="left")
        self.btn_sessao = Botao(botoes, text="USAR A FOLHA DA SESSÃO",
                                sutil=True, command=self._usar_sessao)
        self.btn_sessao.pack(side="left", padx=8)

        cartao = Cartao(linha, titulo="2. O que entrou no SISPREVWEB",
                        glifo="baixar",
                        legenda="Arrecadação › Lançamento › Exportar, depois "
                                "da importação.")
        cartao.grid(row=0, column=1, sticky="nsew", padx=(GAP // 2, 0))
        self.var_lancamentos = tk.StringVar()
        self.rotulo_lancamentos = tk.Label(
            cartao.conteudo, textvariable=self.var_lancamentos, bg=COR_CARTAO,
            fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w", justify="left",
            wraplength=420)
        self.rotulo_lancamentos.pack(fill="x", pady=(0, 10))
        Botao(cartao.conteudo, text="ANEXAR O EXPORT DO LANÇAMENTO",
              primario=True, command=self._anexar).pack(anchor="w")

    def _montar_resultado(self) -> None:
        self.painel = tk.Frame(self.corpo, bg=self.corpo["bg"])

        numeros = tk.Frame(self.painel, bg=self.corpo["bg"])
        numeros.pack(fill="x", pady=(0, GAP))
        self.metricas = {}
        for indice, (chave, rotulo) in enumerate((
                ("base", "diferença na remuneração de contribuição"),
                ("segurado", "diferença na contribuição do segurado"),
                ("nao", "segurado(s) que não entraram"))):
            numeros.columnconfigure(indice, weight=1, uniform="metrica")
            metrica = Metrica(numeros, "0", rotulo)
            metrica.grid(row=0, column=indice, sticky="nsew",
                         padx=(0, 0 if indice == 2 else GAP))
            self.metricas[chave] = metrica
        self.var_conta = tk.StringVar()
        tk.Label(self.painel, textvariable=self.var_conta,
                 bg=self.corpo["bg"], fg=COR_MUDO, font=fonte(T_LEGENDA),
                 anchor="w", justify="left").pack(fill="x", pady=(0, GAP))

        cartao = Cartao(self.painel, titulo="Por fonte pagadora",
                        glifo="planilha",
                        legenda="As fontes com diferença vêm primeiro. "
                                "Fonte que não entrou inteira costuma ser "
                                "código de fonte errado no arquivo.",
                        padding=(14, 14))
        cartao.pack(fill="both", expand=True)
        acoes = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        acoes.pack(side="bottom", fill="x", pady=(12, 0))
        Botao(acoes, text="EXPORTAR A VALIDAÇÃO (XLSX)", primario=True,
              command=self._exportar).pack(side="right")
        Botao(acoes, text="IR PARA O RESUMO", sutil=True,
              command=lambda: self.janela.ir_para("resumo")).pack(side="left")
        moldura, self.tabela = tabela_com_rolagem(cartao.conteudo,
                                                  COLUNAS_FONTES, 12)
        moldura.pack(fill="both", expand=True)
        self.tabela.tag_configure("diferente", foreground=COR_ERRO)
        self.tabela.tag_configure("confere", foreground=COR_OK)

    # ------------------------------------------------------------------ #
    def _linhas_da_sessao(self) -> Optional[List]:
        """O arquivo final desta sessao: os ajustes da tabela, so as marcadas."""
        if not self.estado.linhas:
            return None
        return self.janela.telas["folha"].linhas_finais()

    def _referencia(self):
        """(linhas, descricao) contra o que se valida, ou (None, motivo)."""
        if self.caminho_importado:
            from arrecadacao.complementar import ArquivoComplementarInvalido
            from arrecadacao.validacao import linhas_do_arquivo_importado
            try:
                linhas = linhas_do_arquivo_importado(self.caminho_importado)
            except (OSError, ArquivoComplementarInvalido) as erro:
                return None, str(erro)
            return linhas, "o arquivo importado {} ({} linhas)".format(
                Path(self.caminho_importado).name, len(linhas))
        linhas = self._linhas_da_sessao()
        if linhas is None:
            return None, ("Nenhuma folha lida nesta sessão. Escolha o "
                          "arquivo que foi importado (o _MatriculasSisprev.csv "
                          "ou o .csv normal).")
        folha = self.janela.telas.get("folha")
        com_sisprev = getattr(folha, "comparacao_sisprev", None) is not None
        return linhas, "a folha desta sessão: {} · {} linhas{}".format(
            self.estado.municipio or "sem município", len(linhas),
            " · com as matrículas do SISPREVWEB" if com_sisprev
            else " · com a matrícula da folha")

    def _escolher_importado(self) -> None:
        caminho = filedialog.askopenfilename(
            title="Arquivo que foi importado no SISPREVWEB (CSV do layout)",
            filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")])
        if caminho:
            self.caminho_importado = caminho
            self._validar()

    def _usar_sessao(self) -> None:
        self.caminho_importado = ""
        self._validar()

    def _anexar(self) -> None:
        if anexar_lancamentos(self):
            self._validar()

    # ------------------------------------------------------------------ #
    def _validar(self) -> None:
        linhas, descricao = self._referencia()
        self.var_referencia.set(descricao)
        self.rotulo_referencia.configure(
            fg=COR_MUDO if linhas is not None else COR_ATENCAO)
        tem_sessao = self._linhas_da_sessao() is not None
        self.btn_sessao.configure(
            state="normal" if tem_sessao and self.caminho_importado
            else "disabled")

        lancamentos = self.estado.lancamentos_sisprev
        self.var_lancamentos.set(
            descrever_lancamentos(self.estado) or
            "Nenhum export anexado. No SISPREVWEB: Arrecadação › Lançamento, "
            "filtre o mês e o órgão, Consultar e Exportar.")
        if linhas is None or lancamentos is None:
            self.validacao = None
            self.painel.pack_forget()
            self.repensar_rolagem()
            return

        from arrecadacao.validacao import NAO_ENTROU, validar
        caminho, lidos = lancamentos
        self.validacao = validar(linhas, lidos, caminho)
        self._descricao_referencia = descricao
        totais = self.validacao.totais()
        dif_base = round(totais["base_sisprev"] - totais["base_folha"], 2)
        dif_seg = round(totais["segurado_sisprev"] - totais["segurado_folha"], 2)
        quantos = self.validacao.contagem()
        cor = COR_OK if abs(dif_base) <= 0.01 else COR_ERRO
        self.metricas["base"].definir(_moeda(dif_base), cor_acento=cor)
        self.metricas["segurado"].definir(
            _moeda(dif_seg),
            cor_acento=COR_OK if abs(dif_seg) <= 0.01 else COR_ERRO)
        self.metricas["nao"].definir(
            str(quantos[NAO_ENTROU]),
            cor_acento=COR_OK if not quantos[NAO_ENTROU] else COR_ATENCAO)
        self.var_conta.set(
            "Folha {} − SISPREVWEB {} de remuneração  ·  {} · {}".format(
                _moeda(totais["base_folha"]), _moeda(totais["base_sisprev"]),
                self.validacao.competencia or "competência ?",
                "  ·  ".join("{} {}".format(v, k.lower())
                             for k, v in quantos.items() if v)))

        self.tabela.delete(*self.tabela.get_children())
        for indice, grupo in enumerate(self.validacao.fontes):
            diferente = abs(grupo.dif_base) > 0.01 or \
                abs(grupo.dif_segurado) > 0.01
            self.tabela.insert(
                "", "end", iid=str(indice),
                tags=("diferente" if diferente else "confere",),
                values=(grupo.fonte_enviada or "—", grupo.fonte_folha or "—",
                        grupo.linhas, grupo.nao_entraram or "",
                        _moeda(grupo.base_folha), _moeda(grupo.base_sisprev),
                        _moeda(grupo.dif_base),
                        "; ".join(grupo.fontes_sisprev) or "nada entrou"))
        if not self.painel.winfo_manager():
            self.painel.pack(fill="both", expand=True)
        self.repensar_rolagem()
        self.janela.status(
            "Validação: diferença de {} na remuneração e {} na contribuição."
            .format(_moeda(dif_base), _moeda(dif_seg)))

    def _exportar(self) -> None:
        if self.validacao is None:
            return
        from arrecadacao.relatorios import (gravar_validacao_xlsx,
                                            nome_da_validacao)
        pasta, _ = pasta_gravavel(self.janela.prefs.destino(None))
        destino = filedialog.asksaveasfilename(
            title="Exportar a validação", initialdir=str(pasta),
            initialfile=nome_da_validacao(self.estado.municipio,
                                          self.validacao),
            defaultextension=".xlsx", filetypes=[("XLSX", "*.xlsx")])
        if not destino:
            return
        try:
            gravar_validacao_xlsx(self.validacao, Path(destino),
                                  self.estado.municipio,
                                  self._descricao_referencia)
        except PermissionError:
            messagebox.showerror(
                APP_NOME, "O arquivo está aberto em outro programa:\n\n{}\n\n"
                "Feche-o e exporte de novo.".format(destino))
            return
        except OSError as erro:
            messagebox.showerror(APP_NOME,
                                 "Não foi possível gravar:\n\n{}".format(erro))
            return
        self.janela.indice.registrar(
            destino, "xlsx", "{} · {} · validação contra o SISPREVWEB".format(
                self.estado.municipio or "sem município",
                self.validacao.competencia))
        self.janela.status("Exportado: {}".format(destino))
        if messagebox.askyesno(APP_NOME, "Arquivo gerado:\n\n{}\n\nAbrir "
                               "agora?".format(destino)):
            try:
                os.startfile(destino)      # type: ignore[attr-defined]
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    def ao_entrar(self) -> None:
        self._validar()
        if self.validacao is None:
            self.janela.status("Anexe o export do Lançamento do SISPREVWEB "
                               "para comparar com a folha.")
