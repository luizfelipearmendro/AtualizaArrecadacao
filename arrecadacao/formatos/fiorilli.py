# -*- coding: utf-8 -*-
"""A folha analitica do Fiorilli -- Primavera do Leste, Colniza e Comodoro.

Os tres municipios usam o mesmo gerador, com diferencas pequenas que mordem:
Colniza abre o rodape do bloco com uma coluna a mais ("Salario Base"), chama a
previdencia de "PREV COLNIZA" e, na camara, poe a folha de ferias no mesmo PDF
da mensal. Comodoro imprime a matricula sem o vinculo ("003273") e solta a
letra da aliquota das ferias ("14.00 M"). Cada uma dessas esta tratada onde
acontece, com o caso que a motivou.

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
#
# Em Comodoro nao ha tracinho: "003273 FULANA DE TAL SILVA 07/03/2012 0058 -
# SECRETARIO ...". So que "numero seguido de texto" tambem casa com o cargo que
# quebrou de linha ("0170 - GERENTE DE LICITACOES ..."), e o cargo viraria
# servidor. Por isso a matricula sem vinculo so vale com a data de admissao
# na mesma linha -- e, entre as duas, nome comecando por letra ou nada: o nome
# comprido tambem quebra e sobe ("FULANA DE TAL DO NASCIMENTO SILVA" numa
# linha, "001678 01/02/2007 0253 - COORDENADOR ..." na de baixo).
RE_SERVIDOR = re.compile(
    r"^(\d+-\d+)\s+(\S.*)$"
    r"|^(\d{4,})\s+((?:[^\W\d_].*)?\b\d{2}/\d{2}/\d{4}\b.*)$")
# O pedaco que subiu, ou o que sobrou embaixo ("SANTANA"): so letras. Os
# rotulos do cabecalho do bloco tambem sao so letras, e ficam de fora.
RE_TEXTO_SOLTO = re.compile(r"^[^\W\d_][^\d]*$")
RE_ROTULO_DO_BLOCO = re.compile(
    r"^(Matr.cula|Nome do Trabalhador|Admiss.o|Cargo)\b", re.IGNORECASE)
RE_ADMISSAO = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
RE_CARGO = re.compile(r"(\d{3,4}\s*[-\u2013]\s*\D.*)$")
# Cargo comprido demais para a linha: o gerador o sobe meia linha e ele sai
# ANTES da matricula, sozinho -- "0170 - GERENTE DE LICITACOES DE CONTRATOS E",
# com o "CONVENIOS" do fim vindo depois, perdido. Guarda-se a primeira parte.
RE_CARGO_SOLTO = re.compile(r"^\d{3,4}\s*[-\u2013]\s*[^\W\d_].*$")

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
# Colniza poe uma coluna a mais na frente: "Salario Base Base FGTS ...". Sem
# ela nos rotulos, o "Base" de "Salario Base" seria tomado pela Base FGTS e
# cada coluna escorregaria uma casa -- a base previdenciaria lida seria a do
# FGTS. O segundo rotulo so existe para consumir esse "Base".
ROTULOS_RODAPE_COM_SALARIO = (
    ("salario", "Salario"),
    ("salario_base", "Base"),
) + ROTULOS_RODAPE
# Todos os numeros do rodape sao colados a direita, embaixo do rotulo.
RODAPE_PELA_DIREITA = tuple(chave for chave, _ in ROTULOS_RODAPE_COM_SALARIO)
RE_RODAPE = re.compile(
    r"^(Sal.rio\s+Base\s+)?Base\s+FGTS\s+Valor\s+FGTS\s+Base\s+Prev",
    re.IGNORECASE)
# "Total Unidade: 11", "Total Subdivisao: 11", "Total Divisao: 16", "Total
# Geral: 655". O rodape que vem depois e a SOMA do grupo, e nao pode fechar
# servidor nenhum: foi assim que, em Colniza, o ultimo servidor de cada unidade
# saia com a base da unidade inteira -- 31.892,91 no lugar de 2.295,91.
RE_TOTAL = re.compile(r"^Total\s+\S+.*:\s*\d+\s*$", re.IGNORECASE)

# A folha de ferias que vem no mesmo PDF da mensal -- ver `_absorver_ferias`.
RE_FERIAS = re.compile(r"F.RIAS", re.IGNORECASE)

RE_CODIGO_DA_VERBA = re.compile(r"^\d{3}$")
RE_DINHEIRO = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d\d$")
# "30.00D", "14.00", "25,00", "20%": o quanto, logo antes do valor.
RE_REFERENCIA = re.compile(r"^[\d.,]+[A-Za-z%]?$")
# Em Comodoro a letra da referencia as vezes sai separada do numero: "947
# PREVIDENCIA FERIAS - FUNDO 14.00 M 447,45". Sem juntar os dois, o "M" seria
# tomado pela referencia, nao casaria, e os 14% iriam parar na descricao.
RE_NUMERO_DA_REFERENCIA = re.compile(r"^[\d.,]+$")
RE_LETRA_SOLTA = re.compile(r"^[A-Za-z]$")


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
    declaradas: Dict[int, Optional[float]] = {}
    atual: Optional[Segurado] = None
    fonte_corrente: Optional[FonteDaFolha] = None
    tipo_corrente = ""
    cargo_solto = ""
    nome_solto = ""
    # O resto do nome que quebrou vem logo abaixo da matricula, sozinho.
    falta_resto_do_nome = False
    colunas_rodape: Dict[str, Coluna] = {}
    # Quantas linhas ainda podem trazer os numeros do rodape aberto.
    linhas_de_rodape = 0

    for linha, pagina in linhas:
        texto = linha.texto.strip()

        # Repetido no topo de toda pagina; muda quando o PDF passa para outra
        # folha -- na camara de Colniza, da "Folha Mensal" para "Ferias".
        achado = RE_TIPO.search(texto)
        if achado:
            tipo_corrente = achado.group(1).strip().title()
            continue

        achado = RE_DIVISAO.match(texto)
        if achado:
            fonte_corrente = FonteDaFolha(numero=int(achado.group(1)),
                                          nome=achado.group(2).strip(),
                                          bruto=texto)
            continue

        if RE_TOTAL.match(texto):
            atual = None
            continue

        achado = RE_RODAPE.match(texto)
        if achado:
            rotulos = ROTULOS_RODAPE_COM_SALARIO if achado.group(1) else ROTULOS_RODAPE
            colunas_rodape = localizar_colunas(linha, rotulos,
                                               pela_direita=RODAPE_PELA_DIREITA)
            linhas_de_rodape = 2
            continue

        # A linha de numeros logo depois dos rotulos fecha o bloco: e la que
        # esta a base previdenciaria que a folha declara.
        #
        # Em Colniza os numeros do rodape nem sempre saem numa linha so: o
        # "Salario Base" as vezes fica meio ponto mais baixo e vira uma linha
        # propria, antes ou depois das outras sete. Se a linha que chegou nao
        # tem a Base Prev, o rodape continua aberto ate a proxima.
        if linhas_de_rodape:
            linhas_de_rodape -= 1
            rodape = distribuir(linha, colunas_rodape)
            if not rodape.get("base_prev") and linhas_de_rodape:
                continue
            linhas_de_rodape = 0
            if atual is not None:
                declaradas[id(atual)] = _aplicar_base(atual, rodape)
                atual = None
            continue

        achado = RE_SERVIDOR.match(texto)
        if achado:
            atual = _abrir_servidor(achado, pagina, fonte_corrente)
            atual.tipo_folha = tipo_corrente
            if not atual.cargo:
                atual.cargo = cargo_solto
            falta_resto_do_nome = not atual.nome and bool(nome_solto)
            if not atual.nome:
                atual.nome = nome_solto
            cargo_solto = nome_solto = ""
            segurados.append(atual)
            continue

        if atual is None and RE_CARGO_SOLTO.match(texto):
            cargo_solto = texto
            continue

        if RE_TEXTO_SOLTO.match(texto) and not RE_ROTULO_DO_BLOCO.match(texto):
            if atual is None:
                nome_solto = texto
                continue
            if falta_resto_do_nome:
                atual.nome = "{} {}".format(atual.nome, texto)
                falta_resto_do_nome = False
                continue
        falta_resto_do_nome = False

        if atual is not None:
            atual.verbas.extend(_ler_verbas(linha))

    return _absorver_ferias(segurados, declaradas)


def _absorver_ferias(segurados: List[Segurado],
                     declaradas: Dict[int, Optional[float]]) -> List[Segurado]:
    """Tira a folha de ferias que a mensal ja traz por dentro.

    A camara de Colniza manda as duas no mesmo PDF. Quem saiu de ferias aparece
    na "Folha Mensal" com TUDO -- salario, ferias, "947 PREV COLNIZA - FERIAS"
    e o "927 LIQUIDO FERIAS" descontado -- e de novo na folha de "Ferias",
    so com a parte das ferias. Somar os dois blocos cobraria a contribuicao das
    ferias duas vezes; o SISPREVWEB recusaria a linha repetida, e ainda bem.

    O bloco de ferias, porem, tem uma coisa que o mensal nao tem: a base das
    ferias impressa, sozinha. O mensal so imprime a do salario, e com duas
    previdencias no bloco nao daria para saber de quem e cada base. Entao a
    base das ferias passa para a verba gemea no mensal, a do mensal fica com a
    outra previdencia, e o bloco de ferias sai da lista.

    Se o mensal NAO tiver a verba gemea, nada e mexido: os dois blocos ficam,
    e o aviso de matricula repetida mostra o caso para alguem olhar.
    """
    mensais = {s.matricula: s for s in segurados
               if s.matricula and not RE_FERIAS.search(s.tipo_folha)}
    absorvidos = set()

    for ferias in segurados:
        if not RE_FERIAS.search(ferias.tipo_folha):
            continue
        mensal = mensais.get(ferias.matricula)
        das_ferias = ferias.verbas_previdencia
        base_ferias = declaradas.get(id(ferias))
        if mensal is None or len(das_ferias) != 1 or not base_ferias:
            continue
        gemea = next((v for v in mensal.verbas_previdencia
                      if v.codigo == das_ferias[0].codigo
                      and v.valor == das_ferias[0].valor), None)
        if gemea is None:
            continue

        gemea.base = base_ferias
        outras = [v for v in mensal.verbas_previdencia if v is not gemea]
        base_mensal = declaradas.get(id(mensal))
        if len(outras) == 1 and base_mensal:
            outras[0].base = base_mensal
        absorvidos.add(id(ferias))

    return [s for s in segurados if id(s) not in absorvidos]


def _abrir_servidor(achado, pagina: int,
                    fonte: Optional[FonteDaFolha]) -> Segurado:
    """Matricula, nome, admissao e cargo da linha de abertura do bloco."""
    matricula = achado.group(1) or achado.group(3)
    resto = (achado.group(2) or achado.group(4)).strip()

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
        matricula=matricula,
        nome=resto,
        admissao=admissao,
        cargo=cargo,
        fonte=fonte,
        estrutura=fonte.chave if fonte else "",
        unidade=fonte.nome if fonte else "",
        pagina=pagina,
    )


def _aplicar_base(segurado: Segurado, rodape: Dict[str, str]) -> Optional[float]:
    """Poe na verba de previdencia a base que a folha imprime, e a devolve.

    Preferir a base declarada a deduzi-la da aliquota nao e preciosismo: os
    dois caminhos divergem em centavos por servidor, e e a folha que manda.
    Quando o bloco traz mais de uma previdencia -- quem entrou em beneficio no
    meio do mes --, nao da para saber quanto da base e de cada uma, e ai cada
    verba fica com a sua, deduzida da propria aliquota.

    Em Colniza a deducao seria errada de verdade, e nao em centavos: "842 PREV
    COLNIZA UNICA 1.00 1.186,57" tem referencia 1, e dela sairia uma base de
    118.657,00. Ali so ha uma previdencia por bloco, e a declarada prevalece.

    Em Comodoro quem tirou ferias tem duas -- "942 PREVIDENCIA - FUNDO" e "947
    PREVIDENCIA FERIAS - FUNDO" -- e a Base Prev. impressa e a SOMA das duas:
    197,91 e 447,45 a 14% dao 1.413,64 + 3.196,07 = 4.609,71, e a folha diz
    4.609,73. A deducao erra porque o desconto foi arredondado ao centavo: meio
    centavo de desconto a 14% sao 3,6 centavos de base, por verba -- em
    Comodoro chegam a aparecer 4 centavos de diferenca num servidor so.
    Quando a soma deduzida cabe nesse erro de arredondamento, a sobra vai para
    a maior base e o servidor fecha com o numero da folha. Mais longe que isso
    a declarada nao e a soma (o mensal da camara de Colniza so imprime a base
    do salario, e a diferenca la e a base das ferias inteira), e as deduzidas
    ficam como estao.
    """
    previdencias = segurado.verbas_previdencia
    declarada = numero(rodape.get("base_prev", ""))

    if len(previdencias) == 1 and declarada:
        previdencias[0].base = declarada
        return declarada

    for verba in previdencias:
        if verba.base is None and verba.referencia and verba.valor:
            verba.base = round(verba.valor * 100 / verba.referencia, 2)

    if declarada and len(previdencias) > 1 and all(
            v.base is not None and v.referencia for v in previdencias):
        sobra = round(declarada - sum(v.base for v in previdencias), 2)
        # Meio centavo de desconto vira 0,5/aliquota de base, mais o centavo
        # do proprio arredondamento da base.
        erro_possivel = sum(0.5 / v.referencia + 0.01 for v in previdencias)
        if abs(sobra) <= erro_possivel + 1e-9:
            maior = max(previdencias, key=lambda v: v.base)
            maior.base = round(maior.base + sobra, 2)
    return declarada


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

    if (len(corpo) >= 2 and RE_LETRA_SOLTA.match(corpo[-1])
            and RE_NUMERO_DA_REFERENCIA.match(corpo[-2])):
        corpo = corpo[:-2] + [corpo[-2] + corpo[-1]]

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
