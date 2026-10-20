# -*- coding: utf-8 -*-
"""Os arquivos da validacao e do resumo para o cliente.

A validacao e para CONFERIR, e por isso so sai em .xlsx: tres abas, com os
numeros como numero. O resumo e para MANDAR -- ao cliente, ao conselho --, e
sai no formato que a pessoa pedir: .xlsx para quem vai mexer, .csv para quem
vai importar em outro lugar, .pdf para quem so vai ler.

O PDF e montado com o PyMuPDF, que o programa ja usa para ler a folha:
nenhuma biblioteca nova a empacotar so para escrever uma tabela.
"""

from __future__ import annotations

import csv
import html
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from .exportacao import fonte_tamanho_10
from .validacao import (CONFERE, DIFERENTE, NAO_ENTROU, SO_SISPREV,
                        Lancamento, LinhaResumo, Validacao,
                        competencia_dos_lancamentos, resumir_por_fonte,
                        total_do_resumo)

_NAVY = "344767"
_FUNDO_DA_SITUACAO = {CONFERE: "E3F1E6", DIFERENTE: "FCEFD2",
                      NAO_ENTROU: "F8DADA", SO_SISPREV: "E4ECF7"}


def _moeda(valor: float) -> str:
    """4810.11 -> "4.810,11"."""
    return "{:,.2f}".format(float(valor or 0)).replace(",", "X") \
        .replace(".", ",").replace("X", ".")


def _cabecalho(aba, colunas):
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    for numero, (titulo, largura) in enumerate(colunas, start=1):
        celula = aba.cell(row=1, column=numero, value=titulo)
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor=_NAVY)
        aba.column_dimensions[get_column_letter(numero)].width = largura
    aba.freeze_panes = "A2"
    aba.auto_filter.ref = "A1:{}1".format(get_column_letter(len(colunas)))


def _dinheiro(aba, linha: int, colunas: Sequence[int]) -> None:
    for coluna in colunas:
        aba.cell(row=linha, column=coluna).number_format = "#,##0.00"


