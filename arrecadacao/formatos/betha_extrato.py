# -*- coding: utf-8 -*-
"""O "Relatorio de Extrato Mensal da Folha" do Betha -- Vila Bela.

Mesmo fabricante da folha da camara de Sao Jose do Povo, e nenhuma linha em
comum com ela: la o bloco abre com "Func.: 9999 - FULANA ... CPF:", aqui com
uma tabela de cabecalho

    Codigo Funcionario C.P.F. Admissao Categoria Sal. Contrat Base Prev ...
    2 FULANA DE TAL SANTOS 12345678909 15/03/2001 Mensalista 2.923,90 ...

Por isso e um leitor proprio, e nao um remendo no outro.

O que manda no jeito de ler:

1. A Base Prev vem IMPRESSA na abertura do bloco -- a coluna 05 dita pela
   folha, como no Fiorilli. Nao e preciso deduzi-la da aliquota.

2. Proventos a esquerda, descontos a direita, duas verbas por linha visual. A
   divisa e limpa: o tipo do provento ("P", "(+)") acaba antes de x=297 e o
   codigo do desconto comeca em x=322. Cada verba TERMINA no tipo: "P", "D",
   ou "(+)" / "(-)" -- estes dois sao eventos informativos, que a propria folha
   avisa que ficam fora dos totais ("OBS: Os eventos com o tipo (+) e (-) nao
   sao considerados para a soma..."). Entram como tipo "I".

3. Do lado dos proventos o codigo sai COLADO na descricao, numa palavra so:
   "1HORAS NORMAIS", "388GRAT. 50% CARGO". Pelo texto nao da para separar
   sempre: "771/3 DAS FERIAS" e o codigo 77 com "1/3 DAS FERIAS", e nao o 771.
   Quem resolve e a geometria -- ver `_separar_codigo`.

4. Um PDF traz os processamentos Mensal, Ferias e Complementar juntos,
   ordenados por matricula, e o mesmo servidor aparece em mais de um bloco: o
   mensal com o salario e a previdencia, e outro so com as diarias informativas
   ou com o 1/3 de ferias pago a parte. Os blocos da mesma matricula viram UM
   segurado -- ver `_juntar_blocos`. O "Folha: Mensal - Integral" do topo da
   pagina nao serve para separar: ele muda pagina a pagina e nao diz a qual
   bloco se refere.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from ..folha import Competencia, Folha, Segurado, Verba, numero
from ..fontes import FonteDaFolha
from ..leitor_pdf import Linha, Palavra

NOME = "Betha (extrato mensal)"

# --- cabecalho da folha ------------------------------------------------- #
# "PREFEITURA MUN. VILA BELA DA SANTISSIMA TRINDADE", "CAMARA MUNICIPAL VILA
# BELA DA SANTISSIMA TRINDADE".
RE_ENTIDADE = re.compile(r"^((?:PREFEITURA|C.MARA)\b.+)$", re.IGNORECASE)
RE_COMPETENCIA = re.compile(r"^M.s\s*/\s*Ano:\s*(\d{1,2})/(\d{4})\b",
                            re.IGNORECASE)
# "Folha: Mensal - Integral" -- vale para a folha, nao para o bloco (ver 4).
RE_TIPO = re.compile(r"^Folha:\s*(\S+)", re.IGNORECASE)

# --- abertura do bloco -------------------------------------------------- #
RE_CABECALHO_DO_BLOCO = re.compile(r"^C.digo\s+Funcion.rio\s+C\.P\.F\.",
                                   re.IGNORECASE)
# "2 FULANA DE TAL SANTOS 12345678909 15/03/2001 Mensalista 2.923,90
# 2.923,90 2.901,48 0,00 200,00". Lido do FIM para o comeco: CPF de onze
# digitos, data, categoria, e os cinco numeros -- salario contratual, base
# previdenciaria, base do IR, FGTS e horas no mes. A base do IR pode sair
# negativa ("-783,79"). Na camara a matricula leva o contrato: "141/1".
RE_FUNCIONARIO = re.compile(
    r"^(\d+(?:/\d+)?)\s+(.+?)\s+(\d{11})\s+(\d{2}/\d{2}/\d{4})\s+(.+?)"
    r"\s+(-?[\d.,]+)\s+(-?[\d.,]+)\s+(-?[\d.,]+)\s+(-?[\d.,]+)\s+(-?[\d.,]+)$")
# "Cargo: OUVIDOR Estrutura Organizacional CAMARA MUNICIPAL DE Nivel /
# Classe / Referencia: ..."
RE_CARGO = re.compile(
    r"^Cargo:\s*(.*?)\s*Estrutura\s+Organizacional\s+(.*?)\s*"
    r"(?:N.vel\s*/\s*Classe.*)?$", re.IGNORECASE)

# --- verbas ------------------------------------------------------------- #
MEIO_DA_LINHA = 310.0
TIPOS = {"P": "P", "D": "D", "(+)": "I", "(-)": "I"}
RE_DINHEIRO = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d\d$")
RE_DIGITOS_NA_FRENTE = re.compile(r"^(\d+)(.*)$")
# Onde acaba o codigo colado, e quanto ocupa um digito, no corpo 8 desta
# folha: "1SALARIO" comeca em 52, "75HORAS" em 47, "388GRAT." em 43 -- o
# codigo e alinhado a direita em 56,5 e cada digito tem 4,45 de largura.
FIM_DO_CODIGO = 56.5
LARGURA_DO_DIGITO = 4.45


# ----------------------------------------------------------------------- #
def pontuar(linhas: Sequence[tuple]) -> int:
    """Quantos blocos DESTE relatorio o PDF tem: as linhas de cabecalho."""
    return sum(1 for linha, _p in linhas
               if RE_CABECALHO_DO_BLOCO.match(linha.texto.strip()))


def ler(linhas: Sequence[tuple], folha: Folha) -> List[Segurado]:
    """Preenche o cabecalho da folha e devolve os segurados."""
    _ler_cabecalho_da_folha(linhas, folha)
    return _juntar_blocos(_ler_blocos(linhas))


# ----------------------------------------------------------------------- #
def _ler_cabecalho_da_folha(linhas: Sequence[tuple], folha: Folha) -> None:
    for linha, _pagina in linhas[:20]:
        texto = linha.texto.strip()
        if not folha.entidade:
            achado = RE_ENTIDADE.match(texto)
            if achado:
                folha.entidade = achado.group(1).strip()
                continue
        if folha.competencia is None:
            achado = RE_COMPETENCIA.match(texto)
            if achado:
                folha.competencia = Competencia(ano=int(achado.group(2)),
                                                mes=int(achado.group(1)))
                continue
        if not folha.tipo:
            achado = RE_TIPO.match(texto)
            if achado:
                folha.tipo = achado.group(1).strip().title()


class _Bloco:
    """Um bloco do PDF, antes de virar segurado."""

    def __init__(self, segurado: Segurado, base_prev: Optional[float]):
        self.segurado = segurado
        self.base_prev = base_prev


def _ler_blocos(linhas: Sequence[tuple]) -> List[_Bloco]:
    blocos: List[_Bloco] = []
    atual: Optional[_Bloco] = None
    depois_do_cabecalho = False

    for linha, pagina in linhas:
        texto = linha.texto.strip()

        if RE_CABECALHO_DO_BLOCO.match(texto):
            depois_do_cabecalho = True
            continue

        if depois_do_cabecalho:
            depois_do_cabecalho = False
            achado = RE_FUNCIONARIO.match(texto)
            if achado:
                atual = _Bloco(
                    Segurado(matricula=achado.group(1),
                             nome=achado.group(2).strip(),
                             cpf=achado.group(3),
                             admissao=achado.group(4),
                             regime=achado.group(5).strip(),
                             pagina=pagina),
                    numero(achado.group(7)))
                blocos.append(atual)
            else:
                # Cabecalho sem a linha de valores: nao ha bloco a abrir, e
                # as verbas que vierem nao podem cair no servidor anterior.
                atual = None
            continue

        if atual is None:
            continue

        achado = RE_CARGO.match(texto)
        if achado:
            _por_cargo_e_estrutura(atual.segurado, achado, texto)
            continue

        atual.segurado.verbas.extend(_ler_verbas(linha))

    for bloco in blocos:
        _aplicar_base(bloco)
    return blocos


def _por_cargo_e_estrutura(segurado: Segurado, achado, texto: str) -> None:
    """Cargo, e a estrutura organizacional -- que aqui e a fonte pagadora.

    A folha nao imprime o NUMERO da fonte, so o nome da estrutura, e cortado na
    largura da coluna: "FUNDEB 70 % EFETIVO", que no catalogo do SISPREVWEB e
    "050604-FUNDEB 70% EFETIVO". Sem numero o catalogo nao casa sozinho, entao
    cada estrutura vira um grupo a escolher na tela, no catalogo inteiro do
    municipio -- a escolha fica gravada e o mes seguinte ja vem resolvido.
    """
    segurado.cargo = achado.group(1).strip()
    estrutura = achado.group(2).strip()
    if estrutura:
        segurado.unidade = estrutura
        segurado.fonte = FonteDaFolha(numero=0, nome=estrutura,
                                      folha_inteira=True, bruto=texto)


def _aplicar_base(bloco: _Bloco) -> None:
    """Poe na verba de previdencia a base que a abertura do bloco imprime.

    Com uma previdencia so, a base declarada vai inteira para ela. Na camara,
    quem saiu de ferias tem duas -- "56 I.M.P.V.B." sobre o salario e "907
    FUNDO PREVIDENCIA PAGO EM FERIAS" -- e a Base Prev impressa e a soma:
    387,22 e 774,43 a 14% dao 2.765,86 + 5.531,64, e a folha diz 8.297,48. Cada
    uma fica com a sua, deduzida da aliquota, e a sobra do arredondamento vai
    para a maior, para o servidor fechar com o numero da folha.
    """
    previdencias = bloco.segurado.verbas_previdencia
    declarada = bloco.base_prev
    if len(previdencias) == 1 and declarada:
        previdencias[0].base = declarada
        return

    for verba in previdencias:
        if verba.base is None and verba.referencia and verba.valor:
            verba.base = round(verba.valor * 100 / verba.referencia, 2)
    if declarada and len(previdencias) > 1 and all(
            v.base is not None and v.referencia for v in previdencias):
        sobra = round(declarada - sum(v.base for v in previdencias), 2)
        # Meio centavo de desconto vira 0,5/aliquota de base, mais o centavo
        # do proprio arredondamento da base.
        if abs(sobra) <= sum(0.5 / v.referencia + 0.01 for v in previdencias):
            maior = max(previdencias, key=lambda v: v.base)
            maior.base = round(maior.base + sobra, 2)


def _juntar_blocos(blocos: Sequence[_Bloco]) -> List[Segurado]:
    """Um segurado por matricula, quando isso nao duplica previdencia.

    O que se ve neste PDF: o bloco mensal com salario e "56 PREVILA", e ao lado
    dele um de base ZERO e sem previdencia -- "166 DIARIAS (+)" ou "77 1/3 DAS
    FERIAS". Juntar e o certo: o arquivo do SISPREVWEB quer uma linha por
    servidor, e as verbas do segundo bloco foram pagas no mesmo mes.

    Se DOIS blocos da mesma matricula tiverem previdencia, nada e juntado: nao
    da para saber se e uma folha complementar legitima ou a mesma contribuicao
    impressa duas vezes, e somar as cegas seria o pior dos erros. Os blocos
    ficam separados e o aviso de matricula repetida mostra o caso na tela.
    """
    por_matricula: Dict[str, List[_Bloco]] = {}
    for bloco in blocos:
        por_matricula.setdefault(bloco.segurado.matricula, []).append(bloco)

    segurados: List[Segurado] = []
    for bloco in blocos:
        grupo = por_matricula[bloco.segurado.matricula]
        if len(grupo) == 1:
            segurados.append(bloco.segurado)
            continue
        com_previdencia = [b for b in grupo if b.segurado.verbas_previdencia]
        if len(com_previdencia) > 1:
            segurados.append(bloco.segurado)
            continue
        if bloco is not grupo[0]:
            continue
        principal = (com_previdencia or grupo)[0].segurado
        for outro in grupo:
            if outro.segurado is not principal:
                principal.verbas.extend(outro.segurado.verbas)
        segurados.append(principal)
    return segurados


# ----------------------------------------------------------------------- #
def _ler_verbas(linha: Linha) -> List[Verba]:
    """Ate duas verbas: o provento da esquerda e o desconto da direita."""
    verbas = []
    for lado in ([p for p in linha.palavras if p.x0 < MEIO_DA_LINHA],
                 [p for p in linha.palavras if p.x0 >= MEIO_DA_LINHA]):
        verba = _montar_verba(lado)
        if verba is not None:
            verbas.append(verba)
    return verbas


def _montar_verba(palavras: Sequence[Palavra]) -> Optional[Verba]:
    """"codigo descricao referencia valor tipo" -- ou nada, se nao for verba.

    E' verba o que termina no tipo com um valor em dinheiro logo antes. Isso
    deixa de fora "Total Proventos: 3.508,68", que divide a linha com um
    desconto, e a quebra de linha de uma descricao comprida.
    """
    if len(palavras) < 4 or palavras[-1].texto not in TIPOS:
        return None
    if not RE_DINHEIRO.match(palavras[-2].texto):
        return None

    tipo = TIPOS[palavras[-1].texto]
    valor = numero(palavras[-2].texto)
    referencia = numero(palavras[-3].texto)
    corpo = list(palavras[:-3]) if referencia is not None else list(palavras[:-2])
    if not corpo:
        return None

    codigo, primeira = _separar_codigo(corpo[0])
    if not codigo:
        return None
    descricao = " ".join(([primeira] if primeira else [])
                         + [p.texto for p in corpo[1:]])
    return Verba(codigo=codigo, descricao=descricao.strip(), tipo=tipo,
                 referencia=referencia, base=None, valor=valor)


def _separar_codigo(palavra: Palavra) -> tuple:
    """("77", "1/3") de "771/3": o codigo e o resto da primeira palavra.

    Do lado dos descontos o codigo e uma palavra sozinha ("56 PREVILA"). Do
    lado dos proventos vem colado, e quantos dos digitos da frente sao codigo
    se le pela POSICAO: o codigo e alinhado a direita, entao quanto mais longe
    da margem a palavra comeca, menos digitos ele tem. "771/3" comeca em 47,
    a mesma posicao de "75HORAS" -- dois digitos, codigo 77.

    Se a conta der um numero de digitos impossivel (folha com outra fonte ou
    outra margem), fica a leitura pelo texto: todos os digitos da frente.
    """
    achado = RE_DIGITOS_NA_FRENTE.match(palavra.texto)
    if not achado:
        return "", palavra.texto
    digitos, resto = achado.group(1), achado.group(2)
    if not resto:
        return digitos, ""
    quantos = round((FIM_DO_CODIGO - palavra.x0) / LARGURA_DO_DIGITO)
    if 1 <= quantos < len(digitos):
        return digitos[:quantos], digitos[quantos:] + resto
    return digitos, resto
