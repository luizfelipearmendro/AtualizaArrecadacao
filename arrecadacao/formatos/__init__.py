# -*- coding: utf-8 -*-
"""Os formatos de folha que o programa sabe ler, e como escolher entre eles.

Cada prefeitura contrata o seu sistema de folha, e o PDF que sai de um nao tem
nada a ver com o do outro: muda o que abre o bloco do servidor, muda a tabela
de verbas, muda ate onde mora a fonte pagadora. Sao 29 municipios -- tratar o
primeiro formato como "o" formato era questao de tempo ate quebrar, e quebrou
na folha de Rosario Oeste, que nao tem UMA linha em comum com a de Aripuana.

Por isso cada formato e um modulo que responde duas perguntas:

    pontuar(linhas) -> int      quantos blocos MEUS este PDF tem?
    ler(linhas, folha)          extraia o cabecalho e os segurados

Quem abre o arquivo nao escolhe nada: o despachante pergunta a todos e fica com
o de maior pontuacao. As marcas sao exclusivas -- o PDF de um gerador pontua
zero no outro --, entao a escolha nao e um palpite.

Acrescentar o terceiro formato e escrever um modulo com essas duas funcoes e
inscrever ele em `LEITORES`. Nada do que ja funciona precisa ser tocado, e e
esse o ponto: o proximo municipio com folha diferente nao deve exigir mexer no
leitor que ja esta em producao.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from . import (agili, arfolha, betha, betha_extrato, centi, duralex,
               fastreport, fiorilli)

# A ordem nao importa para a escolha (vence a pontuacao), so para a mensagem
# que a tela mostra quando nenhum reconhece o arquivo.
LEITORES = (agili, arfolha, betha, betha_extrato, centi, duralex, fastreport,
            fiorilli)


def reconhecer(linhas: Sequence[tuple]):
    """O leitor que mais reconhece este PDF, ou None se nenhum reconhece."""
    melhor, pontos = None, 0
    for leitor in LEITORES:
        quantos = leitor.pontuar(linhas)
        if quantos > pontos:
            melhor, pontos = leitor, quantos
    return melhor


def por_nome(nome: str):
    """O leitor de NOME `nome` -- o que a regra do municipio fixou --, ou None."""
    return next((l for l in LEITORES if l.NOME == nome), None)


def nomes() -> List[str]:
    """Os formatos conhecidos, para a mensagem de erro dizer quais sao."""
    return [leitor.NOME for leitor in LEITORES]
