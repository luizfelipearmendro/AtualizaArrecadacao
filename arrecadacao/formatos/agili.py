# -*- coding: utf-8 -*-
r"""Folha do gerador Agili -- a de Aripuana e das prefeituras que usam o mesmo.

A folha nao marca o fim de um funcionario, so o comeco do proximo. O bloco e
delimitado assim:

    Funcionario(a)  Matricula  Situacao  Estrutura ADM ...   <- ABRE o bloco
    FULANA DE TAL DA SILVA SANTOS  9999  Ativo  1.02.001
    Cargo - Estrutura do Cargo
    1177 - AGENTE ADMINISTRATIVO-VI-A - A.01
    Regime Previdenciario   Multiplos vinculos  Vinculo  Forma de ingresso
    RPPS - Regime proprio de previdencia social   Nao   30   Nomeacao ...
    Calculo mensal   Tipo   Referencia   Base   Integral   Valor
    1 - SALARIO MENSAL      (P) - Dia   30,00   4.810,11  4.810,11  4.810,11
    8850 - PREVIDENCIA MUNICIPAL  (D) - Tabela  14,00  4.810,11  673,42  673,42
    Total de proventos: ...  Total de descontos: ...  Total liquido: ...
    Funcionario(a)  Matricula  ...                          <- FECHA o anterior

Ou seja: cada cabecalho fecha o bloco anterior e abre o seguinte, e o ultimo de
cada pagina e fechado pelo rodape. Percorrer as paginas em sequencia -- e nao
pagina a pagina isolada -- e o que faz um bloco partido pela quebra de pagina
continuar inteiro; as 225 paginas da folha mensal viram uma lista unica de
linhas por isso.

Uma escolha que parece detalhe e nao e: as colunas sao lidas do CABECALHO de
cada bloco, e nao fixadas em constantes. O mesmo municipio emite folha mensal,
de rescisao e de 13o pelo mesmo sistema, e elas nao tem as mesmas colunas nas
mesmas posicoes. Reler o cabecalho custa quase nada e e o que permite abrir uma
folha de outro layout sem reescrever este arquivo.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from ..folha import Competencia, Folha, Segurado, Verba, numero
from ..fontes import RE_FONTE_NA_FOLHA, FonteDaFolha
from ..leitor_pdf import Coluna, Linha, distribuir, localizar_colunas

NOME = "Agili"

# --- cabecalho do bloco de funcionario --------------------------------- #
# Os rotulos NA ORDEM das colunas. A primeira palavra basta para achar cada um.
ROTULOS_SEGURADO = (
    ("nome", "Funcionário(a)"),
    ("matricula", "Matrícula"),
    ("situacao", "Situação"),
    ("estrutura", "Estrutura"),
    ("admissao", "Data"),
    ("cpf", "C.P.F."),
    ("pis", "PIS/PASEP"),
)

# --- cabecalho da tabela de verbas ------------------------------------- #
ROTULOS_VERBA = (
    ("descricao", "Cálculo"),
    ("tipo", "Tipo"),
    ("referencia", "Referência"),
    ("base", "Base"),
    ("integral", "Integral"),
    ("valor", "Valor"),
)
# Dinheiro alinha a direita: ver `leitor_pdf.Coluna`.
VERBAS_PELA_DIREITA = ("referencia", "base", "integral", "valor")

RE_CABECALHO_SEGURADO = re.compile(r"^Funcion.rio\(a\)\s+Matr.cula", re.IGNORECASE)
# "Calculo mensal Tipo ...", mas tambem "Calculo 13o salario Tipo ..." e
# "Calculo da rescisao Tipo ...": o que vem entre "Calculo" e "Tipo" e o nome
# da folha, e varia em numero de palavras. Exigir uma palavra so fazia a folha
# de 13o passar SEM tabela de verbas -- o segurado saia com contribuicao zero,
# e zero e um numero que ninguem estranha numa planilha de 774 linhas.
RE_CABECALHO_VERBA = re.compile(
    r"^C.lculo\b.*\bTipo\b.*\bValor\b", re.IGNORECASE)
RE_COMPETENCIA = re.compile(r"FOLHA DE PAGAMENTO\s*[-–]\s*(\d{1,2})\s*/\s*(\d{4})")
RE_SUBTITULO = re.compile(r"^\((.+)\)$")
RE_REGIME = re.compile(r"^(RPPS|RGPS)\b")
RE_ENTIDADE = re.compile(r"^1\s+-\s+(.+)$")
# "1.09.016 - FUNDO MUNICIPAL DE SAUDE": o nome que a estrutura ADM carrega.
RE_UNIDADE = re.compile(r"^(\d+\.\d+\.\d+)\s+-\s+(.+)$")
# A MESMA linha de fonte aparece duas vezes: como cabecalho do grupo, e como
# rotulo do subtotal no fim dele. O subtotal vem emendado com o texto da
# tabelinha de totais ("... funcionarios", "... Proventos Descontos Liquido"),
# porque na pagina eles estao lado a lado e o leitor junta a linha inteira.
# Sem separar os dois, o subtotal do grupo que acabou viraria a fonte do
# proximo servidor -- e o servidor sairia creditado na fonte anterior.
RE_RODAPE_DO_GRUPO = re.compile(r"(funcion.rios|Proventos\s+Descontos)",
                                re.IGNORECASE)
# A linha de numeros do subtotal: "8 R$ 38.209,22 R$ 10.132,35 R$ 28.076,87".
# As vezes o codigo da ficha nao cabe na linha de cima e cai colado na frente
# ("1.540 25 R$ 90.154,36 ..."), por isso o primeiro pedaco e opcional.
RE_TOTAL_DO_GRUPO = re.compile(r"^(?:\S+\s+)?\d+\s+R\$\s*[\d.]+,\d\d")
# "8850 - PREVIDENCIA MUNICIPAL   (D) - Tabela   14,00 ..."
RE_VERBA = re.compile(r"^(\d+)\s+-\s+(.*?)\s+\((P|D|N|B|I)\)\s+-\s+\S+")
RE_CARGO = re.compile(r"^(\d+)\s+-\s+(.+)$")


def _ler_cabecalho_da_folha(linhas: Sequence[tuple], folha: Folha) -> None:
    """Competencia, tipo e entidade -- estao nas primeiras linhas da pagina 1."""
    for linha, _pagina in linhas[:40]:
        texto = linha.texto.strip()

        if folha.competencia is None:
            achado = RE_COMPETENCIA.search(texto)
            if achado:
                folha.competencia = Competencia(ano=int(achado.group(2)),
                                                mes=int(achado.group(1)))
                continue

        # O subtitulo so vale DEPOIS da competencia: "(Mensal)" vem logo abaixo
        # do "FOLHA DE PAGAMENTO - 08/2026", e antes dele ha outros parenteses
        # no cabecalho do gerador.
        if folha.competencia is not None and not folha.tipo:
            achado = RE_SUBTITULO.match(texto)
            if achado and len(texto) < 40:
                folha.tipo = achado.group(1).strip()
                continue

        if not folha.entidade:
            achado = RE_ENTIDADE.match(texto)
            if achado:
                folha.entidade = achado.group(1).strip()


def _ler_segurados(linhas: Sequence[tuple], folha: Folha) -> List[Segurado]:
    """Percorre as linhas abrindo um segurado a cada cabecalho de bloco."""
    segurados: List[Segurado] = []
    atual: Optional[Segurado] = None
    colunas_verba: Dict[str, Coluna] = {}
    unidade_corrente = ""
    fonte_corrente: Optional[FonteDaFolha] = None

    for indice, (linha, pagina) in enumerate(linhas):
        texto = linha.texto.strip()

        # A fonte pagadora vem logo abaixo da estrutura e vale para todos os
        # servidores ate a proxima -- e a chave do de/para com o SISPREVWEB.
        # Testada ANTES da unidade porque "2 - 1 - 2002 -GABINETE..." tambem
        # casa com o padrao de nivel de estrutura.
        achado = RE_FONTE_NA_FOLHA.match(texto)
        if achado and not _e_rodape(linhas, indice):
            fonte_corrente = FonteDaFolha(numero=int(achado.group(2)),
                                          nome=achado.group(3).strip(),
                                          bruto=texto)
            continue

        # O titulo da unidade vem ANTES dos funcionarios dela e vale para todos
        # ate o proximo: e so ele que diz que "1.09.016" se chama "FUNDO
        # MUNICIPAL DE SAUDE", nome que a tela das fontes pagadoras mostra para
        # o usuario nao ter de decorar codigo.
        achado = RE_UNIDADE.match(texto)
        if achado:
            unidade_corrente = achado.group(2).strip()
            continue

        if RE_CABECALHO_SEGURADO.match(texto):
            proxima = linhas[indice + 1][0] if indice + 1 < len(linhas) else None
            atual = _abrir_segurado(linha, proxima, pagina, unidade_corrente,
                                    fonte_corrente)
            if atual is not None:
                segurados.append(atual)
            colunas_verba = {}
            continue

        if atual is None:
            continue

        if RE_CABECALHO_VERBA.match(texto):
            colunas_verba = localizar_colunas(linha, ROTULOS_VERBA,
                                              pela_direita=VERBAS_PELA_DIREITA)
            continue

        if not atual.regime and RE_REGIME.match(texto):
            _ler_regime(linha, atual)
            continue

        if not atual.cargo and RE_CARGO.match(texto) and not RE_VERBA.match(texto):
            atual.cargo = texto
            continue

        if colunas_verba and RE_VERBA.match(texto):
            verba = _ler_verba(linha, colunas_verba)
            if verba is not None:
                atual.verbas.append(verba)

    return segurados


def _e_rodape(linhas: Sequence[tuple], indice: int) -> bool:
    """A linha de fonte que aparece no FIM do grupo, e nao no comeco dele.

    A mesma linha serve de cabecalho do grupo e de rotulo do subtotal que o
    encerra. No subtotal ela vem emendada com o texto da tabelinha de totais
    -- "... funcionarios", "... Proventos Descontos" --, e era so isso que o
    programa testava.

    So que nem sempre: quando a tabelinha quebra, o rotulo fica sozinho na
    linha e o texto cai na seguinte. Ai o subtotal passava por cabecalho, e
    como o nome vinha cortado ("2072- SAUDE VIG EPID. EFETIVOS" sem o
    "F.2.600.0000605"), nascia uma fonte que nao existe -- e os 8 servidores
    do grupo SEGUINTE eram creditados nela. Por isso a linha de baixo tambem
    e olhada: depois de um subtotal vem "8 R$ 38.209,22 ..." ou a propria
    tabelinha.
    """
    texto = linhas[indice][0].texto.strip()
    if RE_RODAPE_DO_GRUPO.search(texto):
        return True
    if indice + 1 >= len(linhas):
        return False
    seguinte = linhas[indice + 1][0].texto.strip()
    return bool(RE_RODAPE_DO_GRUPO.search(seguinte)
                or RE_TOTAL_DO_GRUPO.match(seguinte))


def _abrir_segurado(cabecalho: Linha, valores: Optional[Linha], pagina: int,
                    unidade: str,
                    fonte: Optional[FonteDaFolha] = None) -> Optional[Segurado]:
    """Le a linha de valores logo abaixo do cabecalho do bloco."""
    if valores is None:
        return None
    colunas = localizar_colunas(cabecalho, ROTULOS_SEGURADO)
    if "nome" not in colunas or "matricula" not in colunas:
        return None          # cabecalho truncado: bloco nao aproveitavel

    campos = distribuir(valores, colunas)
    return Segurado(
        matricula=campos.get("matricula", "").strip(),
        nome=campos.get("nome", "").strip(),
        cpf=campos.get("cpf", "").strip(),
        situacao=campos.get("situacao", "").strip(),
        estrutura=campos.get("estrutura", "").strip(),
        unidade=unidade,
        fonte=fonte,
        admissao=campos.get("admissao", "").strip(),
        pagina=pagina,
    )


def _ler_regime(linha: Linha, segurado: Segurado) -> None:
    """Regime previdenciario e forma de ingresso, da linha que comeca em RPPS.

    As duas saem da mesma linha, e sao lidas por posicao relativa as celulas:
    a primeira celula e o regime, e a forma de ingresso e a celula de texto
    mais larga entre as seguintes -- "Nomeacao para cargo efetivo" ao lado de
    "Nao", "30", "200" e "0". Escolher pela largura, e nao por indice fixo,
    porque a folha omite celula vazia: contar posicoes acerta na folha mensal e
    erra na de rescisao.
    """
    celulas = linha.celulas
    if not celulas:
        return
    segurado.regime = celulas[0].texto.strip()

    candidatas = [c.texto.strip() for c in celulas[1:]
                  if any(ch.isalpha() for ch in c.texto)]
    if candidatas:
        segurado.ingresso = max(candidatas, key=len)


def _ler_verba(linha: Linha, colunas: Dict[str, Coluna]) -> Optional[Verba]:
    """Uma linha do calculo mensal, com os numeros na coluna certa."""
    achado = RE_VERBA.match(linha.texto.strip())
    if not achado:
        return None
    campos = distribuir(linha, colunas)
    return Verba(
        codigo=achado.group(1),
        descricao=achado.group(2).strip(),
        tipo=achado.group(3),
        referencia=numero(campos.get("referencia", "")),
        base=numero(campos.get("base", "")),
        integral=numero(campos.get("integral", "")),
        valor=numero(campos.get("valor", "")),
    )


# ---------------------------------------------------------------------- #
def pontuar(linhas: Sequence[tuple]) -> int:
    """Quantos blocos de funcionario DESTE formato o PDF tem.

    E' a marca que so existe aqui: "Funcionario(a) Matricula ...". A folha de
    outro gerador pontua zero, e e assim que o despachante escolhe sem precisar
    perguntar nada a quem abriu o arquivo.
    """
    return sum(1 for linha, _p in linhas
               if RE_CABECALHO_SEGURADO.match(linha.texto.strip()))


def ler(linhas: Sequence[tuple], folha: Folha) -> List[Segurado]:
    """Preenche o cabecalho da folha e devolve os segurados."""
    _ler_cabecalho_da_folha(linhas, folha)
    return _ler_segurados(linhas, folha)
