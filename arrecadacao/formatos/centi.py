# -*- coding: utf-8 -*-
"""A folha do Centi -- Campinapolis (camara) e Sao Felix do Araguaia.

O bloco do servidor e um formulario de rotulos com os valores na linha de
baixo. Em Campinapolis a matricula e o nome dividem a linha com os rotulos:

    Funcionario 1 - FULANA DE TAL          CPF  Nascimento  Dt. admissao
                                  123.456.789-09  16/07/1970  01/02/1993

em Sao Felix descem para a linha dos valores, com o resto:

    Funcionario                             CPF  Nascimento  Dt. admissao
    17501 - FULANO DE TAL DA SILVA  123.456.789-09  06/02/1975  11/03/2013

e o mesmo vale para o campo "Folha": la o "MENSAL" esta na linha do rotulo,
aqui na de baixo. As duas formas sao lidas.
    Cargo                Admissao   Banco ...
    ESCRITURARIO C-34    EFETIVO    1 ...
    Funcao               Folha               Carga Horaria: ...
    SECRETARIO DA CAMARA MENSAL    ...

seguido da tabela de verbas ("Codigo Evento Base calculo Referencia Provento
Desconto") e fechado por "Base calc. previdencia: 14.800,00".

Esse fecho NAO e a coluna 05. Em Campinapolis ele coincide com a base da
verba de previdencia, mas em Sao Felix sai o DOBRO dela: FULANO tem "Base
calc. previdencia: 6.595,84" e a verba "142 PREVIDENCIA RPPS 3.297,92 14,00
461,70" -- 461,70 e 14% de 3.297,92. E o proprio resumo do RPPS no fim do PDF
soma as bases das verbas (118.451,99 para 16.583,22 retidos), nao o fecho. A
base que vale e a da coluna "Base calculo" da verba; o fecho so e usado quando
a verba vem sem ela.

As verbas vem numa coluna so: o que diz se e provento ou desconto e em QUAL
coluna o valor cai, e por isso a linha e distribuida pelo cabecalho, e nao
lida como texto.

Um PDF pode juntar folhas -- "MENSAL, 13o SALARIO ADIANTAMENTO" no topo -- e
o mesmo servidor aparece uma vez em cada. Cada bloco diz a sua no campo
"Folha", e e isso que vai para `Segurado.tipo_folha`.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from ..folha import Competencia, Folha, Segurado, Verba, numero
from ..fontes import FonteDaFolha
from ..leitor_pdf import Coluna, Linha, distribuir, localizar_colunas

NOME = "Centi"

# --- cabecalho da folha ------------------------------------------------- #
RE_ENTIDADE = re.compile(r"^((?:PREFEITURA|C.MARA)\b.+)$", re.IGNORECASE)
RE_COMPETENCIA = re.compile(r"^(\d{1,2})/(\d{4})$")
# "4 - 1.1.2 - CAMARA MUNICIPAL, CAMARA MUNICIPAL, EFETIVOS": o grupo.
RE_GRUPO = re.compile(r"^(\d+)\s*-\s*(\d+(?:\.\d+)+)\s*-\s*(.+)$")

# --- bloco do servidor -------------------------------------------------- #
RE_FUNCIONARIO = re.compile(
    r"^Funcion.rio\s+(\d+)\s*-\s*(.+?)\s+CPF\b", re.IGNORECASE)
# So os rotulos ("Funcionario CPF Nascimento Dt. admissao"): a identificacao
# vem inteira na linha de baixo.
RE_ROTULOS_FUNCIONARIO = re.compile(r"^Funcion.rio\s+CPF\b", re.IGNORECASE)
RE_IDENTIFICACAO = re.compile(
    r"^(\d+)\s*-\s*(.+?)\s+(\d{3}\.\d{3}\.\d{3}-\d{2})\b")
RE_CPF = re.compile(r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b")
RE_DATA = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
RE_ROTULOS_CARGO = re.compile(r"^Cargo\s+Admiss.o\b", re.IGNORECASE)
RE_ROTULOS_FUNCAO = re.compile(r"^Fun..o\b.*\bFolha\b", re.IGNORECASE)
RE_CABECALHO_VERBA = re.compile(r"^C.digo\s+Evento\b", re.IGNORECASE)
RE_BASE_PREV = re.compile(r"Base\s+calc\.\s+previd.ncia:\s*([\d.,]+)",
                          re.IGNORECASE)

ROTULOS_VERBA = (
    ("codigo", "Código"),
    ("evento", "Evento"),
    ("base", "Base"),
    ("referencia", "Referência"),
    ("provento", "Provento"),
    ("desconto", "Desconto"),
)
VERBA_PELA_DIREITA = ("base", "referencia", "provento", "desconto")
# Onde comecam, no formulario, as colunas "Admissao" e "Folha" (x=251): o que
# esta antes e o cargo / a funcao, o que esta dali ate o "Banco" / "Carga
# Horaria" (x~374) e o tipo de admissao / a folha.
INICIO_SEGUNDA_COLUNA = 240.0
INICIO_TERCEIRA_COLUNA = 370.0


# ----------------------------------------------------------------------- #
def pontuar(linhas: Sequence[tuple]) -> int:
    """Os fechos de bloco "Base calc. previdencia:" -- assinatura do Centi."""
    return sum(1 for linha, _p in linhas if RE_BASE_PREV.search(linha.texto))


def ler(linhas: Sequence[tuple], folha: Folha) -> List[Segurado]:
    _ler_cabecalho_da_folha(linhas, folha)
    return _ler_segurados(linhas)


# ----------------------------------------------------------------------- #
def _ler_cabecalho_da_folha(linhas: Sequence[tuple], folha: Folha) -> None:
    """Entidade, tipo ("MENSAL, 13o SALARIO ...") e competencia ("07/2026").

    O tipo e a linha logo antes da competencia, sozinha.
    """
    anterior = ""
    for linha, _pagina in linhas[:15]:
        texto = linha.texto.strip()
        if not folha.entidade and RE_ENTIDADE.match(texto):
            folha.entidade = texto
        if folha.competencia is None:
            achado = RE_COMPETENCIA.match(texto)
            if achado:
                folha.competencia = Competencia(ano=int(achado.group(2)),
                                                mes=int(achado.group(1)))
                if not folha.tipo:
                    folha.tipo = anterior.title()
        anterior = texto


def _ler_segurados(linhas: Sequence[tuple]) -> List[Segurado]:
    segurados: List[Segurado] = []
    atual: Optional[Segurado] = None
    fonte: Optional[FonteDaFolha] = None
    colunas: Dict[str, Coluna] = {}
    # O que a linha seguinte traz: os valores de que formulario.
    esperando = ""

    for linha, pagina in linhas:
        texto = linha.texto.strip()

        achado = RE_GRUPO.match(texto)
        if achado:
            # O numero do grupo na folha nao e o numero da fonte no
            # SISPREVWEB ("4" aqui, "112 - CAMARA MUNICIPAL" la): sem numero
            # que case, a fonte e escolhida na tela, no catalogo inteiro.
            fonte = FonteDaFolha(numero=0, nome=achado.group(3).strip(),
                                 folha_inteira=True, bruto=texto)
            continue

        achado = RE_FUNCIONARIO.match(texto)
        if achado:
            atual = Segurado(matricula=achado.group(1),
                             nome=achado.group(2).strip(),
                             fonte=fonte, unidade=fonte.nome if fonte else "",
                             pagina=pagina)
            segurados.append(atual)
            colunas = {}
            esperando = "documentos"
            continue

        if RE_ROTULOS_FUNCIONARIO.match(texto):
            atual, colunas, esperando = None, {}, "identificacao"
            continue
        if esperando == "identificacao":
            esperando = ""
            achado = RE_IDENTIFICACAO.match(texto)
            if achado:
                atual = Segurado(matricula=achado.group(1),
                                 nome=achado.group(2).strip(),
                                 cpf=achado.group(3),
                                 fonte=fonte,
                                 unidade=fonte.nome if fonte else "",
                                 pagina=pagina)
                datas = RE_DATA.findall(texto)
                if datas:
                    atual.admissao = datas[-1]
                segurados.append(atual)
            continue

        if atual is None:
            continue

        if esperando == "documentos":
            esperando = ""
            cpf = RE_CPF.search(texto)
            if cpf:
                atual.cpf = cpf.group(1)
            datas = RE_DATA.findall(texto)
            if datas:
                atual.admissao = datas[-1]
            continue

        if RE_ROTULOS_CARGO.match(texto):
            esperando = "cargo"
            continue
        if esperando == "cargo":
            esperando = ""
            atual.cargo = _faixa(linha, 0, INICIO_SEGUNDA_COLUNA)
            atual.regime = _faixa(linha, INICIO_SEGUNDA_COLUNA,
                                  INICIO_TERCEIRA_COLUNA)
            continue

        if RE_ROTULOS_FUNCAO.match(texto):
            # "Funcao  MENSAL Folha  Carga Horaria" -- em Campinapolis o valor
            # da folha divide a linha com o proprio rotulo; em Sao Felix vem
            # na linha de baixo.
            atual.tipo_folha = _tipo_da_folha(linha)
            if not atual.tipo_folha:
                esperando = "funcao"
            continue
        if esperando == "funcao":
            esperando = ""
            atual.tipo_folha = _tipo_da_folha(linha)
            continue

        if RE_CABECALHO_VERBA.match(texto):
            colunas = localizar_colunas(_sem_marca_dagua(linha), ROTULOS_VERBA,
                                        pela_direita=VERBA_PELA_DIREITA)
            continue

        achado = RE_BASE_PREV.search(texto)
        if achado:
            _aplicar_base(atual, numero(achado.group(1)))
            atual, colunas = None, {}
            continue

        if colunas:
            verba = _montar_verba(distribuir(_sem_marca_dagua(linha), colunas))
            if verba is not None:
                atual.verbas.append(verba)

    return segurados


def _faixa(linha: Linha, inicio: float, fim: float) -> str:
    return " ".join(p.texto for p in linha.palavras if inicio <= p.x0 < fim)


def _tipo_da_folha(linha: Linha) -> str:
    return " ".join(
        p.texto for p in linha.palavras
        if INICIO_SEGUNDA_COLUNA <= p.x0 < INICIO_TERCEIRA_COLUNA
        and p.texto.casefold() != "folha").title()


def _sem_marca_dagua(linha: Linha) -> Linha:
    """A linha sem o "Conferencia" que a atravessa de x=94 a x=457.

    E' uma marca de folha conferida, desenhada como UMA palavra de 360 pontos,
    e cai em qualquer linha do bloco. No cabecalho, encosta no rotulo
    "Evento", e a coluna do evento passaria a ir ate x=457, por cima de Base e
    Referencia; numa verba, entra no meio da descricao ("PREVIDENCIA
    Conferencia RPPS").
    """
    limpa = Linha(y=linha.y)
    limpa.palavras = [p for p in linha.palavras if p.x1 - p.x0 < 150]
    return limpa


def _montar_verba(campos: Dict[str, str]) -> Optional[Verba]:
    """Codigo de digitos e um valor em Provento ou em Desconto.

    A linha de totais do bloco ("14.800,00 13.081,87") tem os dois valores e
    nenhum codigo, e fica de fora por isso.
    """
    codigo = campos.get("codigo", "").strip()
    if not codigo.isdigit():
        return None
    provento = numero(campos.get("provento", ""))
    desconto = numero(campos.get("desconto", ""))
    if provento is None and desconto is None:
        return None
    return Verba(
        codigo=codigo,
        descricao=campos.get("evento", "").strip(),
        tipo="P" if provento is not None else "D",
        referencia=numero(campos.get("referencia", "")),
        base=numero(campos.get("base", "")),
        valor=provento if provento is not None else desconto,
    )


def _aplicar_base(segurado: Segurado, declarada: Optional[float]) -> None:
    """A base do fecho so vai para a verba de previdencia que vier SEM base.

    A coluna "Base calculo" da propria verba e a base do desconto -- ver o
    cabecalho deste modulo: em Sao Felix o fecho imprime o dobro dela.
    """
    previdencias = segurado.verbas_previdencia
    if len(previdencias) == 1 and declarada and previdencias[0].base is None:
        previdencias[0].base = declarada
