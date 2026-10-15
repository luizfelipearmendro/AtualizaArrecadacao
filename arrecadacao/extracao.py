# -*- coding: utf-8 -*-
r"""Do PDF para os segurados: escolhe o leitor do formato e confere o resultado.

Este modulo nao sabe ler folha nenhuma. Ele abre o PDF, emenda as paginas numa
lista unica de linhas, pergunta a `arrecadacao.formatos` qual leitor reconhece
aquele arquivo e, no fim, levanta os avisos que a tela precisa dar antes de
alguem exportar. Quem sabe ler cada folha sao os modulos de `formatos/`.

A separacao existe porque sao 29 municipios e cada prefeitura contrata o seu
sistema de folha. O que vale para todos -- emendar as paginas, conferir o que
saiu, avisar -- fica aqui; o que e de um gerador so fica la.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import formatos
from .folha import Folha, Origem, Segurado
from .fontes import FonteDaFolha
from .leitor_pdf import Pagina, abrir, paginas_sem_texto


def ler(caminho: str, progresso=None) -> Folha:
    """Le a folha inteira. `progresso` recebe (feitos, total, texto)."""
    paginas = abrir(caminho, progresso)
    folha = Folha(arquivo=caminho, paginas_sem_texto=paginas_sem_texto(paginas))

    if progresso:
        progresso(0, 0, "Localizando os segurados...")
    linhas = _emendar_paginas(paginas)

    leitor = formatos.reconhecer(linhas)
    if leitor is not None:
        folha.formato = leitor.NOME
        folha.segurados = leitor.ler(linhas, folha)
        _fonte_da_folha_inteira(folha)

    folha.origens = [Origem(arquivo=caminho, entidade=folha.entidade,
                            tipo=folha.tipo, formato=folha.formato,
                            competencia=folha.competencia,
                            paginas_sem_texto=list(folha.paginas_sem_texto),
                            segurados=len(folha.segurados))]
    _avisar(folha)
    return folha


def ler_varios(caminhos: Sequence[str], progresso=None) -> Folha:
    """Le varios PDFs e devolve UMA folha com todos os segurados.

    A arrecadacao de um mes raramente cabe num arquivo so: a prefeitura exporta
    a folha dela e a camara a sua, e o SISPREVWEB recebe um arquivo por
    municipio. Lidos separados, os dois viram duas exportacoes para conferir e
    importar em duplicata; lidos juntos, viram o arquivo que o sistema espera.

    Cada PDF e lido pelo seu proprio leitor -- os formatos podem ser
    diferentes, e em Barra do Garcas e Primavera eles sao o mesmo mas em
    municipios futuros nao serao. Os avisos sao refeitos sobre o conjunto, e
    nao somados: "3 matriculas repetidas" vale para a folha inteira, e e
    justamente entre dois PDFs que a matricula repetida passa despercebida.
    """
    caminhos = [c for c in caminhos if c]
    if not caminhos:
        return Folha()
    if len(caminhos) == 1:
        return ler(caminhos[0], progresso)

    lidas = []
    for indice, caminho in enumerate(caminhos, 1):
        if progresso:
            progresso(indice - 1, len(caminhos),
                      "Lendo {} ({} de {})...".format(
                          Path(caminho).name, indice, len(caminhos)))
        lidas.append(ler(caminho, progresso))
    return _juntar(lidas)


# ---------------------------------------------------------------------- #
def _juntar(lidas: Sequence[Folha]) -> Folha:
    """Uma folha so a partir de varias, mantendo de onde veio cada coisa."""
    junta = Folha(arquivo=lidas[0].arquivo)
    for parcial in lidas:
        junta.segurados.extend(parcial.segurados)
        junta.origens.extend(parcial.origens)
        junta.paginas_sem_texto.extend(parcial.paginas_sem_texto)

    # A competencia e o tipo saem do primeiro PDF que os trouxe; divergencia
    # entre arquivos vira aviso, nao escolha silenciosa -- juntar a folha de
    # julho com a de agosto e erro de quem anexou, e o programa tem de dizer.
    junta.competencia = next((o.competencia for o in junta.origens
                              if o.competencia is not None), None)
    junta.tipo = next((o.tipo for o in junta.origens if o.tipo), "")
    junta.entidade = " + ".join(
        _distintos(o.entidade for o in junta.origens if o.entidade))
    junta.formato = " + ".join(
        _distintos(o.formato for o in junta.origens if o.formato))

    _avisar(junta)
    _avisar_divergencias(junta)
    return junta


def _avisar_divergencias(folha: Folha) -> None:
    """Competencias ou tipos diferentes entre os PDFs anexados."""
    competencias = _distintos(str(o.competencia) for o in folha.origens
                              if o.competencia is not None)
    if len(competencias) > 1:
        folha.avisos.append(
            "Os documentos anexados são de competências diferentes ({}). "
            "Exportando juntos, todas as linhas sairão em {} — separe os "
            "arquivos se não for isso que você quer.".format(
                ", ".join(competencias), folha.competencia))

    # Comparar o TEXTO do tipo acusaria diferenca onde nao ha: o mesmo gerador
    # escreve "NORMAL" num PDF e "FOLHA MENSAL" no outro para a mesma coisa. O
    # que muda a competencia de saida e so o 13o salario, e e so disso que vale
    # avisar.
    decimos = [o.nome for o in folha.origens if _e_decimo(o.tipo)]
    mensais = [o.nome for o in folha.origens if not _e_decimo(o.tipo)]
    if decimos and mensais:
        folha.avisos.append(
            "Há folha de 13º salário ({}) junto com folha mensal ({}). As "
            "linhas do 13º sairão na competência 13 e as demais no mês da "
            "folha — confira se é isso que você quer num arquivo só.".format(
                ", ".join(decimos), ", ".join(mensais)))


def _e_decimo(tipo: str) -> bool:
    from .folha import Segurado
    return Segurado(tipo_folha=tipo or "").e_decimo_terceiro


def _distintos(itens) -> List[str]:
    vistos: List[str] = []
    for item in itens:
        if item and item not in vistos:
            vistos.append(item)
    return vistos


# ---------------------------------------------------------------------- #
def _fonte_da_folha_inteira(folha: Folha) -> None:
    """Quando NENHUM segurado tem fonte, a folha inteira e de uma fonte so.

    E' o caso da camara: das tres folhas de camara que temos, duas nao trazem
    grupo nenhum -- 94 servidores em Barra do Garcas e 25 em Primavera. Sem
    isto, eles chegariam na tela como "94 segurados sem fonte pagadora", um
    aviso que nao da o que fazer, e sairiam no arquivo sem codigo.

    Com a fonte sintetica eles viram UMA pendencia, com o nome da entidade, que
    se resolve escolhendo no catalogo como qualquer outra -- e a escolha fica
    gravada para o mes seguinte. A conversao so acontece quando a folha nao
    agrupa NINGUEM: se ela agrupa uns e outros nao, isso e falha de leitura do
    cabecalho do grupo, e inventar uma fonte esconderia o problema.
    """
    if not folha.segurados or any(s.fonte is not None for s in folha.segurados):
        return
    nome = folha.entidade.strip() or Path(folha.arquivo).stem
    fonte = FonteDaFolha(numero=0, nome=nome, folha_inteira=True,
                         bruto="documento inteiro: {}".format(
                             Path(folha.arquivo).name))
    for segurado in folha.segurados:
        segurado.fonte = fonte
        if not segurado.unidade:
            segurado.unidade = nome


# ---------------------------------------------------------------------- #
def _emendar_paginas(paginas: Sequence[Pagina]) -> List[tuple]:
    """Todas as linhas, em sequencia, cada uma sabendo de que pagina veio.

    Emendadas porque o bloco de um funcionario atravessa a quebra de pagina: o
    cabecalho dele fica no pe de uma e as verbas no topo da seguinte. Lendo
    pagina a pagina, esse servidor sairia sem contribuicao nenhuma -- e sem
    erro nenhum, que e o pior jeito de perder um registro.
    """
    return [(linha, pagina.numero) for pagina in paginas for linha in pagina.linhas]


# ---------------------------------------------------------------------- #
def _avisar(folha: Folha) -> None:
    """O que a tela precisa dizer antes de alguem exportar."""
    for origem in folha.origens:
        if not origem.paginas_sem_texto:
            continue
        # O numero da pagina so localiza alguma coisa se vier com o nome do
        # arquivo: anexados dois PDFs, "página 7" existe nos dois.
        onde = " de {}".format(origem.nome) if len(folha.origens) > 1 else ""
        folha.avisos.append(
            "{} página(s){} sem texto — a folha parece digitalizada. "
            "Os valores dessas páginas NÃO foram lidos: {}.".format(
                len(origem.paginas_sem_texto), onde,
                _resumir(origem.paginas_sem_texto)))

    vazias = [o.nome for o in folha.origens if not o.segurados]
    if vazias and folha.segurados:
        folha.avisos.append(
            "Nenhum segurado foi encontrado em {}. Esse documento não entrou "
            "no arquivo — confira se ele está em um dos formatos conhecidos "
            "({}).".format(", ".join(vazias), ", ".join(formatos.nomes())))

    if not folha.segurados:
        # A mensagem diz QUAIS formatos o programa conhece: quem recebe
        # "formato não reconhecido" sem isso nao tem o que fazer com a
        # informacao, e a saida util e mandar o PDF para acrescentar o leitor.
        folha.avisos.append(
            "Nenhum segurado encontrado. Este PDF não está em nenhum dos "
            "formatos de folha que o programa conhece ({}). Se for de um "
            "município novo, o PDF precisa ser analisado para acrescentar o "
            "leitor dele.".format(", ".join(formatos.nomes())))
        return

    if folha.competencia is None:
        folha.avisos.append(
            "Competência não encontrada no cabeçalho. Informe o ano e o mês "
            "antes de exportar.")

    sem_previdencia = folha.sem_previdencia
    if sem_previdencia:
        folha.avisos.append(
            "{} segurado(s) sem desconto previdenciário no mês. Confira antes "
            "de exportar: {}.".format(
                len(sem_previdencia),
                _resumir([s.matricula or s.nome for s in sem_previdencia])))

    sem_fonte = folha.sem_fonte
    if sem_fonte:
        folha.avisos.append(
            "{} segurado(s) sem fonte pagadora na folha — o cabeçalho do "
            "grupo não foi reconhecido, e essas linhas sairão sem código: "
            "{}.".format(len(sem_fonte),
                         _resumir([s.matricula or s.nome for s in sem_fonte])))

    sem_matricula = [s for s in folha.segurados if not s.matricula]
    if sem_matricula:
        folha.avisos.append(
            "{} segurado(s) sem matrícula legível: {}.".format(
                len(sem_matricula),
                _resumir([s.nome or "(sem nome)" for s in sem_matricula])))

    repetidas = _matriculas_repetidas(folha.segurados)
    if repetidas:
        folha.avisos.append(
            "{} matrícula(s) aparecem mais de uma vez nesta folha — a "
            "importação costuma recusar competência repetida para o mesmo "
            "segurado: {}.".format(len(repetidas), _resumir(repetidas)))


def _matriculas_repetidas(segurados: Sequence[Segurado]) -> List[str]:
    """Quem sai duas vezes NA MESMA competencia -- e so isso e problema.

    Contar a matricula crua acusaria os cem servidores de Barra do Garcas que
    aparecem na folha mensal e na de 13o do mesmo PDF. Esses dois blocos viram
    linhas em competencias diferentes (07 e 13), que e o certo, e avisar sobre
    eles treinaria o usuario a ignorar o aviso -- justamente o aviso que
    precisa ser levado a serio quando a repeticao for de verdade.
    """
    vistas: Dict[tuple, int] = {}
    for segurado in segurados:
        if segurado.matricula:
            chave = (segurado.matricula, segurado.e_decimo_terceiro)
            vistas[chave] = vistas.get(chave, 0) + 1
    return [m for (m, _decimo), quantas in vistas.items() if quantas > 1]


def _resumir(itens: Sequence, limite: int = 10) -> str:
    textos = [str(i) for i in itens]
    if len(textos) <= limite:
        return ", ".join(textos)
    return "{} ... (+{})".format(", ".join(textos[:limite]), len(textos) - limite)
