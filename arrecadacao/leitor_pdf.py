# -*- coding: utf-8 -*-
r"""Leitura do PDF da folha: de palavras soltas de volta a linhas e colunas.

O PDF da folha nao tem tabela nenhuma -- tem texto posicionado. Pedir
`pagina.get_text()` devolve as palavras na ordem interna do arquivo, que no
gerador da Agili intercala o BLOCO DOS ROTULOS com o BLOCO DOS VALORES:

    Funcionario(a)
    Estrutura ADM
    C.P.F.
    Data de Admissao
    1.02.001
    123.456.789-09
    02/03/2022

Ou seja: os tres rotulos primeiro, os tres valores depois, e nada dizendo qual
valor pertence a qual rotulo. Ler assim e adivinhar. Pior: a ordem muda de uma
folha para outra (a de rescisao nao traz os mesmos campos que a mensal), e o
programa que adivinha certo na folha de agosto erra na de setembro sem avisar.

Aqui a pagina e remontada pelas COORDENADAS, que sao o que o olho de quem
confere usa:

* palavras com o mesmo topo (`y0`) formam uma linha;
* dentro da linha, um espaco grande entre uma palavra e a seguinte separa uma
  celula da outra -- e assim "FULANA DE TAL DA SILVA SANTOS" continua sendo
  UM valor, e nao quatro;
* cada celula e atribuida a coluna do cabecalho mais proxima.

O detalhe que obriga a distinguir dois tipos de coluna: **texto e alinhado a
esquerda, numero e alinhado a direita**. Na folha de rescisao a situacao
"Exonerado" comeca 7 pontos ANTES do rotulo "Situacao", porque e mais larga que
"Ativo"; ja "4.810,11" termina exatamente onde termina o rotulo "Base". Casar
numero pela borda esquerda erra por uma coluna inteira -- o valor do desconto
vira base de calculo --, e foi por isso que `Coluna` guarda de que lado ela
alinha.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import fitz  # PyMuPDF

# Duas palavras pertencem a mesma linha quando os topos diferem menos do que
# isto. A folha usa corpo 6 a 8: linhas vizinhas distam 9 pontos ou mais, e
# palavras da mesma linha raramente diferem de 1 -- mas diferem, porque o
# gerador desenha o texto em caixas de altura propria.
TOLERANCIA_LINHA = 3.0

# Espaco em branco que separa uma celula da seguinte. A medida e apertada de
# proposito: entre palavras de um mesmo nome o vao e de 1,9 ponto, e o menor
# vao ENTRE COLUNAS na folha inteira e o de 10,8 que separa a data de admissao
# do CPF. Com 12 -- o palpite obvio -- data e CPF viravam uma celula so, e o
# CPF saia vazio em todos os 774 registros sem erro nenhum aparecer.
VAO_ENTRE_CELULAS = 8.0

# Abaixo disto a pagina nao tem texto util: e folha digitalizada (imagem).
MIN_CARACTERES_PAGINA = 120


@dataclass(frozen=True)
class Palavra:
    """Uma palavra e onde ela esta na pagina."""

    texto: str
    x0: float
    x1: float
    y0: float

    @property
    def centro(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Celula:
    """Palavras vizinhas de uma mesma linha, separadas do resto por um vao."""

    texto: str
    x0: float
    x1: float

    @property
    def centro(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Linha:
    """Uma linha visual da pagina, ja quebrada em celulas."""

    y: float
    palavras: List[Palavra] = field(default_factory=list)
    _celulas: Optional[List[Celula]] = field(default=None, repr=False)

    @property
    def texto(self) -> str:
        """A linha como se le, com um espaco entre palavras."""
        return " ".join(p.texto for p in self.palavras)

    @property
    def celulas(self) -> List[Celula]:
        """As celulas da linha, da esquerda para a direita (calculadas uma vez)."""
        if self._celulas is None:
            self._celulas = _agrupar_em_celulas(self.palavras)
        return self._celulas

    def faixa(self, inicio: float, fim: float) -> str:
        """O texto das palavras que comecam dentro da faixa horizontal."""
        return " ".join(p.texto for p in self.palavras if inicio <= p.x0 < fim)

    def comeca_com(self, prefixo: str) -> bool:
        return self.texto.startswith(prefixo)


def _agrupar_em_celulas(palavras: Sequence[Palavra]) -> List[Celula]:
    """Quebra a linha onde o espaco em branco passa de `VAO_ENTRE_CELULAS`."""
    if not palavras:
        return []
    ordenadas = sorted(palavras, key=lambda p: p.x0)
    celulas: List[Celula] = []
    atual = [ordenadas[0]]
    for palavra in ordenadas[1:]:
        if palavra.x0 - atual[-1].x1 > VAO_ENTRE_CELULAS:
            celulas.append(_fechar_celula(atual))
            atual = [palavra]
        else:
            atual.append(palavra)
    celulas.append(_fechar_celula(atual))
    return celulas


def _fechar_celula(palavras: List[Palavra]) -> Celula:
    return Celula(texto=" ".join(p.texto for p in palavras),
                  x0=palavras[0].x0, x1=palavras[-1].x1)


def linhas_da_pagina(pagina) -> List[Linha]:
    """As linhas visuais da pagina, de cima para baixo.

    Agrupa por `y0` arredondado a `TOLERANCIA_LINHA`. Arredondar, e nao
    comparar com a linha anterior, porque a comparacao encadeada faz duas
    linhas distantes acabarem no mesmo grupo quando ha uma terceira no meio --
    o efeito domino que junta o rodape com a ultima verba.
    """
    grupos: Dict[int, List[Palavra]] = {}
    for x0, y0, x1, _y1, texto, *_resto in pagina.get_text("words"):
        if not texto.strip():
            continue
        chave = int(round(y0 / TOLERANCIA_LINHA))
        grupos.setdefault(chave, []).append(
            Palavra(texto=texto, x0=x0, x1=x1, y0=y0))

    linhas = [Linha(y=chave * TOLERANCIA_LINHA, palavras=sorted(p, key=lambda w: w.x0))
              for chave, p in sorted(grupos.items())]
    return linhas


# ---------------------------------------------------------------------- #
# colunas
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class Coluna:
    """Uma coluna do cabecalho: onde ela esta e de que lado o valor alinha.

    `pela_direita` vale para as colunas de dinheiro da tabela de verbas. Ali o
    gerador alinha numero a direita: "4.810,11", "673,42" e "17.055,84"
    comecam em pontos diferentes e TERMINAM todos em 450,4 -- exatamente onde
    termina o rotulo "Base". Casar essas pela borda esquerda erra por uma
    coluna inteira, e o erro e silencioso: o valor do desconto entra como base
    de calculo e a guia sai com o numero errado.
    """

    chave: str
    x0: float
    x1: float
    pela_direita: bool = False

    @property
    def centro(self) -> float:
        return (self.x0 + self.x1) / 2

    def distancia(self, celula: Celula) -> float:
        """Quao longe a celula esta desta coluna, no criterio que ela usa.

        Fora da tabela de verbas o gerador CENTRALIZA o valor no rotulo --
        matricula, situacao, estrutura, data, CPF e PIS batem centro com centro
        com menos de um ponto de diferenca. So o nome foge disso: ele e longo,
        alinha pela esquerda, e o centro de "FULANA DE TAL DA SILVA SANTOS"
        cai mais perto do centro da coluna "Matricula" do que do da propria
        coluna do nome. Por isso a distancia e a MENOR entre a do centro e a da
        borda esquerda: cada coluna e encontrada pelo criterio que de fato a
        alinha, sem precisar dizer de antemao qual e qual.
        """
        if self.pela_direita:
            return abs(celula.x1 - self.x1)
        return min(abs(celula.x0 - self.x0), abs(celula.centro - self.centro))


def localizar_colunas(linha: Linha, rotulos: Sequence[Tuple[str, str]],
                      pela_direita: Sequence[str] = ()) -> Dict[str, Coluna]:
    """Acha, na linha de cabecalho, onde cada coluna comeca e termina.

    `rotulos` e uma sequencia de (chave, primeira palavra do rotulo) NA ORDEM
    em que as colunas aparecem. Procurar pela primeira palavra -- "Data", e nao
    "Data de Admissao" -- porque o rotulo de duas palavras ja vem quebrado em
    palavras separadas, e porque a ordem garante que "Data" nao seja confundida
    com outra ocorrencia mais a esquerda.

    Devolve so as colunas encontradas: uma folha sem PIS/PASEP simplesmente nao
    traz essa chave, e quem le decide se isso e um problema.
    """
    achadas: Dict[str, Coluna] = {}
    indice = 0
    proprias = {palavra.casefold() for _, palavra in rotulos}

    for chave, primeira_palavra in rotulos:
        alvo = primeira_palavra.casefold()
        for posicao in range(indice, len(linha.palavras)):
            if linha.palavras[posicao].texto.casefold() != alvo:
                continue
            palavra = linha.palavras[posicao]
            # O rotulo pode ter mais palavras ("Estrutura ADM"): a borda
            # direita da coluna e a da ultima palavra colada nele.
            fim = palavra.x1
            seguinte = posicao + 1
            while (seguinte < len(linha.palavras)
                   and linha.palavras[seguinte].x0 - fim <= VAO_ENTRE_CELULAS
                   and linha.palavras[seguinte].texto.casefold() not in proprias):
                fim = linha.palavras[seguinte].x1
                seguinte += 1
            achadas[chave] = Coluna(chave=chave, x0=palavra.x0, x1=fim,
                                    pela_direita=chave in pela_direita)
            indice = posicao + 1
            break
    return achadas


def distribuir(linha: Linha, colunas: Dict[str, Coluna],
               tolerancia: float = 60.0) -> Dict[str, str]:
    """Cada celula da linha vai para a coluna mais proxima.

    Nao ha divisa fixa entre colunas, e de proposito. Dividir no meio do caminho
    entre dois rotulos parece natural e erra logo no primeiro registro: o nome
    "FULANA DE TAL DA SILVA SANTOS" termina DEPOIS do meio do caminho entre
    "Funcionario(a)" e "Matricula", e a ultima palavra do nome viraria a
    matricula. Medir a distancia de cada celula ate cada rotulo resolve os dois
    casos, porque a celula inteira -- e nao a palavra solta -- e que procura o
    seu lugar.

    `tolerancia` descarta o que esta longe de tudo: numa folha de outro
    gerador, uma coluna a mais no meio da linha nao deve ser empurrada para a
    coluna vizinha como se fosse dela.
    """
    resultado: Dict[str, List[str]] = {chave: [] for chave in colunas}
    for celula in linha.celulas:
        melhor: Optional[Coluna] = None
        menor = tolerancia
        for coluna in colunas.values():
            distancia = coluna.distancia(celula)
            if distancia < menor:
                menor, melhor = distancia, coluna
        if melhor is not None:
            resultado[melhor.chave].append(celula.texto)
    return {chave: " ".join(partes).strip() for chave, partes in resultado.items()}


# ---------------------------------------------------------------------- #
# documento
# ---------------------------------------------------------------------- #
@dataclass
class Pagina:
    """Uma pagina ja remontada."""

    numero: int
    linhas: List[Linha]

    @property
    def tem_texto(self) -> bool:
        return sum(len(l.texto) for l in self.linhas) >= MIN_CARACTERES_PAGINA


def abrir(caminho: str, progresso=None) -> List[Pagina]:
    """Le o PDF inteiro e devolve as paginas remontadas.

    `progresso` recebe (feitos, total, texto) -- a folha mensal tem 225 paginas
    e a janela precisa dizer que esta viva enquanto elas passam.
    """
    documento = fitz.open(caminho)
    try:
        total = len(documento)
        paginas: List[Pagina] = []
        for indice, pagina in enumerate(documento, start=1):
            paginas.append(Pagina(numero=indice, linhas=linhas_da_pagina(pagina)))
            if progresso and (indice % 10 == 0 or indice == total):
                progresso(indice, total,
                          "Lendo a folha: pagina {} de {}...".format(indice, total))
        return paginas
    finally:
        documento.close()


def paginas_sem_texto(paginas: Sequence[Pagina]) -> List[int]:
    """Numeros das paginas que vieram como imagem (folha digitalizada).

    Este programa nao faz OCR: uma folha escaneada nao tem os numeros que ele
    precisa somar, e um OCR errando um digito em "4.810,11" produz uma guia de
    recolhimento errada -- calado. Melhor apontar as paginas e parar.
    """
    return [p.numero for p in paginas if not p.tem_texto]
