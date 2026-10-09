# -*- coding: utf-8 -*-
r"""Grava as linhas do layout em .xlsx ou .csv.

Duas saidas com propositos diferentes, e por isso com padroes diferentes:

* **.xlsx** e para CONFERIR. Vai com titulos, com as colunas na largura certa e
  com os valores como numero de verdade (nao texto), para que somar a coluna no
  Excel bata com o total da folha.
* **.csv** e para IMPORTAR. Vai sem titulos e com ponto-e-virgula, que e o que
  o importador de layout posicional espera: uma linha de titulos vira um
  registro invalido logo na primeira linha do arquivo.

O decimal e virgula nos dois, porque e o que o Excel em portugues le sem
perguntar nada e o que o SISPREVWEB espera. Gravar "4810.11" num CSV aberto no
Excel brasileiro produz 481011 -- sem aviso.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .folha import Folha
from .layout import CAMPOS, MODELO_COMPLETO, ORDEM, Campo, Linha, campos_do_modelo

# O Excel em portugues abre CSV de ponto-e-virgula direto; com virgula ele joga
# a linha inteira na coluna A.
SEPARADOR_CSV = ";"

# BOM porque o Excel, sem ele, le UTF-8 como ANSI e mostra "JOSÃ‰" no lugar de
# "JOSÉ". O importador ignora o BOM.
CODIFICACAO_CSV = "utf-8-sig"


def _texto_numero(valor: float, decimais: int) -> str:
    """4810.11 -> "4810,11". Sem separador de milhar: ele quebra a importacao."""
    return "{:.{}f}".format(float(valor or 0), decimais).replace(".", ",")


def _celula(linha: Linha, campo: Campo, para_csv: bool):
    valor = getattr(linha, campo.chave)
    if not campo.numerico:
        return str(valor or "")
    if para_csv:
        return _texto_numero(valor, campo.decimais)
    # No xlsx o numero vai como numero: texto que parece numero nao soma, e a
    # conferencia da coluna contra o total da folha e justamente o que se quer
    # poder fazer.
    return round(float(valor or 0), campo.decimais) if campo.decimais else int(valor or 0)


# ---------------------------------------------------------------------- #
def gravar_csv(linhas: Sequence[Linha], destino: Path, modelo: str,
               com_titulos: bool = False) -> Path:
    """Escreve o arquivo de importacao."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    campos = campos_do_modelo(modelo)

    # newline="": sem isso o modulo csv escreve \r\r\n no Windows e o
    # importador ve uma linha em branco entre cada registro.
    with destino.open("w", newline="", encoding=CODIFICACAO_CSV) as arquivo:
        escritor = csv.writer(arquivo, delimiter=SEPARADOR_CSV,
                              quoting=csv.QUOTE_MINIMAL)
        if com_titulos:
            escritor.writerow([c.titulo for c in campos])
        for linha in linhas:
            escritor.writerow([_celula(linha, c, para_csv=True) for c in campos])
    return destino


