# -*- coding: utf-8 -*-
r"""Folha do gerador ARFolha -- a de Rosario Oeste e das que usam o mesmo.

Outro sistema de folha, outro PDF: nao ha uma linha em comum com o do Agili.
O bloco de um servidor e assim:

    SUBFOLHA: 1 - MEDIA E ALTA COMPLEXIDADE- MAC (RECURSO PROPRIO)  <- a fonte
    SERVIDOR: 9999.1 - FULANA DE TAL DA SILVA SANTOS  CPF: 123...  30/03/2007
    Base Previdencia: 4.926,11   Base INSS: 0,00   Base IR: 7.350,97
    COD DESCRICAO  N Parc  REFERENCIA  BASE  QTD  PROVENTO  DESCONTO
    1     SALARIO BASE        Fixo  AUTOMATICO  4.926,1100  30,00  4.926,11
    7000  FUNDO PREVIDENCIA   Fixo  AUTOMATICO  4.926,1100  14,00      689,65
    TOTAL PROVENTOS: 8.340,62  TOTAL DESCONTOS: ...   <- FECHA o bloco

Tres coisas merecem atencao:

**O bloco fecha sozinho.** "TOTAL PROVENTOS:" encerra cada servidor, e fechar
ali e obrigatorio: no fim de cada subfolha vem um quadro de TOTAIS cuja linha
"5  44.958,91  18.458,86  26.500,05" passaria por verba de codigo 5 e entraria
no ultimo servidor do grupo.

**PROVENTO e DESCONTO so se distinguem por coordenada.** Em texto plano,
"SALARIO BASE ... 4.926,11" e "CDC BANCO DO BRASIL ... 324,27" tem a mesma
forma; o que diz que um e ganho e o outro desconto e a coluna embaixo da qual o
numero esta. Por isso as verbas saem de `distribuir`, e nao de regex.

**A fonte pagadora e a SUBFOLHA.** O numero dela e a chave do catalogo do
SISPREVWEB -- "SUBFOLHA: 11" casa com "11- SEC. SAUDE VIG SANITARIA". Aqui o
numero identifica melhor que no Agili, onde ele se repete entre fontes.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from ..folha import Competencia, Folha, Segurado, Verba, numero
from ..fontes import FonteDaFolha
from ..leitor_pdf import Coluna, Linha, distribuir, localizar_colunas

NOME = "ARFolha"

# --- cabecalho da tabela de verbas ------------------------------------- #
ROTULOS_VERBA = (
    ("cod", "COD"),
    ("descricao", "DESCRIÇÃO"),
    ("parcela", "Nº"),
    ("referencia", "REFERÊNCIA"),
    ("base", "BASE"),
    ("qtd", "QTD"),
    ("provento", "PROVENTO"),
    ("desconto", "DESCONTO"),
)
# So PROVENTO e DESCONTO alinham a direita. BASE e QTD, apesar de numericas,
# sao coladas a ESQUERDA nesta folha -- e marca-las como de direita custou 45
# servidores: "13.774,3900" e mais largo que "4.926,1100", e com o criterio
# errado o valor largo escorregava para a coluna vizinha. O servidor saia com
# contribuicao certa e base ZERO, que e o tipo de erro que passa na conferencia
# por amostragem.
VERBAS_PELA_DIREITA = ("provento", "desconto")
# O que as colunas vizinhas deixam colado no fim da descricao comprida: a
# "992 PREVIDENCIA FUNDO 13o SALARIO PROPORC" de Barra do Garcas termina em
# x=234 e o "14,0000" da coluna seguinte comeca em 237, e a descricao saia
# "... PROPORC 14,0000 Fixo". Numero com virgula e marca de parcela ("Fixo",
# "13/120") nao terminam nome de verba nenhum.
RE_COLADO_NA_DESCRICAO = re.compile(
    r"(?:\s+(?:\d[\d.]*,\d+|Fixo|\d+/\d+))+\s*$", re.IGNORECASE)

# "FOLHA DE PAGAMENTO - 09/2026 - 1 - NORMAL": competencia e tipo na mesma
# linha. O tipo e o que vem depois do ultimo tracinho -- NORMAL, RESCISAO,
# 13 SALARIO -- e e ele que manda a competencia virar mes 13.
RE_FOLHA = re.compile(
    r"FOLHA DE PAGAMENTO\s*[-–]\s*(\d{1,2})\s*/\s*(\d{4})\s*[-–]\s*\d+\s*[-–]\s*(.+?)\s*$",
    re.IGNORECASE)
RE_COMPETENCIA = re.compile(r"FOLHA DE PAGAMENTO\s*[-–]\s*(\d{1,2})\s*/\s*(\d{4})")
# A mesma familia de folha tambem imprime o cabecalho assim, sem a palavra
# "FOLHA DE PAGAMENTO": "TIPO DA FOLHA - NORMAL - N - 07/2026".
RE_TIPO_DA_FOLHA = re.compile(
    r"TIPO\s+DA\s+FOLHA\s*[-–]\s*(.+?)\s*[-–]\s*\S+\s*[-–]\s*"
    r"(\d{1,2})\s*/\s*(\d{4})", re.IGNORECASE)
# A entidade pode ser a prefeitura ou a camara -- e camara, aqui, nao e
# detalhe: a folha da camara costuma vir sem grupo de fonte pagadora nenhum.
# O "MUNICIPAL" e opcional: Chapada escreve "PREFEITURA DE CHAPADA DOS
# GUIMARAES MT", e exigir a palavra deixava a entidade em branco.
RE_ENTIDADE = re.compile(
    r"^((?:PREFEITURA|C.MARA)\s+(?:MUNICIPAL\s+)?DE\s+.+)$", re.IGNORECASE)
# O grupo de fonte pagadora. Rosario Oeste chama de SUBFOLHA e Barra do
# Garcas de SECRETARIA, mas os dois dizem a mesma coisa: "<numero> - <nome>".
RE_SUBFOLHA = re.compile(
    r"^(?:SUBFOLHA|SECRETARIA):\s*(\d+)\s*[-–]\s*(.+)$", re.IGNORECASE)

# --- cabecalho do bloco de servidor ------------------------------------ #
# Os rotulos NA ORDEM das colunas, como em qualquer cabecalho deste programa.
ROTULOS_SERVIDOR = (
    ("servidor", "SERVIDOR:"),
    ("cpf", "CPF:"),
    ("admissao", "Admissão:"),
    ("status", "Status:"),
)
RE_SERVIDOR = re.compile(r"^SERVIDOR:", re.IGNORECASE)
# "9999.1 - FULANA DE TAL DA SILVA SANTOS": matricula.vinculo, traco, nome.
RE_MATRICULA_NOME = re.compile(r"^(\d[\d.]*)\s*-\s*(\S.*)$")
RE_CABECALHO_VERBA = re.compile(r"^COD\b.*\bBASE\b.*\bDESCONTO\b", re.IGNORECASE)
RE_FIM_DO_BLOCO = re.compile(r"^TOTAL\s+PROVENTOS:", re.IGNORECASE)
RE_CONTRATACAO = re.compile(r"^\d+\s*-\s*CONCURSADO\b", re.IGNORECASE)


# ---------------------------------------------------------------------- #
def pontuar(linhas: Sequence[tuple]) -> int:
    """Quantos blocos de servidor DESTE formato o PDF tem."""
    return sum(1 for linha, _p in linhas
               if RE_SERVIDOR.match(linha.texto.strip()))


def ler(linhas: Sequence[tuple], folha: Folha) -> List[Segurado]:
    """Preenche o cabecalho da folha e devolve os segurados."""
    _ler_cabecalho_da_folha(linhas, folha)
    return _ler_segurados(linhas)


# ---------------------------------------------------------------------- #
def _ler_cabecalho_da_folha(linhas: Sequence[tuple], folha: Folha) -> None:
    """Competencia, tipo e entidade: estao nas primeiras linhas da pagina 1."""
    for linha, _pagina in linhas[:40]:
        texto = linha.texto.strip()

        if folha.competencia is None:
            achado = RE_FOLHA.search(texto)
            if achado:
                folha.competencia = Competencia(ano=int(achado.group(2)),
                                                mes=int(achado.group(1)))
                folha.tipo = _limpar_tipo(achado.group(3))
                continue
            achado = RE_COMPETENCIA.search(texto)
            if achado:
                folha.competencia = Competencia(ano=int(achado.group(2)),
                                                mes=int(achado.group(1)))
                continue
            achado = RE_TIPO_DA_FOLHA.search(texto)
            if achado:
                folha.competencia = Competencia(ano=int(achado.group(3)),
                                                mes=int(achado.group(2)))
                folha.tipo = _limpar_tipo(achado.group(1))
                continue

        if not folha.entidade:
            # So a primeira celula: na mesma linha, a direita, vem "Hora:
            # 09:20" -- e o nome da prefeitura nao pode levar o relogio junto.
            primeira = linha.celulas[0].texto.strip() if linha.celulas else texto
            achado = RE_ENTIDADE.match(primeira)
            if achado:
                folha.entidade = achado.group(1).strip()
                continue


def _ler_segurados(linhas: Sequence[tuple]) -> List[Segurado]:
    """Percorre as linhas abrindo um servidor a cada "SERVIDOR:"."""
    segurados: List[Segurado] = []
    atual: Optional[Segurado] = None
    colunas_verba: Dict[str, Coluna] = {}
    fonte_corrente: Optional[FonteDaFolha] = None
    # Um PDF desta familia pode empilhar varias folhas -- ver `Segurado.
    # tipo_folha`. A linha "TIPO DA FOLHA - 13 SALARIO - D - 07/2026" se
    # repete no alto de cada pagina, entao basta guardar a ultima vista.
    tipo_corrente = ""

    for indice, (linha, pagina) in enumerate(linhas):
        texto = linha.texto.strip()

        achado = RE_TIPO_DA_FOLHA.search(texto)
        if achado:
            tipo_corrente = _limpar_tipo(achado.group(1))
            continue

        achado = RE_SUBFOLHA.match(texto)
        if achado:
            fonte_corrente = FonteDaFolha(numero=int(achado.group(1)),
                                          nome=achado.group(2).strip(),
                                          bruto=texto)
            continue

        if RE_SERVIDOR.match(texto):
            atual = _abrir_servidor(linhas, indice, pagina, fonte_corrente)
            if atual is not None:
                atual.tipo_folha = tipo_corrente
                segurados.append(atual)
            colunas_verba = {}
            continue

        if atual is None:
            continue

        # Fecha o bloco ANTES de qualquer outra coisa: ver o cabecalho deste
        # modulo -- o quadro de TOTAIS que vem depois tem linha que passaria
        # por verba.
        if RE_FIM_DO_BLOCO.match(texto):
            atual = None
            colunas_verba = {}
            continue

        if RE_CABECALHO_VERBA.match(texto):
            colunas_verba = localizar_colunas(linha, ROTULOS_VERBA,
                                              pela_direita=VERBAS_PELA_DIREITA)
            continue

        if not atual.regime and RE_CONTRATACAO.match(texto):
            atual.regime = texto
            continue

        if colunas_verba:
            verba = _ler_verba(linha, colunas_verba)
            if verba is not None:
                atual.verbas.append(verba)

    return segurados


def _abrir_servidor(linhas: Sequence[tuple], indice: int, pagina: int,
                    fonte: Optional[FonteDaFolha]) -> Optional[Segurado]:
    """Le a identificacao do servidor a partir da linha de rotulos.

    Aqui os valores nem sempre estao na mesma linha visual dos rotulos: em 42
    dos 271 blocos desta folha o nome sobe ou desce uma linha, e o grupo sai
    partido em "SERVIDOR: CPF: 123.456.789-09 Admissao: 09/03/2009" de um lado
    e "9999 - FULANA DE TAL DA SILVA SANTOS" do outro. Regex sobre o texto
    plano perde esses 42 em silencio -- e silencio, aqui, e servidor que nao
    entra na arrecadacao.

    Por isso as COLUNAS mandam: a linha dos rotulos diz onde cada campo mora,
    e a vizinha e lida nas mesmas colunas. So entra como nome a vizinha que
    tenha a forma de "matricula - nome", para o rodape do bloco anterior
    ("TOTAL PROVENTOS: ...") nao ser confundido com um servidor.
    """
    rotulos = linhas[indice][0]
    colunas = localizar_colunas(rotulos, ROTULOS_SERVIDOR)
    if "servidor" not in colunas:
        return None

    campos = {chave: "" for chave in colunas}

    def aproveitar(linha: Linha, exigir_matricula: bool) -> None:
        distribuidos = distribuir(linha, colunas)
        servidor = _sem_rotulo(distribuidos.get("servidor", ""), "SERVIDOR:")
        if exigir_matricula and not RE_MATRICULA_NOME.match(servidor):
            return
        for chave, valor in distribuidos.items():
            limpo = _sem_rotulo(valor, dict(ROTULOS_SERVIDOR)[chave])
            if limpo and not campos[chave]:
                campos[chave] = limpo

    aproveitar(rotulos, exigir_matricula=False)
    if not RE_MATRICULA_NOME.match(campos["servidor"]):
        for vizinha in (indice - 1, indice + 1):
            if 0 <= vizinha < len(linhas):
                aproveitar(linhas[vizinha][0], exigir_matricula=True)
    if not RE_MATRICULA_NOME.match(campos["servidor"]):
        _celula_depois_do_rotulo(rotulos, campos)

    _separar_rotulos_colados(campos)
    achado = RE_MATRICULA_NOME.match(campos["servidor"])
    if achado is None:
        return None

    return Segurado(
        matricula=achado.group(1).strip(),
        nome=achado.group(2).strip(),
        cpf=campos.get("cpf", "").strip(),
        admissao=campos.get("admissao", "").strip(),
        situacao=campos.get("status", "").strip(),
        fonte=fonte,
        pagina=pagina,
    )


def _celula_depois_do_rotulo(rotulos: Linha, campos: Dict[str, str]) -> None:
    """O servidor e a celula logo depois de "SERVIDOR:", longe ou nao dele.

    A matricula vem alinhada a direita no campo: "1449.1" comeca em x=85, mas
    "286.1" so em x=108, a 30 pontos do rotulo -- vao demais para a coluna do
    servidor ir alem do proprio "SERVIDOR:". E o nome comprido ainda encosta no
    "CPF:", e a celula "286.1 - FULANA ... SANTO CPF: 123.456.789-09" fica
    longe das duas colunas. Eram 14 dos 231 servidores da folha normal de Santo
    Antonio de Leverger. O CPF colado, `_separar_rotulos_colados` devolve.
    """
    celulas = [celula.texto.strip() for celula in rotulos.celulas]
    for posicao, texto in enumerate(celulas[:-1]):
        if texto.upper() != "SERVIDOR:":
            continue
        seguinte = celulas[posicao + 1]
        if RE_MATRICULA_NOME.match(seguinte):
            campos["servidor"] = seguinte
            if campos.get("cpf") and campos["cpf"] in seguinte:
                campos["cpf"] = ""
        return


def _separar_rotulos_colados(campos: Dict[str, str]) -> None:
    """Devolve a cada campo o pedaco que veio colado no anterior.

    O nome comprido termina encostado no rotulo seguinte -- "FULANA DE TAL DA
    SILVA DOS SAN" acaba em x=295 e "CPF:" comeca em 294 --, e sem vao entre
    os dois a celula e uma so: o nome saia "... DOS SAN CPF: 123.456.789-09" e
    o CPF vazio. Eram 282 dos 3.233 servidores de Barra do Garcas. O rotulo
    escrito DENTRO do valor e a marca de onde cortar.
    """
    ordem = [chave for chave, _rotulo in ROTULOS_SERVIDOR if chave in campos]
    for posicao, chave in enumerate(ordem):
        for seguinte in ordem[posicao + 1:]:
            rotulo = dict(ROTULOS_SERVIDOR)[seguinte]
            valor = campos[chave]
            corte = valor.upper().find(" " + rotulo.upper())
            if corte < 0:
                continue
            campos[chave] = valor[:corte].strip()
            resto = _sem_rotulo(valor[corte:], rotulo)
            # Se o campo ja tinha valor proprio, ele fica: o pedaco colado so
            # podia ser o mesmo valor repetido.
            if resto and not campos[seguinte]:
                campos[seguinte] = resto


def _sem_rotulo(valor: str, rotulo: str) -> str:
    """Tira o proprio rotulo da celula quando ele veio colado no valor."""
    limpo = valor.strip()
    if limpo.upper().startswith(rotulo.upper()):
        limpo = limpo[len(rotulo):]
    return limpo.strip()


def _ler_verba(linha: Linha, colunas: Dict[str, Coluna]) -> Optional[Verba]:
    """Uma linha do calculo, com os numeros na coluna certa.

    O que faz uma linha ser verba e ter um CODIGO so de digitos na primeira
    coluna e um valor em PROVENTO ou em DESCONTO. Testar isso DEPOIS de
    distribuir -- e nao com regex sobre o texto -- descarta de graca o
    "TOTAL PROVENTOS: 8.340,62" e as linhas soltas de "0,00" do cabecalho.
    """
    campos = distribuir(linha, colunas)
    codigo = campos.get("cod", "").strip()
    if not codigo.isdigit():
        return None

    provento = numero(campos.get("provento", ""))
    desconto = numero(campos.get("desconto", ""))
    if provento is None and desconto is None:
        return None

    # "P" ou "D" conforme a coluna em que o numero caiu. E' a MESMA convencao
    # do outro formato, e e o que faz `Verba.e_previdencia_do_segurado` --
    # desconto cuja descricao fala em previdencia -- valer aqui sem mudanca:
    # "7000 FUNDO PREVIDENCIA" entra, "7005 ABONO PERMANENCIA" (provento) nao.
    if desconto is not None:
        tipo, valor = "D", desconto
    else:
        tipo, valor = "P", provento

    base, quantidade = _base_e_qtd(campos)
    return Verba(
        codigo=codigo,
        descricao=RE_COLADO_NA_DESCRICAO.sub(
            "", campos.get("descricao", "")).strip(),
        tipo=tipo,
        referencia=quantidade,
        base=base,
        valor=valor,
    )


def _base_e_qtd(campos: Dict[str, str]):
    """A base e a quantidade, mesmo quando saem coladas numa celula so.

    As duas colunas vizinhas nem sempre ficam separadas o bastante: na folha
    de Barra do Garcas, a linha "942 PREVIDENCIA - FUNDO ... 5.713,8900
    14,0000 799,94" poe os dois numeros a sete pontos um do outro -- menos que
    o vao que divide celulas --, e eles viram a celula unica "5.713,8900
    14,0000". Lida como numero, essa celula e nada, e a base do servidor saia
    zerada com a contribuicao certa: 3.233 servidores e base somada de
    R$ 1.257,56.

    Quando a celula da base traz mais de um pedaco e a da quantidade esta
    vazia, o primeiro pedaco e a base e o ultimo e a quantidade.
    """
    base = campos.get("base", "").strip()
    qtd = campos.get("qtd", "").strip()
    pedacos = base.split()
    if len(pedacos) > 1 and not qtd:
        return numero(pedacos[0]), numero(pedacos[-1])
    return numero(base), numero(qtd)


def _limpar_tipo(texto: str) -> str:
    """"FOLHA MENSAL 07/2026" -> "Mensal".

    O cabecalho repete a competencia dentro do nome do tipo em algumas folhas
    desta familia e nao em outras. Deixada como veio, a mesma folha mensal sai
    como "Normal" num PDF e "Folha Mensal 07/2026" no outro, e juntar os dois
    levantava um aviso de tipos diferentes que nao existe.
    """
    limpo = re.sub(r"\s*\d{1,2}\s*/\s*\d{4}\s*$", "", texto or "").strip()
    limpo = re.sub(r"^FOLHA\s+", "", limpo, flags=re.IGNORECASE).strip()
    return limpo.title()
