# -*- coding: utf-8 -*-
"""A folha analitica do Fiorilli -- Primavera do Leste.

Duas coisas distinguem este formato dos outros dois e mandam no jeito de ler.

A primeira: as verbas saem em DUAS colunas lado a lado, proventos a esquerda e
descontos a direita, duas por linha visual. A linha

    P 002 VENCIMENTO MEN/HOR 30.00D 3.950,73 D 332 MENS. SINDICATO 3.00 48,63

e um provento E um desconto, de assuntos diferentes. Ler a linha inteira como
uma verba so junta o vencimento com a mensalidade do sindicato; por isso a
linha e quebrada toda vez que aparece um "P" ou um "D" sozinho seguido do
codigo da verba.

A segunda, e e uma boa noticia: o bloco fecha com a base previdenciaria
IMPRESSA -- "Base Prev. 4.345,80". E' exatamente a coluna 05 do arquivo do
SISPREVWEB, dita pela propria folha, entao nao e preciso deduzi-la da
aliquota. A diferenca nao e teorica: 608,41 descontados a 14% dao 4.345,79 por
divisao, e a folha diz 4.345,80. Um centavo por servidor, 2.283 servidores.
"""
from __future__ import annotations

import re
import string
from typing import Dict, List, Optional, Sequence

from ..folha import Competencia, Folha, Segurado, Verba, numero
from ..fontes import FonteDaFolha
from ..leitor_pdf import Coluna, Linha, Palavra, distribuir, localizar_colunas

NOME = "Fiorilli"

# --- cabecalho da folha ------------------------------------------------- #
RE_ENTIDADE = re.compile(
    r"^((?:PREFEITURA|C.MARA)\s+(?:MUNICIPAL\s+)?DE\s+.+)$", re.IGNORECASE)
# O rotulo "Mes/Ano" vem numa linha e a competencia logo abaixo -- mas nem
# sempre sozinha: na folha da camara ela sai colada no endereco, em
# "PRIMAVERA , 300, . PRIMAVERA DO LESTE-MT 07/2026". Por isso a competencia
# e procurada PALAVRA a palavra nas linhas seguintes ao rotulo, e nao como
# linha inteira. "24/07/2026" e data e nao casa: tem tres pedacos.
RE_COMPETENCIA = re.compile(r"^(\d{1,2})/(\d{4})$")
RE_MES_ANO = re.compile(r"^M.s\s*/\s*Ano$", re.IGNORECASE)
RE_TIPO = re.compile(r"Data\s+Pagamento:.*[-\u2013]\s*(.+?)\s*$", re.IGNORECASE)

# --- grupo de fonte pagadora -------------------------------------------- #
# "Divisao: 000002 - EXECUTIVO MUNICIPAL". Na folha da camara nao existe
# nenhuma: a folha inteira e de uma fonte so.
RE_DIVISAO = re.compile(r"^Divis.o:\s*(\d+)\s*[-\u2013]\s*(.+)$", re.IGNORECASE)

# --- bloco do servidor -------------------------------------------------- #
# "1100-1 ANA CLAUDIA HAGEMANN LOPES 02/03/2000 0008 - AUXILIAR BIBLIOTECARIO"
# A matricula traz o vinculo depois do tracinho, como em "9999-1".
RE_SERVIDOR = re.compile(r"^(\d+-\d+)\s+(\S.*)$")
RE_ADMISSAO = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
RE_CARGO = re.compile(r"(\d{3,4}\s*[-\u2013]\s*\D.*)$")

# --- rodape do bloco, onde mora a base ---------------------------------- #
ROTULOS_RODAPE = (
    ("base_fgts", "Base"),
    ("valor_fgts", "Valor"),
    ("base_prev", "Base"),
    ("base_irrf", "Base"),
    ("proventos", "Proventos"),
    ("descontos", "Descontos"),
    ("liquido", "Líquido"),
)
# Todos os numeros do rodape sao colados a direita, embaixo do rotulo.
RODAPE_PELA_DIREITA = tuple(chave for chave, _ in ROTULOS_RODAPE)
RE_RODAPE = re.compile(r"^Base\s+FGTS\s+Valor\s+FGTS\s+Base\s+Prev", re.IGNORECASE)

