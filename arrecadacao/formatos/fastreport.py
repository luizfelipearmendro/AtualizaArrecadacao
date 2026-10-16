# -*- coding: utf-8 -*-
"""A folha da prefeitura de Campinapolis, gerada em FastReport.

    SECRETARIA 02 - GABINETE DO PREFEITO
    DEPARTAMENTO 010 - GABINETE DO PREFEITO
    LOTACAO 00000001 - GABINETE DO PREFEITO
    Funcionario: 1990 - FULANO DE TAL SILVA C.P.F.: 123.456.789-09 Data Admissao: 11/03/2014
    Cargo :00439/A /01 - GESTOR DE TECNOLOGIA DA INFORMACAO
    Tipo Admissao: Efetivo
    CP Provento / Desconto / Neutro  N Parc.  Base  DEP  Referencia  Provento  Desconto  Neutro
    1  7000 PREVI-CAMP               3.809,74  T  14,00            533,36
    Sal. Base.: ... Sal. Bruto.: ... Total Desc: ... Sal. Liquido: ...

Proventos, descontos e "neutros" (informativos, como diarias) vem numa
coluna so de descricao; o que diz o que e cada verba e a coluna em que o VALOR
cai -- por isso a linha e distribuida pelo cabecalho. A base da previdencia
nao vem num quadro: vem na coluna Base da propria verba ("PREVI-CAMP
3.809,74"), que e exatamente a base de calculo do desconto.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from ..folha import Competencia, Folha, Segurado, Verba, numero
from ..fontes import FonteDaFolha
from ..leitor_pdf import Coluna, distribuir, localizar_colunas

NOME = "FastReport"

RE_ENTIDADE = re.compile(r"^((?:PREFEITURA|C.MARA)\b.+)$", re.IGNORECASE)
RE_COMPETENCIA = re.compile(r"FOLHA\s+DE\s+PAGAMENTO\s+DO\s+M.S\s+(\d{1,2})/(\d{4})",
                            re.IGNORECASE)
RE_DEPARTAMENTO = re.compile(r"^DEPARTAMENTO\s+\d+\s*-\s*(.+)$", re.IGNORECASE)
RE_LOTACAO = re.compile(r"^LOTA..O\s+\d+\s*-\s*(.+)$", re.IGNORECASE)
RE_FUNCIONARIO = re.compile(
    r"^Funcion.rio:\s*(\d+)\s*-\s*(.+?)\s+C\.P\.F\.:\s*([\d.\-]+)"
    r"(?:.*?Admiss.o:\s*(\d{2}/\d{2}/\d{4}))?", re.IGNORECASE)
RE_CARGO = re.compile(r"^Cargo\s*:\s*\S+\s+\S+\s*-\s*(.+)$", re.IGNORECASE)
RE_TIPO_ADMISSAO = re.compile(r"^Tipo\s+Admiss.o:\s*(.+)$", re.IGNORECASE)
RE_CABECALHO_VERBA = re.compile(r"^CP\s+Provento\s*/\s*Desconto", re.IGNORECASE)
RE_FIM_DO_BLOCO = re.compile(r"^Sal\.\s*Base", re.IGNORECASE)

ROTULOS_VERBA = (
    ("cp", "CP"),
    ("evento", "Provento"),
    ("parcela", "Nº"),
    ("base", "Base"),
    ("dep", "DEP"),
    ("referencia", "Referência"),
    ("provento", "Provento"),
    ("desconto", "Desconto"),
    ("neutro", "Neutro"),
)
VERBA_PELA_DIREITA = ("base", "referencia", "provento", "desconto", "neutro")
TIPO_DA_COLUNA = (("provento", "P"), ("desconto", "D"), ("neutro", "I"))


def pontuar(linhas: Sequence[tuple]) -> int:
    return sum(1 for linha, _p in linhas
               if RE_CABECALHO_VERBA.match(linha.texto.strip()))


def ler(linhas: Sequence[tuple], folha: Folha) -> List[Segurado]:
    for linha, _pagina in linhas[:15]:
        texto = linha.texto.strip()
        if not folha.entidade and RE_ENTIDADE.match(texto):
            folha.entidade = texto
        achado = RE_COMPETENCIA.search(texto)
        if achado and folha.competencia is None:
            folha.competencia = Competencia(ano=int(achado.group(2)),
                                            mes=int(achado.group(1)))
            folha.tipo = folha.tipo or "Mensal"
    return _ler_segurados(linhas)


def _ler_segurados(linhas: Sequence[tuple]) -> List[Segurado]:
    segurados: List[Segurado] = []
    atual: Optional[Segurado] = None
    departamento = ""
    fonte: Optional[FonteDaFolha] = None
    colunas: Dict[str, Coluna] = {}

    for linha, pagina in linhas:
        texto = linha.texto.strip()

        achado = RE_DEPARTAMENTO.match(texto)
        if achado:
            departamento = achado.group(1).strip()
            continue

        # A lotacao e o grupo mais fino da folha, e e nesse nivel que o
        # catalogo do SISPREVWEB separa as fontes ("SEC MUNICIPAL DE SAUDE
        # PSF", "... CAPS", "... FPM"). O numero dela ("00000001") recomeca em
        # cada departamento e nao e o da fonte: a escolha e feita na tela, e o
        # nome leva o departamento para os grupos nao se confundirem.
        achado = RE_LOTACAO.match(texto)
        if achado:
            nome = " / ".join(p for p in (departamento, achado.group(1).strip()) if p)
            fonte = FonteDaFolha(numero=0, nome=nome, folha_inteira=True,
                                 bruto=texto)
            continue

        achado = RE_FUNCIONARIO.match(texto)
        if achado:
            atual = Segurado(matricula=achado.group(1),
                             nome=achado.group(2).strip(),
                             cpf=achado.group(3),
                             admissao=achado.group(4) or "",
                             fonte=fonte, unidade=fonte.nome if fonte else "",
                             pagina=pagina)
            segurados.append(atual)
            colunas = {}
            continue

        if atual is None:
            continue

        achado = RE_CARGO.match(texto)
        if achado:
            atual.cargo = achado.group(1).strip()
            continue
        achado = RE_TIPO_ADMISSAO.match(texto)
        if achado:
            atual.regime = achado.group(1).strip()
            continue

        if RE_CABECALHO_VERBA.match(texto):
            colunas = localizar_colunas(linha, ROTULOS_VERBA,
                                        pela_direita=VERBA_PELA_DIREITA)
            continue

        if RE_FIM_DO_BLOCO.match(texto):
            atual, colunas = None, {}
            continue

        if colunas:
            verba = _montar_verba(distribuir(linha, colunas))
            if verba is not None:
                atual.verbas.append(verba)

    return segurados


def _montar_verba(campos: Dict[str, str]) -> Optional[Verba]:
    """"1 7000 PREVI-CAMP ..." -- o codigo e a primeira palavra do evento.

    O codigo nao tem rotulo proprio no cabecalho: fica entre o "CP" e a
    descricao, alinhado a direita, e chega junto com ela na coluna do evento.
    """
    codigo, _, descricao = campos.get("evento", "").strip().partition(" ")
    if not codigo.isdigit():
        return None
    for chave, tipo in TIPO_DA_COLUNA:
        valor = numero(campos.get(chave, ""))
        if valor is not None:
            return Verba(codigo=codigo, descricao=descricao.strip(), tipo=tipo,
                         referencia=numero(campos.get("referencia", "")),
                         base=numero(campos.get("base", "")), valor=valor)
    return None
