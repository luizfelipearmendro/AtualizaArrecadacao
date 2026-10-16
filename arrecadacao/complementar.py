# -*- coding: utf-8 -*-
"""O arquivo complementar que alguns municipios mandam junto com a folha.

Nova Olimpia manda, alem do PDF da Dura Lex, um CSV que ja esta no layout de
importacao do SISPREVWEB -- uma linha por servidor:

    14;FULANO DE TAL SANTOS;2026;8;"4880,74";"683,3";"1741,94";"111,28";8809;EFETIVO

matricula, nome, ano, mes, base, contribuicao do segurado, patronal normal,
patronal custo especial, fonte pagadora e categoria: os dez campos do modelo
simplificado, na mesma ordem.

Por que o PDF continua sendo lido, se o CSV ja tem tudo: porque o CSV e o que
a prefeitura DIZ que descontou, e o PDF e a folha que pagou. Os dois juntos se
conferem -- o CSV de 08/2026 tem 347 servidores e a folha 383, e os 36 que
faltam no CSV sao justamente o que alguem precisa ver antes de importar.

O que o CSV traz e o PDF da Dura Lex nao: a BASE de cada servidor. A folha so
imprime a contribuicao, e a base deduzida dela (contribuicao / aliquota) fica
ate 7 centavos longe da verdadeira. Com o CSV, a base e a do municipio --
ver `regras.aplicar`.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class LinhaComplementar:
    matricula: str
    nome: str
    ano: int
    mes: int
    base: float
    segurado: float
    patronal: float = 0.0
    especial: float = 0.0
    fonte: str = ""
    categoria: str = ""

    @property
    def chave(self) -> str:
        """A matricula sem os zeros da frente -- "000014" no PDF e "14" aqui."""
        return chave_de_matricula(self.matricula)


def chave_de_matricula(matricula: str) -> str:
    limpa = str(matricula or "").strip()
    return limpa.lstrip("0") or limpa


class ArquivoComplementarInvalido(ValueError):
    """O arquivo nao tem a forma do layout -- nao e o CSV que se esperava."""


def ler_csv_sisprevweb(caminho: str) -> List[LinhaComplementar]:
    """As linhas do CSV, na ordem do arquivo. Cabecalho, se houver, e pulado.

    Aceita ";" ou "," entre campos e virgula ou ponto nos decimais, porque o
    arquivo vem de sistemas diferentes e do Excel de quem o abriu antes.
    """
    texto = _ler_texto(Path(caminho))
    separador = ";" if texto.count(";") >= texto.count(",") else ","
    linhas: List[LinhaComplementar] = []
    recusadas = 0
    for campos in csv.reader(io.StringIO(texto), delimiter=separador):
        campos = [c.strip() for c in campos]
        if not any(campos):
            continue
        linha = _linha(campos)
        if linha is None:
            recusadas += 1
            continue
        linhas.append(linha)
    if not linhas:
        raise ArquivoComplementarInvalido(
            "{} não está no layout de importação do SISPREVWEB (matrícula; "
            "nome; ano; mês; base; contribuição; ...).".format(
                Path(caminho).name))
    return linhas


def _ler_texto(caminho: Path) -> str:
    bruto = caminho.read_bytes()
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return bruto.decode("latin-1", errors="replace")


def _linha(campos: List[str]) -> Optional[LinhaComplementar]:
    """Uma linha do layout, ou None quando ela nao e uma (o cabecalho)."""
    if len(campos) < 6:
        return None
    ano, mes = _inteiro(campos[2]), _inteiro(campos[3])
    base, segurado = _valor(campos[4]), _valor(campos[5])
    if ano is None or mes is None or base is None or segurado is None:
        return None
    resto = campos + [""] * (10 - len(campos))
    return LinhaComplementar(
        matricula=campos[0], nome=campos[1], ano=ano, mes=mes,
        base=base, segurado=segurado,
        patronal=_valor(resto[6]) or 0.0, especial=_valor(resto[7]) or 0.0,
        fonte=resto[8], categoria=resto[9])


def _inteiro(texto: str) -> Optional[int]:
    try:
        return int(str(texto).strip())
    except ValueError:
        return None


def _valor(texto: str) -> Optional[float]:
    """"4880,74", "4.880,74", "4880.74" e "0" -- todos sao valor."""
    limpo = str(texto or "").strip().replace(" ", "")
    if not limpo:
        return None
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return round(float(limpo), 2)
    except ValueError:
        return None
