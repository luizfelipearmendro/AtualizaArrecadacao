# -*- coding: utf-8 -*-
"""A folha de pagamento da camara de Sao Jose do Povo.

O quarto gerador. Como o Fiorilli, poe proventos a esquerda e descontos a
direita, duas verbas por linha visual -- mas com colunas proprias, e aqui a
divisa entre os dois lados e limpa: nada de provento passa de x=300 e nada de
desconto fica antes. Por isso a linha e cortada nessa divisa e cada metade e
lida com o seu proprio cabecalho.

A particularidade que importa e outra: a verba de previdencia NAO se chama
previdencia. Chama-se "FUNPREV" -- e `Verba.e_previdencia_do_segurado`, que
reconhece pela descricao, nao a veria. Os cinco servidores sairiam com base e
contribuicao ZERO, sem erro nenhum na tela. Ver a lista de nomes la.

De rede de seguranca, o rodape de cada bloco: "Base Prev. R$ 2.558,79 / Vlr
Prev. R$ 358,23" e a propria folha dizendo as colunas 05 e 06. Quando nenhuma
verba e reconhecida como previdencia mas o rodape declara base, a verba e
criada a partir dele -- assim um municipio que batize a verba de outro jeito
ainda sai certo, em vez de sair zerado em silencio.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from ..folha import Competencia, Folha, Segurado, Verba, numero
from ..leitor_pdf import Coluna, Linha, Palavra, distribuir, localizar_colunas

NOME = "Betha"

# --- cabecalho da folha ------------------------------------------------- #
RE_COMPETENCIA = re.compile(r"^Compet.ncia:\s*(\d{1,2})\s*/\s*(\d{4})",
                            re.IGNORECASE)
RE_ENTIDADE = re.compile(r"^(.*\b(?:CAMARA|C.MARA|PREFEITURA)\b.*)$",
                         re.IGNORECASE)

# --- bloco do servidor -------------------------------------------------- #
# "Func.: 9999 - FULANA DE TAL DA SILVA SANTOS CPF: 123.456.789-09"
RE_FUNCIONARIO = re.compile(
    r"^Func\.:\s*(\d+)\s*[-\u2013]\s*(.+?)\s+CPF:\s*([\d.\-]+)\s*$",
    re.IGNORECASE)
# "Classe: CARGO EFETIVO Cargo: VIGIA Admissão: 01/01/2005"
RE_CARGO = re.compile(r"Cargo:\s*(.+?)\s+Admiss.o:\s*(\d{2}/\d{2}/\d{4})",
                      re.IGNORECASE)
RE_CLASSE = re.compile(r"^Classe:\s*(.+?)\s+Cargo:", re.IGNORECASE)
# "Lotação: 2.01.002.13 - SETOR ADMIN Local Trab.: ..."
# A lotacao e o SETOR, e nao a fonte pagadora -- "SETOR ADMIN" e divisao
# interna da camara, nao fonte do SISPREVWEB. Vai para unidade, que e o que
# ajuda a achar a fonte no catalogo; quem define a fonte desta folha e a
# escolha unica feita na tela (ver `extracao._fonte_da_folha_inteira`).
RE_LOTACAO = re.compile(
    r"^Lota..o:\s*([\d.]+)\s*[-\u2013]\s*(.+?)(?:\s+Local\s+Trab|$)",
    re.IGNORECASE)
RE_TIPO_FOLHA = re.compile(r"Tipo\s+Folha:\s*(\w+)", re.IGNORECASE)

# --- a tabela de verbas ------------------------------------------------- #
RE_CABECALHO_VERBA = re.compile(r"^Cod\.\s+Descri..o\s+Ref\.", re.IGNORECASE)
RE_FIM_DO_BLOCO = re.compile(r"^Proventos:\s*R\$", re.IGNORECASE)
ROTULOS_VERBA = (
    ("cod", "Cod."),
    ("descricao", "Descrição"),
    ("referencia", "Ref."),
    ("valor", "Valor"),
    ("base", "Base"),
)
# PROVENTOS acaba em 291 e DESCONTOS comeca em 303. Cortar no meio separa os
# dois lados sem depender de qual verba e qual.
MEIO_DA_LINHA = 297.0

# --- rodape do bloco ---------------------------------------------------- #
RE_RODAPE = re.compile(r"^Base\s+Prev\.\s+Vlr\s+Prev\.", re.IGNORECASE)
ROTULOS_RODAPE = (
    ("base_prev", "Base"),
    ("vlr_prev", "Vlr"),
)


# ----------------------------------------------------------------------- #
def pontuar(linhas: Sequence[tuple]) -> int:
    """Quantos blocos DESTE formato o PDF tem.

    Conta o rodape, e nao o "Func.:": e a dupla "Base Prev. Vlr Prev." que e
    assinatura deste gerador.
    """
    return sum(1 for linha, _p in linhas if RE_RODAPE.match(linha.texto.strip()))


def ler(linhas: Sequence[tuple], folha: Folha) -> List[Segurado]:
    """Preenche o cabecalho da folha e devolve os segurados."""
    _ler_cabecalho_da_folha(linhas, folha)
    return _ler_segurados(linhas)


# ----------------------------------------------------------------------- #
def _ler_cabecalho_da_folha(linhas: Sequence[tuple], folha: Folha) -> None:
    for linha, _pagina in linhas[:20]:
        texto = linha.texto.strip()

        if folha.competencia is None:
            achado = RE_COMPETENCIA.match(texto)
            if achado:
                folha.competencia = Competencia(ano=int(achado.group(2)),
                                                mes=int(achado.group(1)))
                continue

        if not folha.entidade:
            achado = RE_ENTIDADE.match(texto)
            if achado:
                folha.entidade = achado.group(1).strip()
                continue

        if not folha.tipo:
            achado = RE_TIPO_FOLHA.search(texto)
            if achado:
                folha.tipo = achado.group(1).strip().title()


def _ler_segurados(linhas: Sequence[tuple]) -> List[Segurado]:
    """Percorre as linhas abrindo um servidor a cada "Func.:"."""
    segurados: List[Segurado] = []
    atual: Optional[Segurado] = None
    esquerda: Dict[str, Coluna] = {}
    direita: Dict[str, Coluna] = {}
    colunas_rodape: Dict[str, Coluna] = {}
    esperando_rodape = False

    for linha, pagina in linhas:
        texto = linha.texto.strip()

        achado = RE_FUNCIONARIO.match(texto)
        if achado:
            atual = Segurado(matricula=achado.group(1),
                             nome=achado.group(2).strip(),
                             cpf=achado.group(3).strip(),
                             pagina=pagina)
            segurados.append(atual)
            esquerda = direita = {}
            continue

        if RE_RODAPE.match(texto):
            colunas_rodape = localizar_colunas(linha, ROTULOS_RODAPE,
                                               pela_direita=("base_prev",
                                                             "vlr_prev"))
            esperando_rodape = True
            continue

        if esperando_rodape:
            esperando_rodape = False
            if atual is not None:
                _conferir_previdencia(atual, distribuir(linha, colunas_rodape))
                atual = None
            continue

        if atual is None:
            continue

        achado = RE_CARGO.search(texto)
        if achado:
            atual.cargo = achado.group(1).strip()
            atual.admissao = achado.group(2)
            classe = RE_CLASSE.match(texto)
            if classe:
                atual.regime = classe.group(1).strip()
            continue

        achado = RE_LOTACAO.match(texto)
        if achado:
            atual.estrutura = achado.group(1).strip()
            atual.unidade = achado.group(2).strip()
            continue

        if RE_CABECALHO_VERBA.match(texto):
            esquerda, direita = _colunas_dos_dois_lados(linha)
            continue

        # "Proventos: R$ 3.398,49 Descontos: ..." fecha a tabela de verbas; o
        # bloco so termina mesmo na linha de valores do rodape.
        if RE_FIM_DO_BLOCO.match(texto):
            esquerda = direita = {}
            continue

        if esquerda or direita:
            atual.verbas.extend(_ler_verbas(linha, esquerda, direita))

    return segurados


def _colunas_dos_dois_lados(cabecalho: Linha) -> tuple:
    """Os rotulos aparecem DUAS vezes na mesma linha, um jogo por lado."""
    esquerdas = [p for p in cabecalho.palavras if p.x0 < MEIO_DA_LINHA]
    direitas = [p for p in cabecalho.palavras if p.x0 >= MEIO_DA_LINHA]
    return (localizar_colunas(_recortar(cabecalho, esquerdas), ROTULOS_VERBA),
            localizar_colunas(_recortar(cabecalho, direitas), ROTULOS_VERBA))


def _recortar(linha: Linha, palavras: Sequence[Palavra]) -> Linha:
    """Uma linha com so estas palavras, para ler metade de cada vez."""
    recorte = Linha(y=linha.y)
    recorte.palavras = list(palavras)
    return recorte


def _ler_verbas(linha: Linha, esquerda: Dict[str, Coluna],
                direita: Dict[str, Coluna]) -> List[Verba]:
    """Ate duas verbas: o provento da esquerda e o desconto da direita."""
    verbas = []
    for colunas, tipo, metade in (
            (esquerda, "P", [p for p in linha.palavras if p.x0 < MEIO_DA_LINHA]),
            (direita, "D", [p for p in linha.palavras if p.x0 >= MEIO_DA_LINHA])):
        if not colunas or not metade:
            continue
        verba = _montar_verba(distribuir(_recortar(linha, metade), colunas),
                              tipo)
        if verba is not None:
            verbas.append(verba)
    return verbas


def _montar_verba(campos: Dict[str, str], tipo: str) -> Optional[Verba]:
    """O que faz uma linha ser verba e ter CODIGO de digitos e um VALOR."""
    # O codigo fica a TRES pontos da descricao -- menos que o vao que divide
    # celulas --, entao os dois sempre chegam juntos, em "1 PROVENTOS". E a
    # celula emendada cai ora na coluna do codigo, ora na da descricao,
    # conforme onde fique o centro dela: "1 PROVENTOS" comeca em 43 e vai para
    # a descricao, "11 ADICIONAL NOTURNO 25%" comeca em 38 e vai para o
    # codigo. Por isso as duas sao juntadas de volta e separadas aqui, onde o
    # criterio e o texto e nao a geometria: o primeiro pedaco e o codigo.
    cabeca = " ".join(p for p in (campos.get("cod", "").strip(),
                                  campos.get("descricao", "").strip()) if p)
    codigo, _, descricao = cabeca.partition(" ")

    valor = numero(campos.get("valor", ""))
    if not codigo.isdigit() or valor is None:
        return None
    return Verba(
        codigo=codigo,
        descricao=descricao.strip(),
        tipo=tipo,
        referencia=_referencia(campos.get("referencia", "")),
        base=numero(campos.get("base", "")),
        valor=valor,
    )


def _referencia(texto: str) -> Optional[float]:
    """"14.00 %", "30 Dia(s)", "25.00 %": o quanto, com ponto decimal."""
    achado = re.match(r"^\s*(\d+(?:\.\d+)?)", texto or "")
    return float(achado.group(1)) if achado else None


def _conferir_previdencia(segurado: Segurado, rodape: Dict[str, str]) -> None:
    """A rede de seguranca: o rodape declara a base e o valor da previdencia.

    Quando as verbas ja trouxeram a previdencia -- o caso normal --, nao se
    mexe em nada: os numeros sao os mesmos e a verba traz o codigo, que a tela
    mostra para conferencia. Quando NENHUMA verba foi reconhecida como
    previdencia e mesmo assim a folha declara base, a verba e criada aqui.

    Isso existe porque o reconhecimento e pela descricao, e a descricao muda
    de municipio para municipio: aqui a verba se chama "FUNPREV". Se amanha
    chamar "RPPS SERVIDOR", o arquivo sai certo por este caminho em vez de
    sair zerado sem ninguem notar.
    """
    if segurado.verbas_previdencia:
        return
    base = numero(rodape.get("base_prev", ""))
    valor = numero(rodape.get("vlr_prev", ""))
    if not base or not valor:
        return
    segurado.verbas.append(Verba(
        codigo="",
        descricao="PREVIDENCIA (do rodapé da folha)",
        tipo="D", base=base, valor=valor,
    ))
