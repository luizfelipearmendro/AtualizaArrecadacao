# -*- coding: utf-8 -*-
"""O que cada linha precisa antes de ir para o arquivo, e o que foi ajustado.

A tela da folha mostra UMA tabela, e cada linha diz na coluna "Ajuste" o que
falta nela: fonte sem codigo, fonte sugerida, matricula nao achada no
SISPREVWEB, fonte diferente do cadastro, contribuicao zerada. O ajuste e feito
na propria linha -- e antes eram tres cartoes separados, e o que sobrava so
aparecia no fim, abrindo o arquivo de importacao para corrigir a mao.

Os ajustes de uma linha ficam num dicionario da sessao, pela `chave`:

    {"importar": bool, "fonte": "2372", "matricula": "17231"}

A fonte escolhida para um GRUPO sem codigo nao mora aqui: vai para o cadastro
de fontes, gravada para os meses seguintes (`fontes.Cadastro.escolher`). Aqui
fica so o que e daquela linha.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .layout import Linha
from .segurados_sisprev import NAO_ENCONTRADO, chave_da_linha

# Do mais grave para o mais leve: a cor da linha e a do primeiro.
FONTE = "fonte"                        # sem codigo: nao entra na importacao
ERRO = "erro"                          # outra pendencia que trava a linha
FONTE_SUGERIDA = "fonte_sugerida"
FONTE_REPETIDA = "fonte_repetida"
MATRICULA_SUGERIDA = "matricula_sugerida"
MATRICULA = "matricula"
DIVERGE = "diverge"
ZERADA = "zerada"
TIPOS = (FONTE, ERRO, FONTE_SUGERIDA, FONTE_REPETIDA, MATRICULA_SUGERIDA,
         MATRICULA, DIVERGE, ZERADA)

AJUSTADA_NA_TABELA = "ajustada na tabela"

# As pendencias de `layout._pendencias` que esta coluna diz de outro jeito.
_PENDENCIAS_DE_FONTE = ("sem fonte pagadora na folha", "fonte pagadora sem código")
_PENDENCIAS_DE_VALOR = ("sem contribuição no mês", "sem base de cálculo")


def chave(linha: Linha) -> str:
    """A linha na sessao: matricula + nome + mes (o 13o e outra linha)."""
    return "{}|{}".format(chave_da_linha(linha), linha.mes)


def importa(linha: Linha, ajuste: Optional[dict]) -> bool:
    """Marcada para o arquivo? Por padrao, quem contribuiu no mes."""
    if ajuste and "importar" in ajuste:
        return bool(ajuste["importar"])
    return linha.segurado > 0


def aplicar_fontes(linhas: Sequence[Linha], ajustes: Dict[str, dict]) -> None:
    """Poe nas linhas a fonte escolhida para cada uma. Muda no lugar."""
    for linha in linhas:
        codigo = (ajustes.get(chave(linha)) or {}).get("fonte")
        if not codigo:
            continue
        linha.fonte = codigo
        linha.fonte_origem = AJUSTADA_NA_TABELA
        linha.pendencias = [p for p in linha.pendencias
                            if p not in _PENDENCIAS_DE_FONTE]


def diagnosticar(linha: Linha, correspondencia=None, comparacao=None,
                 ajuste: Optional[dict] = None,
                 codigos_repetidos: Set[str] = frozenset()
                 ) -> List[Tuple[str, str]]:
    """[(tipo, texto)] do que a linha precisa, do mais grave para o mais leve.

    `correspondencia` e a da fonte da folha (`fontes.Correspondencia`);
    `comparacao`, a do cadastro do SISPREVWEB, quando ele foi anexado.
    """
    ajuste = ajuste or {}
    achados: List[Tuple[str, str]] = []
    if not linha.fonte:
        sugerido = getattr(correspondencia, "sugerido", None)
        if sugerido is not None:
            achados.append((FONTE_SUGERIDA, "fonte: confirme {} — {}".format(
                sugerido.codigo, sugerido.nome)))
        else:
            achados.append((FONTE, "fonte sem código"))
    elif linha.fonte in codigos_repetidos and "fonte" not in ajuste:
        achados.append((FONTE_REPETIDA,
                        "código {} também em outra fonte da folha".format(
                            linha.fonte)))
    for pendencia in linha.pendencias:
        if pendencia not in _PENDENCIAS_DE_FONTE + _PENDENCIAS_DE_VALOR:
            achados.append((ERRO, pendencia))

    if comparacao is not None and not ajuste.get("matricula"):
        if comparacao.situacao == NAO_ENCONTRADO:
            if comparacao.sugerido is not None:
                achados.append((MATRICULA_SUGERIDA,
                                "matrícula: sugestão {} — {}".format(
                                    comparacao.sugerido.codigo,
                                    comparacao.sugerido.nome)))
            else:
                achados.append((MATRICULA,
                                "matrícula não achada no SISPREVWEB"))
        if comparacao.fonte_diverge and "fonte" not in ajuste:
            achados.append((DIVERGE, "fonte ≠ cadastro: {}".format(
                comparacao.fonte_cadastro)))

    if linha.segurado <= 0:
        achados.append((ZERADA, "sem contribuição no mês"))
    return achados


def matricula_final(linha: Linha, comparacao=None,
                    ajuste: Optional[dict] = None) -> str:
    """A matricula que vai para o arquivo: a digitada, a do SISPREVWEB ou a
    da folha, nessa ordem."""
    if ajuste and ajuste.get("matricula"):
        return ajuste["matricula"]
    if comparacao is not None:
        return comparacao.matricula_ajustada
    return linha.matricula


def linhas_finais(linhas: Sequence[Linha], comparacoes: Dict[int, object],
                  ajustes: Dict[str, dict]) -> List[Linha]:
    """O arquivo de importacao: so as marcadas, com a matricula final.

    `comparacoes` e {id da linha: comparacao}.
    """
    finais = []
    for linha in linhas:
        ajuste = ajustes.get(chave(linha))
        if not importa(linha, ajuste):
            continue
        finais.append(replace(linha, matricula=matricula_final(
            linha, comparacoes.get(id(linha)), ajuste)))
    return finais
