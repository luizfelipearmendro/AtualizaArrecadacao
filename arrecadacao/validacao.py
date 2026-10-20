# -*- coding: utf-8 -*-
r"""Depois de importar: o que entrou no SISPREVWEB bate com a folha?

A importacao nao diz, no fim, quanto deixou de entrar. Ela recusa linha a
linha -- segurado nao encontrado, fonte pagadora que nao existe -- e o total do
Lancamento simplesmente fica menor que o da folha. Em Colniza 09/2026 faltaram
141.210,62 de base, e a causa so apareceu cruzando os dois arquivos: TODAS as
linhas de quatro fontes pagadoras (112, 146, 239, 122) tinham sido recusadas.

O SISPREVWEB exporta o Lancamento (Arrecadacao > Lancamento > Exportar) no
mesmo formato do cadastro de segurados, agora com os valores:

    CODIGO_ORGAO;NOME;ANO;MES;REMUNERACAO;VLR_SEGURADO;VLR_ORGAO;
    VLR_CUSTO_ESP;FONTE_PAG;CATEGORIA;DATA_ADMISSAO

Um segurado aparece numa linha por fonte pagadora do cadastro dele, quase
sempre com zero nas outras. Por isso os valores sao SOMADOS por codigo antes
de comparar.

**Contra o que se compara.** As linhas que foram para o arquivo: a matricula de
cada uma e a que o importador recebeu -- a do SISPREVWEB, quando a comparacao
de matriculas foi feita. Quem nao casa pelo codigo casa pelo nome, quando ele
e unico dos dois lados (a pessoa corrigida a mao no SISPREVWEB depois da
importacao entra com outro codigo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

from .layout import Linha
from .segurados_sisprev import _linhas_do_csv, nome_comparavel

CONFERE = "Confere"
DIFERENTE = "Valor diferente"
NAO_ENTROU = "Não entrou no SISPREVWEB"
SO_SISPREV = "Só no SISPREVWEB"
SEM_VALOR = "Sem valor nos dois"
SITUACOES = (CONFERE, DIFERENTE, NAO_ENTROU, SO_SISPREV, SEM_VALOR)

# Centavos de arredondamento: o SISPREVWEB grava com seis casas e a folha com
# duas. Acima disto e diferenca de verdade.
TOLERANCIA = 0.01

COLUNAS = {"codigo": "CODIGO_ORGAO", "nome": "NOME", "ano": "ANO", "mes": "MES",
           "remuneracao": "REMUNERACAO", "segurado": "VLR_SEGURADO",
           "orgao": "VLR_ORGAO", "custo": "VLR_CUSTO_ESP",
           "fonte": "FONTE_PAG", "categoria": "CATEGORIA",
           "admissao": "DATA_ADMISSAO"}
OBRIGATORIAS = ("codigo", "nome", "remuneracao", "segurado", "fonte")


class LancamentoInvalido(ValueError):
    """O arquivo nao e o export do Lancamento do SISPREVWEB."""


@dataclass(frozen=True)
class Lancamento:
    """Uma linha do export: um segurado numa fonte pagadora."""

    codigo: str
    nome: str
    ano: int
    mes: int
    remuneracao: float
    segurado: float
    orgao: float
    custo: float
    fonte: str
    categoria: str = ""
    admissao: str = ""

    @property
    def tem_valor(self) -> bool:
        return bool(self.remuneracao or self.segurado or self.orgao
                    or self.custo)


def _numero(texto) -> float:
    limpo = str(texto or "").strip().replace(" ", "")
    if not limpo:
        return 0.0
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return 0.0


def _inteiro(texto) -> int:
    try:
        return int(float(str(texto).strip().replace(",", ".")))
    except ValueError:
        return 0


def ler_lancamentos(caminho: str) -> List[Lancamento]:
    """As linhas do export do Lancamento, colunas achadas pelo nome."""
    linhas = _linhas_do_csv(Path(caminho))
    if not linhas:
        raise LancamentoInvalido("{} está vazio.".format(Path(caminho).name))
    cabecalho = [str(c or "").strip().upper() for c in linhas[0]]
    faltam = [COLUNAS[c] for c in OBRIGATORIAS if COLUNAS[c] not in cabecalho]
    if faltam:
        raise LancamentoInvalido(
            "{} não parece o export do Lançamento do SISPREVWEB: faltam as "
            "colunas {} na primeira linha.".format(
                Path(caminho).name, ", ".join(faltam)))
    indice = {chave: cabecalho.index(nome) for chave, nome in COLUNAS.items()
              if nome in cabecalho}

    def campo(campos, chave):
        i = indice.get(chave)
        return campos[i] if i is not None and i < len(campos) else ""

    lidos: List[Lancamento] = []
    for campos in linhas[1:]:
        codigo = str(campo(campos, "codigo")).strip()
        if not codigo:
            continue
        lidos.append(Lancamento(
            codigo=codigo, nome=str(campo(campos, "nome")).strip(),
            ano=_inteiro(campo(campos, "ano")), mes=_inteiro(campo(campos, "mes")),
            remuneracao=_numero(campo(campos, "remuneracao")),
            segurado=_numero(campo(campos, "segurado")),
            orgao=_numero(campo(campos, "orgao")),
            custo=_numero(campo(campos, "custo")),
            fonte=" ".join(str(campo(campos, "fonte")).split()),
            categoria=str(campo(campos, "categoria")).strip(),
            admissao=str(campo(campos, "admissao")).strip()))
    if not lidos:
        raise LancamentoInvalido(
            "{} não tem nenhum lançamento.".format(Path(caminho).name))
    return lidos


def competencia_dos_lancamentos(lancamentos: Sequence[Lancamento]) -> str:
    """"09/2026" -- a mais frequente, se o arquivo misturar."""
    contagem: Dict[str, int] = {}
    for l in lancamentos:
        if l.ano and l.mes:
            chave = "{:02d}/{:04d}".format(l.mes, l.ano)
            contagem[chave] = contagem.get(chave, 0) + 1
    return max(contagem, key=contagem.get) if contagem else ""


# ---------------------------------------------------------------------- #
# validacao
# ---------------------------------------------------------------------- #
@dataclass
class NoSisprev:
    """Um segurado do export, com os valores somados de todas as fontes."""

    codigo: str
    nome: str
    remuneracao: float = 0.0
    segurado: float = 0.0
    orgao: float = 0.0
    custo: float = 0.0
    fontes: List[str] = field(default_factory=list)   # so as com valor


@dataclass
class ItemValidado:
    situacao: str
    codigo: str                      # o que foi no arquivo
    nome: str
    fonte_enviada: str = ""          # o codigo de fonte que foi no arquivo
    fonte_folha: str = ""            # o nome da fonte na folha
    base_folha: float = 0.0
    segurado_folha: float = 0.0
    codigo_sisprev: str = ""
    base_sisprev: float = 0.0
    segurado_sisprev: float = 0.0
    orgao_sisprev: float = 0.0
    fontes_sisprev: str = ""
    observacao: str = ""

    @property
    def dif_base(self) -> float:
        return round(self.base_sisprev - self.base_folha, 2)

    @property
    def dif_segurado(self) -> float:
        return round(self.segurado_sisprev - self.segurado_folha, 2)


@dataclass
class GrupoFonte:
    """As linhas que foram com o mesmo codigo de fonte pagadora."""

    fonte_enviada: str
    fonte_folha: str
    linhas: int = 0
    nao_entraram: int = 0
    base_folha: float = 0.0
    segurado_folha: float = 0.0
    base_sisprev: float = 0.0
    segurado_sisprev: float = 0.0
    fontes_sisprev: List[str] = field(default_factory=list)

    @property
    def dif_base(self) -> float:
        return round(self.base_sisprev - self.base_folha, 2)

    @property
    def dif_segurado(self) -> float:
        return round(self.segurado_sisprev - self.segurado_folha, 2)


@dataclass
class Validacao:
    arquivo: str
    competencia: str = ""
    itens: List[ItemValidado] = field(default_factory=list)
    fontes: List[GrupoFonte] = field(default_factory=list)

    def contagem(self) -> Dict[str, int]:
        quantos = {s: 0 for s in SITUACOES}
        for item in self.itens:
            quantos[item.situacao] += 1
        return quantos

    def totais(self) -> Dict[str, float]:
        def soma(atributo):
            return round(sum(getattr(i, atributo) for i in self.itens), 2)
        return {"base_folha": soma("base_folha"),
                "segurado_folha": soma("segurado_folha"),
                "base_sisprev": soma("base_sisprev"),
                "segurado_sisprev": soma("segurado_sisprev"),
                "orgao_sisprev": soma("orgao_sisprev")}


def _somar_por_codigo(lancamentos: Sequence[Lancamento]) -> Dict[str, NoSisprev]:
    somados: Dict[str, NoSisprev] = {}
    for l in lancamentos:
        no = somados.setdefault(l.codigo, NoSisprev(l.codigo, l.nome))
        no.remuneracao += l.remuneracao
        no.segurado += l.segurado
        no.orgao += l.orgao
        no.custo += l.custo
        if l.tem_valor and l.fonte not in no.fontes:
            no.fontes.append(l.fonte)
    for no in somados.values():
        for atributo in ("remuneracao", "segurado", "orgao", "custo"):
            setattr(no, atributo, round(getattr(no, atributo), 2))
    return somados


def validar(linhas: Sequence[Linha], lancamentos: Sequence[Lancamento],
            arquivo: str = "") -> Validacao:
    """Cruza o que foi no arquivo com o que o SISPREVWEB registrou.

    `linhas` sao as linhas do arquivo importado, com a matricula que foi nele.
    """
    sisprev = _somar_por_codigo(lancamentos)
    por_nome: Dict[str, List[NoSisprev]] = {}
    for no in sisprev.values():
        por_nome.setdefault(nome_comparavel(no.nome), []).append(no)
    nomes_na_folha: Dict[str, int] = {}
    for linha in linhas:
        chave = nome_comparavel(linha.nome)
        nomes_na_folha[chave] = nomes_na_folha.get(chave, 0) + 1

    resultado = Validacao(arquivo=arquivo,
                          competencia=competencia_dos_lancamentos(lancamentos))
    usados: set = set()
    grupos: Dict[str, GrupoFonte] = {}

    for linha in linhas:
        no = sisprev.get(linha.matricula)
        observacao = ""
        if no is None or no.codigo in usados:
            # Pelo nome, so quando ele e unico dos dois lados: homonimo
            # cruzado com homonimo e chute.
            chave = nome_comparavel(linha.nome)
            candidatos = [n for n in por_nome.get(chave, [])
                          if n.codigo not in usados]
            if len(candidatos) == 1 and nomes_na_folha.get(chave) == 1:
                no = candidatos[0]
                observacao = "achado pelo nome: no SISPREVWEB está no código " \
                    "{}, o arquivo levou {}".format(no.codigo, linha.matricula)
            else:
                no = None
        if no is not None:
            usados.add(no.codigo)

        item = ItemValidado(
            situacao="", codigo=linha.matricula, nome=linha.nome,
            fonte_enviada=str(linha.fonte or ""), fonte_folha=linha.fonte_nome,
            base_folha=round(linha.base, 2),
            segurado_folha=round(linha.segurado, 2), observacao=observacao)
        if no is not None:
            item.codigo_sisprev = no.codigo
            item.base_sisprev = no.remuneracao
            item.segurado_sisprev = no.segurado
            item.orgao_sisprev = no.orgao
            item.fontes_sisprev = "; ".join(no.fontes)

        tem_folha = bool(item.base_folha or item.segurado_folha)
        tem_sisprev = bool(item.base_sisprev or item.segurado_sisprev)
        if not tem_folha and not tem_sisprev:
            item.situacao = SEM_VALOR
        elif tem_folha and not tem_sisprev:
            item.situacao = NAO_ENTROU
            if no is None:
                item.observacao = "o código {} não está no export".format(
                    linha.matricula)
            else:
                item.observacao = (item.observacao + "; " if item.observacao
                                   else "") + "está no cadastro, com valor zero"
        elif abs(item.dif_base) > TOLERANCIA or \
                abs(item.dif_segurado) > TOLERANCIA:
            item.situacao = DIFERENTE
        else:
            item.situacao = CONFERE
        resultado.itens.append(item)

        grupo = grupos.setdefault(item.fonte_enviada, GrupoFonte(
            item.fonte_enviada, item.fonte_folha))
        grupo.linhas += 1
        grupo.base_folha += item.base_folha
        grupo.segurado_folha += item.segurado_folha
        grupo.base_sisprev += item.base_sisprev
        grupo.segurado_sisprev += item.segurado_sisprev
        if item.situacao == NAO_ENTROU:
            grupo.nao_entraram += 1
        for fonte in (no.fontes if no is not None else []):
            if fonte not in grupo.fontes_sisprev:
                grupo.fontes_sisprev.append(fonte)

    # Quem tem valor no SISPREVWEB e nao veio do arquivo: lancamento feito a
    # mao, ou de outra importacao do mesmo mes. Entra no total do SISPREVWEB,
    # e sem esta lista a diferenca nao fecha.
    extras = GrupoFonte("", "(fora do arquivo importado)")
    for no in sisprev.values():
        if no.codigo in usados or not (no.remuneracao or no.segurado):
            continue
        resultado.itens.append(ItemValidado(
            situacao=SO_SISPREV, codigo="", nome=no.nome,
            codigo_sisprev=no.codigo, base_sisprev=no.remuneracao,
            segurado_sisprev=no.segurado, orgao_sisprev=no.orgao,
            fontes_sisprev="; ".join(no.fontes),
            observacao="tem valor no SISPREVWEB e não estava no arquivo"))
        extras.linhas += 1
        extras.base_sisprev += no.remuneracao
        extras.segurado_sisprev += no.segurado
        for fonte in no.fontes:
            if fonte not in extras.fontes_sisprev:
                extras.fontes_sisprev.append(fonte)

    resultado.fontes = sorted(
        grupos.values(), key=lambda g: (-abs(g.dif_base), g.fonte_enviada))
    if extras.linhas:
        resultado.fontes.append(extras)
    for grupo in resultado.fontes:
        for atributo in ("base_folha", "segurado_folha", "base_sisprev",
                         "segurado_sisprev"):
            setattr(grupo, atributo, round(getattr(grupo, atributo), 2))
    return resultado


def linhas_do_arquivo_importado(caminho: str) -> List[Linha]:
    """As linhas de um arquivo de importacao ja gerado (o .csv do layout).

    Para validar sem reler a folha: o arquivo e exatamente o que o importador
    recebeu. Nao traz o nome da fonte da folha nem a admissao -- so o que o
    layout tem.
    """
    from .complementar import ler_csv_sisprevweb
    return [Linha(matricula=l.matricula, nome=l.nome, ano=l.ano, mes=l.mes,
                  base=l.base, segurado=l.segurado, patronal=l.patronal,
                  especial=l.especial, fonte=l.fonte, categoria=l.categoria)
            for l in ler_csv_sisprevweb(caminho)]


# ---------------------------------------------------------------------- #
# resumo para o cliente
# ---------------------------------------------------------------------- #
@dataclass
class LinhaResumo:
    fonte: str
    segurados: int = 0
    remuneracao: float = 0.0
    segurado: float = 0.0
    orgao: float = 0.0
    custo: float = 0.0

    @property
    def total(self) -> float:
        return round(self.segurado + self.orgao + self.custo, 2)


def resumir_por_fonte(lancamentos: Sequence[Lancamento]) -> List[LinhaResumo]:
    """Uma linha por fonte pagadora do SISPREVWEB, so as que tem valor."""
    grupos: Dict[str, LinhaResumo] = {}
    codigos: Dict[str, set] = {}
    for l in lancamentos:
        if not l.tem_valor:
            continue
        grupo = grupos.setdefault(l.fonte, LinhaResumo(l.fonte))
        grupo.remuneracao += l.remuneracao
        grupo.segurado += l.segurado
        grupo.orgao += l.orgao
        grupo.custo += l.custo
        codigos.setdefault(l.fonte, set()).add(l.codigo)
    for fonte, grupo in grupos.items():
        grupo.segurados = len(codigos[fonte])
        for atributo in ("remuneracao", "segurado", "orgao", "custo"):
            setattr(grupo, atributo, round(getattr(grupo, atributo), 2))
    return sorted(grupos.values(), key=lambda g: g.fonte)


def total_do_resumo(linhas: Sequence[LinhaResumo],
                    lancamentos: Sequence[Lancamento]) -> LinhaResumo:
    total = LinhaResumo("Total")
    total.segurados = len({l.codigo for l in lancamentos if l.tem_valor})
    for atributo in ("remuneracao", "segurado", "orgao", "custo"):
        setattr(total, atributo,
                round(sum(getattr(l, atributo) for l in linhas), 2))
    return total