def gravar_xlsx(linhas: Sequence[Linha], destino: Path, modelo: str,
                folha: Optional[Folha] = None, municipio: str = "") -> Path:
    """Escreve a planilha de conferencia, com uma aba de resumo."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    campos = campos_do_modelo(modelo)

    livro = Workbook()
    aba = livro.active
    aba.title = "Arrecadação"

    tinta = Font(bold=True, color="FFFFFF")
    fundo = PatternFill("solid", fgColor="344767")     # o navy da identidade
    for coluna, campo in enumerate(campos, start=1):
        celula = aba.cell(row=1, column=coluna, value=campo.titulo)
        celula.font = tinta
        celula.fill = fundo
        celula.alignment = Alignment(vertical="center", wrap_text=True)
        aba.column_dimensions[get_column_letter(coluna)].width = max(
            12, min(42, campo.largura / 6.5))
    aba.freeze_panes = "A2"

    for indice, linha in enumerate(linhas, start=2):
        for coluna, campo in enumerate(campos, start=1):
            celula = aba.cell(row=indice, column=coluna,
                              value=_celula(linha, campo, para_csv=False))
            if campo.decimais:
                celula.number_format = "#,##0.00"

    _aba_de_resumo(livro, linhas, modelo, folha, municipio)
    livro.save(destino)
    return destino


def _aba_de_resumo(livro, linhas: Sequence[Linha], modelo: str,
                   folha: Optional[Folha], municipio: str = "") -> None:
    """A segunda aba: de onde veio o arquivo e o que ficou pendente.

    Existe porque a planilha de arrecadacao circula entre pessoas e meses. Sem
    esta aba, daqui a tres meses ninguem sabe de qual PDF ela saiu, se as somas
    conferem com a folha, nem se alguma linha foi exportada com pendencia.
    """
    from openpyxl.styles import Font

    aba = livro.create_sheet("Resumo")
    negrito = Font(bold=True)
    campos = campos_do_modelo(modelo)

    def escrever(rotulo: str, valor) -> None:
        proxima = aba.max_row + 1 if aba.max_row > 1 or aba["A1"].value else 1
        aba.cell(row=proxima, column=1, value=rotulo).font = negrito
        aba.cell(row=proxima, column=2, value=valor)

    if folha is not None:
        escrever("Folha de origem", Path(folha.arquivo).name)
        escrever("Tipo de folha", folha.tipo)
        escrever("Entidade", folha.entidade)
    # O municipio ESCOLHIDO, que pode nao ser o que o cabecalho diz: e ele que
    # decidiu de qual catalogo saiu cada codigo de fonte pagadora, entao e ele
    # que responde "por que esta linha foi para a fonte 5085?".
    if municipio:
        escrever("Município (catálogo de fontes)", municipio)
    if folha is not None:
        competencia = folha.competencia_de_saida()
        escrever("Competência exportada", str(competencia) if competencia else "")
    escrever("Modelo do layout", modelo)
    escrever("Colunas", ", ".join(c.titulo for c in campos))
    escrever("Registros", len(linhas))
    # Os proventos e a diferenca nao sao colunas do arquivo: estao aqui porque
    # e nesta aba que a planilha e conferida contra o rodape da folha, e os
    # dois numeros nao batem nem devem bater -- ver `Segurado.total_proventos`.
    proventos = round(sum(l.proventos for l in linhas), 2)
    base = round(sum(l.base for l in linhas), 2)
    escrever("Total de proventos da folha", proventos)
    escrever("Verbas que não compõem a base", round(proventos - base, 2))
    escrever("Remuneração de contribuição", base)
    escrever("Contribuição do segurado", round(sum(l.segurado for l in linhas), 2))
    # Dito, e nao calculado: as duas colunas de patronal saem zeradas por
    # decisao de quem recolhe, e somar uma coluna de zeros nao responde nada.
    # Quem abrir esta planilha daqui a tres meses vai estranhar os zeros, e e
    # esta linha que explica.
    escrever("Patronal normal e custo especial",
             "0,00 — não são coletados da folha")

    # De onde saiu o codigo de cada fonte. Sem isto, conferir meses depois por
    # que uma contribuicao caiu numa fonte exige reabrir o PDF e o catalogo: a
    # planilha nao guarda sinal nenhum de que "5085" veio do nome ou de uma
    # escolha feita a mao numa tarde.
    origens: Dict[str, int] = {}
    for linha in linhas:
        if linha.fonte_origem:
            origens[linha.fonte_origem] = origens.get(linha.fonte_origem, 0) + 1
    for origem, quantas in sorted(origens.items(), key=lambda i: -i[1]):
        escrever("Fonte pagadora — {}".format(origem),
                 "{} linha(s)".format(quantas))

    pendentes = [l for l in linhas if l.tem_pendencia]
    escrever("Linhas com pendência", len(pendentes))
    if pendentes:
        aba.cell(row=aba.max_row + 2, column=1, value="Pendências").font = negrito
        cabecalho = aba.max_row + 1
        for coluna, titulo in enumerate(("Matrícula", "Nome", "Página", "Motivo"),
                                        start=1):
            aba.cell(row=cabecalho, column=coluna, value=titulo).font = negrito
        for deslocamento, linha in enumerate(pendentes, start=1):
            destino = cabecalho + deslocamento
            aba.cell(row=destino, column=1, value=linha.matricula)
            aba.cell(row=destino, column=2, value=linha.nome)
            aba.cell(row=destino, column=3, value=linha.pagina)
            aba.cell(row=destino, column=4, value="; ".join(linha.pendencias))

    aba.column_dimensions["A"].width = 32
    aba.column_dimensions["B"].width = 60


# ---------------------------------------------------------------------- #
def nome_sugerido(folha: Folha, modelo: str, extensao: str,
                  municipio: str = "") -> str:
    """"Arrecadacao_Aripuana_2026-08_Mensal.xlsx".

    Municipio, competencia e tipo -- nao a data de hoje. A data de geracao nao
    identifica nada: quem recebe o arquivo precisa saber de que MUNICIPIO e de
    que COMPETENCIA ele e, e gerar o mesmo mes duas vezes tem de produzir o
    mesmo nome, para substituir o anterior em vez de acumular copias.

    O municipio vem primeiro porque sao 29 e a mesma competencia sai para
    todos: numa pasta com o mes inteiro, ordenar por nome agrupa por cidade,
    que e como os arquivos sao procurados.
    """
    competencia = folha.competencia_de_saida()
    partes = ["Arrecadacao"]
    if municipio:
        partes.append(_em_palavras(municipio))
    if competencia is not None:
        partes.append("{:04d}-{:02d}".format(competencia.ano, competencia.mes))
    if folha.tipo:
        partes.append(_sem_pontuacao(folha.tipo))
    if modelo != MODELO_COMPLETO:
        partes.append("8campos")
    return "{}.{}".format("_".join(p for p in partes if p), extensao.lstrip("."))


def _sem_pontuacao(texto: str) -> str:
    """Nome de arquivo sem acento nem caractere que o Windows recuse."""
    import unicodedata
    plano = unicodedata.normalize("NFKD", str(texto or ""))
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else "" for c in plano)


def _em_palavras(texto: str) -> str:
    """"BARÃO DE MELGAÇO" -> "BaraoDeMelgaco".

    O municipio e o unico pedaco do nome com mais de uma palavra. Colado em
    caixa alta ele sai "BARAODEMELGACO", que ninguem le; o separador "_" ja
    separa os campos do nome e usa-lo aqui tambem confundiria os dois niveis.
    """
    palavras = str(texto or "").split()
    return "".join(_sem_pontuacao(p).capitalize() for p in palavras)
