# -*- coding: utf-8 -*-
"""As colunas do arquivo de importacao do SISPREVWEB, e como preenche-las.

O documento LAYOUT DE IMPORTACAO / MODULO DE ARRECADACAO descreve dois modelos.
O que se usa aqui e o **simplificado**, para segurados ja cadastrados, e ele
tem DEZ campos -- todos obrigatorios:

    01 Identificador do Segurado (Matricula)      Texto
    02 Nome                                       Texto
    03 Ano                                        Numerico
    04 Mes                                        Numerico   01 a 13
    05 Remuneracao de Contribuicao (Valor Base)   Numerico
    06 Contribuicao Previdenciaria - Segurado     Numerico
    07 Contribuicao Previdenciaria - Patronal Normal          Numerico
    08 Contribuicao Previdenciaria - Patronal Custo Especial  Numerico
    09 Identificador da Fonte Pagadora            Numerico
    10 Categoria                                  Texto

Circula tambem uma versao de OITO campos, sem os dois patronais, com a fonte
pagadora e a categoria renumeradas para 07 e 08. As duas existem aqui porque a
diferenca nao e de gosto: mandar oito colunas onde o importador espera dez faz
a fonte pagadora cair na coluna do patronal, e o arquivo ou e recusado ou entra
torto. Quem exporta escolhe, e o nome do modelo aparece na tela.

Os dois patronais saem da propria folha: a verba de nota "10004 - Base Patronal
para RPPS" e a parte normal. **Custo especial nao existe nesta folha** e sai
zero -- e um aporte de plano de amortizacao, que quando houver vira verba
propria e entra aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from .folha import CATEGORIA_PADRAO, Competencia, Folha, Segurado

# Custo especial: a folha nao tem verba para ele. Zero explicito, e nao coluna
# vazia -- o campo e obrigatorio e numerico.
PATRONAL_CUSTO_ESPECIAL = 0.0


@dataclass(frozen=True)
class Campo:
    """Uma coluna do arquivo de saida."""

    chave: str
    titulo: str
    numerico: bool = False
    decimais: int = 0
    largura: int = 120           # largura sugerida da coluna na tela


# As colunas, na ordem do documento. `decimais=2` marca as de dinheiro.
CAMPOS = {
    "matricula": Campo("matricula", "Identificador do Segurado", largura=110),
    "nome": Campo("nome", "Nome", largura=260),
    "ano": Campo("ano", "Ano", numerico=True, largura=60),
    "mes": Campo("mes", "Mês", numerico=True, largura=55),
    "base": Campo("base", "Remuneração de Contribuição",
                  numerico=True, decimais=2, largura=160),
    "segurado": Campo("segurado", "Contribuição - Segurado",
                      numerico=True, decimais=2, largura=150),
    "patronal": Campo("patronal", "Contribuição - Patronal Normal",
                      numerico=True, decimais=2, largura=170),
    "especial": Campo("especial", "Contribuição - Patronal Custo Especial",
                      numerico=True, decimais=2, largura=200),
    "fonte": Campo("fonte", "Identificador da Fonte Pagadora", largura=170),
    "categoria": Campo("categoria", "Categoria", largura=110),
}

MODELO_COMPLETO = "completo"
MODELO_REDUZIDO = "reduzido"

ORDEM = {
    MODELO_COMPLETO: ("matricula", "nome", "ano", "mes", "base", "segurado",
                      "patronal", "especial", "fonte", "categoria"),
    MODELO_REDUZIDO: ("matricula", "nome", "ano", "mes", "base", "segurado",
                      "fonte", "categoria"),
}

NOMES_DOS_MODELOS = {
    MODELO_COMPLETO: "Simplificado — 10 campos (com patronal)",
    MODELO_REDUZIDO: "Reduzido — 8 campos (sem patronal)",
}


def campos_do_modelo(modelo: str) -> List[Campo]:
    return [CAMPOS[chave] for chave in ORDEM.get(modelo, ORDEM[MODELO_COMPLETO])]


# ---------------------------------------------------------------------- #
@dataclass
class Linha:
    """Um segurado ja traduzido para as colunas do layout.

    Guarda tambem o que NAO vai no arquivo -- pagina, situacao, codigos das
    verbas somadas -- porque e disso que quem confere precisa na tela antes de
    exportar: uma linha com dois codigos de previdencia somados merece um
    olhar, e depois de exportada nao ha mais como saber de onde o numero veio.
    """

    matricula: str
    nome: str
    ano: int
    mes: int
    base: float
    segurado: float
    patronal: float
    especial: float
    fonte: str
    categoria: str

    # conferencia, fora do arquivo
    estrutura: str = ""
    unidade: str = ""
    fonte_nome: str = ""          # "001 - 2002 -GABINETE EFETIVOS F 1.500"
    fonte_origem: str = ""        # como o codigo foi obtido -- ver `fontes`
    situacao: str = ""
    verbas: str = ""
    pagina: int = 0
    # Tudo o que o servidor recebeu no mes. Nao e coluna do layout -- e o
    # numero contra o qual a folha e conferida, e que NAO bate com a base de
    # contribuicao. Ver `Segurado.total_proventos`.
    proventos: float = 0.0
    pendencias: Sequence[str] = ()

    def valores(self, modelo: str) -> List:
        return [getattr(self, chave) for chave in ORDEM.get(modelo, ORDEM[MODELO_COMPLETO])]

    @property
    def tem_pendencia(self) -> bool:
        return bool(self.pendencias)


def montar(folha: Folha, codigo_da_fonte: Callable[[str], str],
           competencia: Optional[Competencia] = None,
           categoria: str = CATEGORIA_PADRAO) -> List[Linha]:
    """Traduz a folha lida para as linhas do arquivo de importacao.

    `codigo_da_fonte` recebe a fonte pagadora do segurado (`FonteDaFolha`, ou
    None quando a folha nao trouxe grupo) e devolve `(codigo, origem)` -- ou so
    o codigo. Devolver "" marca a linha como pendente, em vez de exportar um
    campo obrigatorio em branco.

    `competencia` sobrepoe a da folha -- a tela deixa o usuario corrigir ano e
    mes quando o cabecalho vier ilegivel.
    """
    alvo = competencia or folha.competencia_de_saida()
    linhas: List[Linha] = []

    for segurado in folha.segurados:
        codigo, origem = _resolver_fonte(codigo_da_fonte, segurado)
        linhas.append(Linha(
            matricula=segurado.matricula,
            nome=segurado.nome,
            ano=alvo.ano if alvo else 0,
            mes=alvo.mes if alvo else 0,
            base=segurado.base_de_contribuicao,
            segurado=segurado.contribuicao_do_segurado,
            patronal=segurado.patronal_normal,
            especial=PATRONAL_CUSTO_ESPECIAL,
            fonte=codigo,
            categoria=categoria,
            estrutura=segurado.estrutura,
            unidade=segurado.unidade,
            fonte_nome=str(segurado.fonte) if segurado.fonte else "",
            fonte_origem=origem,
            situacao=segurado.situacao,
            verbas=segurado.codigos_previdencia,
            pagina=segurado.pagina,
            proventos=segurado.total_proventos,
            pendencias=_pendencias(segurado, codigo, alvo),
        ))
    return linhas


def _resolver_fonte(codigo_da_fonte: Callable, segurado: Segurado):
    """Chama quem resolve a fonte e aceita as duas formas de resposta.

    `(codigo, origem)` quando quem chama sabe dizer COMO chegou no codigo -- a
    tela mostra isso numa coluna, porque "casou pelo nome inteiro" e "casou so
    pelo numero" pedem confianca diferente. So o codigo tambem serve, e e o que
    um script usa.
    """
    resposta = codigo_da_fonte(segurado.fonte)
    if isinstance(resposta, tuple):
        codigo, origem = (list(resposta) + ["", ""])[:2]
    else:
        codigo, origem = resposta, ""
    return ((codigo or "").strip(), (origem or "").strip())


def _pendencias(segurado: Segurado, codigo: str,
                competencia: Optional[Competencia]) -> List[str]:
    """O que impede esta linha de ser importada como esta.

    Uma lista por linha, e nao um aviso geral da folha: com 774 registros, "ha
    fontes pagadoras sem codigo" nao diz QUAIS linhas, e quem confere precisa
    achar as tres no meio das setecentas.
    """
    faltas: List[str] = []
    if not segurado.matricula:
        faltas.append("sem matrícula")
    if not segurado.nome:
        faltas.append("sem nome")
    if competencia is None or not competencia.valida:
        faltas.append("competência inválida")
    if segurado.fonte is None:
        faltas.append("sem fonte pagadora na folha")
    elif not codigo:
        faltas.append("fonte pagadora sem código")
    if segurado.contribuicao_do_segurado <= 0:
        faltas.append("sem contribuição no mês")
    elif segurado.base_de_contribuicao <= 0:
        faltas.append("sem base de cálculo")
    return faltas


def resumo(linhas: Sequence[Linha]) -> Dict[str, float]:
    """Os numeros que a tela mostra nos cartoes de metrica."""
    return {
        "registros": len(linhas),
        "proventos": round(sum(l.proventos for l in linhas), 2),
        "base": round(sum(l.base for l in linhas), 2),
        "segurado": round(sum(l.segurado for l in linhas), 2),
        "patronal": round(sum(l.patronal for l in linhas), 2),
        "pendentes": sum(1 for l in linhas if l.tem_pendencia),
    }