# ---------------------------------------------------------------------- #
# validacao
# ---------------------------------------------------------------------- #
def gravar_validacao_xlsx(validacao: Validacao, destino: Path,
                          municipio: str = "", origem: str = "") -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    livro = Workbook()

    # 1. o resumo vem primeiro: e a pergunta ("bateu?") e a resposta.
    resumo = livro.active
    resumo.title = "Resumo"
    negrito = Font(bold=True)
    totais = validacao.totais()
    linhas = [("Município", municipio), ("Competência", validacao.competencia),
              ("Comparado com", origem),
              ("Export do SISPREVWEB", Path(validacao.arquivo).name), None,
              ("", "Folha / arquivo", "SISPREVWEB", "Diferença"),
              ("Remuneração de contribuição", totais["base_folha"],
               totais["base_sisprev"],
               round(totais["base_sisprev"] - totais["base_folha"], 2)),
              ("Contribuição do segurado", totais["segurado_folha"],
               totais["segurado_sisprev"],
               round(totais["segurado_sisprev"] - totais["segurado_folha"], 2)),
              None]
    for situacao, quantos in validacao.contagem().items():
        linhas.append((situacao, quantos))
    for numero, valores in enumerate(linhas, start=1):
        if valores is None:
            continue
        for coluna, valor in enumerate(valores, start=1):
            celula = resumo.cell(row=numero, column=coluna, value=valor)
            if coluna == 1 or valores[0] == "":
                celula.font = negrito
            if isinstance(valor, float):
                celula.number_format = "#,##0.00"
    resumo.column_dimensions["A"].width = 30
    for letra in "BCD":
        resumo.column_dimensions[letra].width = 20

    # 2. por fonte pagadora: onde a diferenca mora
    aba = livro.create_sheet("Por fonte pagadora")
    _cabecalho(aba, (("Fonte no arquivo", 12), ("Fonte na folha", 40),
                     ("Linhas", 8), ("Não entraram", 12),
                     ("Base folha", 15), ("Base SISPREVWEB", 15),
                     ("Diferença base", 15), ("Segurado folha", 15),
                     ("Segurado SISPREVWEB", 15), ("Diferença segurado", 15),
                     ("Onde entrou no SISPREVWEB", 60)))
    for numero, grupo in enumerate(validacao.fontes, start=2):
        valores = (grupo.fonte_enviada, grupo.fonte_folha, grupo.linhas,
                   grupo.nao_entraram, grupo.base_folha, grupo.base_sisprev,
                   grupo.dif_base, grupo.segurado_folha, grupo.segurado_sisprev,
                   grupo.dif_segurado, "; ".join(grupo.fontes_sisprev))
        for coluna, valor in enumerate(valores, start=1):
            aba.cell(row=numero, column=coluna, value=valor)
        _dinheiro(aba, numero, range(5, 11))
        if abs(grupo.dif_base) > 0.01 or abs(grupo.dif_segurado) > 0.01:
            aba.cell(row=numero, column=7).fill = PatternFill(
                "solid", fgColor="F8DADA")

    # 3. por segurado
    aba = livro.create_sheet("Por segurado")
    _cabecalho(aba, (("Situação", 24), ("Código no arquivo", 12),
                     ("Código no SISPREVWEB", 12), ("Nome", 40),
                     ("Fonte no arquivo", 10), ("Base folha", 14),
                     ("Base SISPREVWEB", 14), ("Diferença base", 14),
                     ("Segurado folha", 14), ("Segurado SISPREVWEB", 14),
                     ("Diferença segurado", 14), ("Patronal SISPREVWEB", 14),
                     ("Fontes no SISPREVWEB", 50), ("Observação", 60)))
    ordem = {s: i for i, s in enumerate(
        (NAO_ENTROU, DIFERENTE, SO_SISPREV, CONFERE))}
    itens = sorted(validacao.itens,
                   key=lambda i: (ordem.get(i.situacao, 9), i.nome))
    for numero, item in enumerate(itens, start=2):
        valores = (item.situacao, item.codigo, item.codigo_sisprev, item.nome,
                   item.fonte_enviada, item.base_folha, item.base_sisprev,
                   item.dif_base, item.segurado_folha, item.segurado_sisprev,
                   item.dif_segurado, item.orgao_sisprev, item.fontes_sisprev,
                   item.observacao)
        for coluna, valor in enumerate(valores, start=1):
            aba.cell(row=numero, column=coluna, value=valor)
        _dinheiro(aba, numero, range(6, 13))
        cor = _FUNDO_DA_SITUACAO.get(item.situacao)
        if cor:
            aba.cell(row=numero, column=1).fill = PatternFill(
                "solid", fgColor=cor)

    fonte_tamanho_10(livro)
    livro.save(destino)
    return destino


# ---------------------------------------------------------------------- #
# resumo para o cliente
# ---------------------------------------------------------------------- #
TITULOS_RESUMO = ("Fonte pagadora", "Segurados", "Remuneração de contribuição",
                  "Contribuição do segurado", "Patronal",
                  "Patronal custo especial", "Total")


def _valores(linha: LinhaResumo):
    return (linha.fonte, linha.segurados, linha.remuneracao, linha.segurado,
            linha.orgao, linha.custo, linha.total)


def montar_resumo(lancamentos: Sequence[Lancamento]):
    linhas = resumir_por_fonte(lancamentos)
    return linhas, total_do_resumo(linhas, lancamentos)


def gravar_resumo_xlsx(lancamentos: Sequence[Lancamento], destino: Path,
                       municipio: str = "") -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    linhas, total = montar_resumo(lancamentos)
    livro = Workbook()
    aba = livro.active
    aba.title = "Resumo"
    aba.cell(row=1, column=1, value="Resumo da arrecadação").font = Font(
        bold=True, size=14)
    aba.cell(row=2, column=1, value="{}  ·  competência {}".format(
        municipio or "", competencia_dos_lancamentos(lancamentos)))
    inicio = 4
    from openpyxl.styles import PatternFill
    from openpyxl.utils import get_column_letter
    for coluna, titulo in enumerate(TITULOS_RESUMO, start=1):
        celula = aba.cell(row=inicio, column=coluna, value=titulo)
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor=_NAVY)
        aba.column_dimensions[get_column_letter(coluna)].width = \
            50 if coluna == 1 else 18
    for deslocamento, linha in enumerate(list(linhas) + [total], start=1):
        numero = inicio + deslocamento
        for coluna, valor in enumerate(_valores(linha), start=1):
            celula = aba.cell(row=numero, column=coluna, value=valor)
            if linha is total:
                celula.font = Font(bold=True)
        _dinheiro(aba, numero, range(3, 8))
    aba.freeze_panes = aba.cell(row=inicio + 1, column=1)
    fonte_tamanho_10(livro)
    livro.save(destino)
    return destino


