# -*- coding: utf-8 -*-
"""O relatorio "Patronal RPPS" do Agili (Nova Olimpia, 10/2026).

Nao e a folha: e o resumo da previdencia que o mesmo sistema emite, um
servidor por linha, ja com a base e o desconto do RPPS calculados.

    Patronal RPPS - 10/2026
    1.1.03 - SMAD - SECR MUN DE ADMINISTRACAO
    3327 - GABINETE SEC. ADMINISTRACAO / EFETIVO        <- a fonte
    Calculo Funcionario Matricula CPF ...
    Mensal Evanir Candida Augusto 783 593.495.571-34 03/01/2006 R$ 6.883,09
        14,00 R$ 963,63 35,69 R$ 2.456,57 R$ 3.420,20

A coluna "Calculo" diz de que folha veio a linha -- "Mensal", "Rescisao",
"13o salario" --, e vira o `tipo_folha` do segurado: o 13o sai na competencia
13 como nos outros formatos. O desconto entra como uma verba so, "RPPS", que
`Verba.e_previdencia_do_segurado` ja reconhece pelo nome.

Depois do "Total: CLASSIFICACAO GERAL" vem a pagina RESUMO, com as mesmas
linhas "3327 - GABINETE ..." seguidas dos totais: nada dali e lido.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence

from ..folha import Competencia, Folha, Segurado, Verba, numero
from ..fontes import FonteDaFolha

NOME = "Agili (Patronal RPPS)"

RE_TITULO = re.compile(r"^Patronal\s+RPPS\s*-\s*(\d{1,2})/(\d{4})$",
                       re.IGNORECASE)
RE_ENTIDADE = re.compile(r"^((?:PREFEITURA|C.MARA)\b.+)$", re.IGNORECASE)
RE_UNIDADE = re.compile(r"^\d+\.\d+\.\d+\s*-\s*(.+)$")
RE_FONTE = re.compile(r"^(\d{3,})\s*-\s*(\D.*)$")
RE_FIM = re.compile(r"^Total:\s*CLASSIFICA", re.IGNORECASE)
_DINHEIRO = r"R\$\s*([\d.]+,\d\d)"
RE_SERVIDOR = re.compile(
    r"^(13\S*\s+sal\S*|\S+)\s+(.+?)\s+(\d+)\s+(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
    r"(\d{2}/\d{2}/\d{4})\s+" + _DINHEIRO + r"\s+[\d,]+\s+" + _DINHEIRO +
    r"\s+[\d,]+\s+" + _DINHEIRO + r"\s+" + _DINHEIRO + r"$", re.IGNORECASE)


def pontuar(linhas: Sequence[tuple]) -> int:
    if not any(RE_TITULO.match(l.texto.strip()) for l, _p in linhas[:40]):
        return 0
    return sum(1 for l, _p in linhas if RE_SERVIDOR.match(l.texto.strip()))


def ler(linhas: Sequence[tuple], folha: Folha) -> List[Segurado]:
    for linha, _pagina in linhas[:40]:
        texto = linha.texto.strip()
        achado = RE_TITULO.match(texto)
        if achado and folha.competencia is None:
            folha.competencia = Competencia(ano=int(achado.group(2)),
                                            mes=int(achado.group(1)))
        elif not folha.entidade and RE_ENTIDADE.match(texto):
            folha.entidade = texto

    segurados = _ler_segurados(linhas)
    tipos = {s.tipo_folha for s in segurados}
    # Um tipo so vira o tipo da folha; misturado, cada linha leva o seu.
    folha.tipo = tipos.pop() if len(tipos) == 1 else "Mensal"
    return segurados


def _ler_segurados(linhas: Sequence[tuple]) -> List[Segurado]:
    segurados: List[Segurado] = []
    unidade = ""
    fonte: Optional[FonteDaFolha] = None
    for linha, pagina in linhas:
        texto = linha.texto.strip()
        if RE_FIM.match(texto):
            break
        achado = RE_UNIDADE.match(texto)
        if achado:
            unidade = achado.group(1).strip()
            continue
        achado = RE_SERVIDOR.match(texto)
        if achado:
            (calculo, nome, matricula, cpf, admissao, base, valor,
             _patronal, _total) = achado.groups()
            segurado = Segurado(
                matricula=matricula, nome=nome.strip(), cpf=cpf,
                admissao=admissao, regime="RPPS", fonte=fonte,
                unidade=unidade, pagina=pagina, tipo_folha=calculo.strip())
            segurado.verbas.append(Verba(
                codigo="RPPS", descricao="RPPS - FUNCIONÁRIO", tipo="D",
                base=numero(base), valor=numero(valor)))
            segurados.append(segurado)
            continue
        achado = RE_FONTE.match(texto)
        if achado:
            fonte = FonteDaFolha(numero=int(achado.group(1)),
                                 nome=achado.group(2).strip(), bruto=texto)
    return segurados