RE_CODIGO_DA_VERBA = re.compile(r"^\d{3}$")
RE_DINHEIRO = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d\d$")
# "30.00D", "14.00", "25,00", "20%": o quanto, logo antes do valor.
RE_REFERENCIA = re.compile(r"^[\d.,]+[A-Za-z%]?$")


# ----------------------------------------------------------------------- #
def pontuar(linhas: Sequence[tuple]) -> int:
    """Quantos rodapes de bloco DESTE formato o PDF tem.

    O rodape, e nao o cabecalho do servidor: "Matricula Nome do Trabalhador"
    aparece em folha de qualquer fabricante, mas "Base FGTS Valor FGTS Base
    Prev." e assinatura deste.
    """
    return sum(1 for linha, _p in linhas if RE_RODAPE.match(linha.texto.strip()))


def ler(linhas: Sequence[tuple], folha: Folha) -> List[Segurado]:
    """Preenche o cabecalho da folha e devolve os segurados."""
    _ler_cabecalho_da_folha(linhas, folha)
    return _ler_segurados(linhas)


# ----------------------------------------------------------------------- #
def _ler_cabecalho_da_folha(linhas: Sequence[tuple], folha: Folha) -> None:
    """Entidade, competencia e tipo: tudo nas primeiras linhas da pagina 1."""
    esperando_competencia = False
    for linha, _pagina in linhas[:40]:
        texto = linha.texto.strip()

        if not folha.entidade:
            achado = RE_ENTIDADE.match(texto)
            if achado:
                folha.entidade = achado.group(1).strip()
                continue

        if folha.competencia is None:
            if RE_MES_ANO.match(texto):
                esperando_competencia = True
                continue
            if esperando_competencia:
                for palavra in linha.palavras:
                    achado = RE_COMPETENCIA.match(palavra.texto)
                    if achado:
                        folha.competencia = Competencia(
                            ano=int(achado.group(2)), mes=int(achado.group(1)))
                        esperando_competencia = False
                        break
                if folha.competencia is not None:
                    continue

        if not folha.tipo:
            achado = RE_TIPO.search(texto)
            if achado:
                folha.tipo = achado.group(1).strip().title()


def _ler_segurados(linhas: Sequence[tuple]) -> List[Segurado]:
    """Percorre as linhas abrindo um servidor a cada matricula."""
    segurados: List[Segurado] = []
    atual: Optional[Segurado] = None
    fonte_corrente: Optional[FonteDaFolha] = None
    colunas_rodape: Dict[str, Coluna] = {}
    esperando_rodape = False

    for linha, pagina in linhas:
        texto = linha.texto.strip()

        achado = RE_DIVISAO.match(texto)
        if achado:
            fonte_corrente = FonteDaFolha(numero=int(achado.group(1)),
                                          nome=achado.group(2).strip(),
                                          bruto=texto)
            continue

        if RE_RODAPE.match(texto):
            colunas_rodape = localizar_colunas(linha, ROTULOS_RODAPE,
                                               pela_direita=RODAPE_PELA_DIREITA)
            esperando_rodape = True
            continue

        # A linha de numeros logo depois dos rotulos fecha o bloco: e la que
        # esta a base previdenciaria que a folha declara.
        if esperando_rodape:
            esperando_rodape = False
            if atual is not None:
                _aplicar_base(atual, distribuir(linha, colunas_rodape))
                atual = None
            continue

        achado = RE_SERVIDOR.match(texto)
        if achado:
            atual = _abrir_servidor(achado, pagina, fonte_corrente)
            segurados.append(atual)
            continue

        if atual is not None:
            atual.verbas.extend(_ler_verbas(linha))

    return segurados


def _abrir_servidor(achado, pagina: int,
                    fonte: Optional[FonteDaFolha]) -> Segurado:
    """Matricula, nome, admissao e cargo da linha de abertura do bloco."""
    resto = achado.group(2).strip()

    cargo = ""
    acha_cargo = RE_CARGO.search(resto)
    if acha_cargo:
        cargo = acha_cargo.group(1).strip()
        resto = resto[:acha_cargo.start()].strip()

    admissao = ""
    acha_data = RE_ADMISSAO.search(resto)
    if acha_data:
        admissao = acha_data.group(1)
        resto = resto[:acha_data.start()].strip()

    return Segurado(
        matricula=achado.group(1),
        nome=resto,
        admissao=admissao,
        cargo=cargo,
        fonte=fonte,
        estrutura=fonte.chave if fonte else "",
        unidade=fonte.nome if fonte else "",
        pagina=pagina,
    )