def gravar_resumo_csv(lancamentos: Sequence[Lancamento], destino: Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    linhas, total = montar_resumo(lancamentos)
    with destino.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(TITULOS_RESUMO)
        for linha in list(linhas) + [total]:
            valores = _valores(linha)
            escritor.writerow([valores[0], valores[1]] + [
                "{:.2f}".format(v).replace(".", ",") for v in valores[2:]])
    return destino


def gravar_resumo_pdf(lancamentos: Sequence[Lancamento], destino: Path,
                      municipio: str = "", logo: Optional[Path] = None) -> Path:
    """Uma pagina A4 deitada, com a tabela por fonte e o total."""
    import fitz

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    linhas, total = montar_resumo(lancamentos)

    def celulas(linha, tag="td"):
        valores = _valores(linha)
        partes = ['<{0} class="nome">{1}</{0}>'.format(
            tag, html.escape(str(valores[0])))]
        partes.append('<{0} class="num">{1}</{0}>'.format(tag, valores[1]))
        partes += ['<{0} class="num">{1}</{0}>'.format(tag, _moeda(v))
                   for v in valores[2:]]
        return "".join(partes)

    corpo = "".join("<tr>{}</tr>".format(celulas(l)) for l in linhas)
    cabecalho = "".join("<th>{}</th>".format(html.escape(t))
                        for t in TITULOS_RESUMO)
    documento = """
    <h1>Resumo da arrecadação</h1>
    <p class="sub">{municipio}{sep}competência {competencia}</p>
    <table>
      <tr class="cab">{cabecalho}</tr>
      {corpo}
      <tr class="total">{total}</tr>
    </table>
    <p class="pe">Valores registrados no SISPREVWEB. Gerado em {quando}.</p>
    """.format(municipio=html.escape(municipio or ""),
               sep="  ·  " if municipio else "",
               competencia=competencia_dos_lancamentos(lancamentos),
               cabecalho=cabecalho, corpo=corpo,
               total=celulas(total, "td"),
               quando=datetime.now().strftime("%d/%m/%Y %H:%M"))
    estilo = """
    * { font-family: sans-serif; }
    h1 { font-size: 16px; color: #344767; margin: 0 0 2px 0; }
    p.sub { font-size: 10px; color: #6b7a90; margin: 0 0 10px 0; }
    table { border-collapse: collapse; width: 100%; }
    th { background-color: #344767; color: #ffffff; font-size: 8px;
         padding: 4px; text-align: right; }
    th:first-child { text-align: left; }
    td { font-size: 8px; padding: 3px 4px; border-bottom: 1px solid #e9e9e9; }
    td.num { text-align: right; }
    tr.total td { font-weight: bold; border-top: 1px solid #344767; }
    p.pe { font-size: 7px; color: #8a92a3; margin-top: 10px; }
    """
    pagina_retangulo = fitz.paper_rect("a4-l")
    area = pagina_retangulo + (36, 36, -36, -36)
    historia = fitz.Story(html=documento, user_css=estilo)
    escritor = fitz.DocumentWriter(str(destino))
    mais = True
    while mais:
        dispositivo = escritor.begin_page(pagina_retangulo)
        mais, _ = historia.place(area)
        historia.draw(dispositivo)
        escritor.end_page()
    escritor.close()
    return destino


def nome_do_resumo(municipio: str, lancamentos: Sequence[Lancamento],
                   extensao: str) -> str:
    from .exportacao import _em_palavras
    competencia = competencia_dos_lancamentos(lancamentos)
    mes, _, ano = competencia.partition("/")
    partes = ["Resumo"]
    if municipio:
        partes.append(_em_palavras(municipio))
    if ano and mes:
        partes.append("{}-{}".format(ano, mes))
    return "{}.{}".format("_".join(partes), extensao)


def nome_da_validacao(municipio: str, validacao: Validacao) -> str:
    from .exportacao import _em_palavras
    mes, _, ano = validacao.competencia.partition("/")
    partes = ["Validacao"]
    if municipio:
        partes.append(_em_palavras(municipio))
    if ano and mes:
        partes.append("{}-{}".format(ano, mes))
    return "{}.xlsx".format("_".join(partes))