def _aplicar_base(segurado: Segurado, rodape: Dict[str, str]) -> None:
    """Poe na verba de previdencia a base que a folha imprime.

    Preferir a base declarada a deduzi-la da aliquota nao e preciosismo: os
    dois caminhos divergem em centavos por servidor, e e a folha que manda.
    Quando o bloco traz mais de uma previdencia -- quem entrou em beneficio no
    meio do mes --, nao da para saber quanto da base e de cada uma, e ai cada
    verba fica com a sua, deduzida da propria aliquota.
    """
    previdencias = segurado.verbas_previdencia
    declarada = numero(rodape.get("base_prev", ""))

    if len(previdencias) == 1 and declarada:
        previdencias[0].base = declarada
        return

    for verba in previdencias:
        if verba.base is None and verba.referencia and verba.valor:
            verba.base = round(verba.valor * 100 / verba.referencia, 2)


def _ler_verbas(linha: Linha) -> List[Verba]:
    """As verbas de uma linha -- podem ser duas, uma de cada coluna."""
    return [v for pedaco in _quebrar_em_verbas(linha.palavras)
            if (v := _montar_verba(pedaco)) is not None]


def _quebrar_em_verbas(palavras: Sequence[Palavra]) -> List[List[Palavra]]:
    """Reparte as palavras da linha em "P/D + codigo + ... + valor".

    Exigir que o "P" ou o "D" venham colados ao codigo de tres digitos e o que
    impede uma descricao de ser cortada no meio: "MENS. SINDICATO - SINSPP"
    tem palavras de uma letra, mas nenhuma delas e seguida de "332".
    """
    inicios = [posicao for posicao, palavra in enumerate(palavras)
               if palavra.texto in ("P", "D")
               and posicao + 1 < len(palavras)
               and RE_CODIGO_DA_VERBA.match(palavras[posicao + 1].texto)]
    if not inicios:
        return []
    return [list(palavras[inicio:fim])
            for inicio, fim in zip(inicios, inicios[1:] + [len(palavras)])]


def _montar_verba(pedaco: Sequence[Palavra]) -> Optional[Verba]:
    """Uma verba: tipo, codigo, descricao, referencia e valor."""
    textos = [p.texto for p in pedaco]
    if len(textos) < 3:
        return None

    tipo, codigo, resto = textos[0], textos[1], textos[2:]

    # O valor e o ULTIMO dinheiro da verba. "QUINQUENIO 25,00 1.047,84" tem
    # dois numeros com virgula, e o que vale e o de tras.
    fim = None
    for posicao in range(len(resto) - 1, -1, -1):
        if RE_DINHEIRO.match(resto[posicao]):
            fim = posicao
            break
    if fim is None:
        return None

    valor = numero(resto[fim])
    corpo = resto[:fim]

    referencia = None
    if corpo and RE_REFERENCIA.match(corpo[-1]):
        referencia = _referencia(corpo[-1])
        corpo = corpo[:-1]

    return Verba(
        codigo=codigo,
        descricao=" ".join(corpo).strip(),
        tipo=tipo,
        referencia=referencia,
        base=None,
        valor=valor,
    )


def _referencia(texto: str) -> Optional[float]:
    """O "quanto" da verba: "30.00D", "14.00", "25,00", "20%", "11.177".

    Nesta folha o ponto e separador DECIMAL, e nao de milhar: "14.00" sao
    catorze por cento. Ler isso com a regra brasileira devolve 1.400, e a base
    deduzida de uma aliquota cem vezes maior sai cem vezes menor -- 17,48 no
    lugar de 1.748,31. Com virgula, o numero e brasileiro mesmo.
    """
    limpo = texto.strip().rstrip("%").rstrip(string.ascii_letters)
    if "," in limpo:
        return numero(limpo)
    try:
        return float(limpo)
    except ValueError:
        return None
