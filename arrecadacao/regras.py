# -*- coding: utf-8 -*-
"""As regras de cada municipio, e a aplicacao delas sobre a folha lida.

O leitor de PDF responde "o que a folha diz". O que fazer com isso varia de
municipio para municipio, e ate de quem declara: em Aripuana a rescisao da
FULANA DE TAL traz o 13o proporcional com previdencia propria

    8850 PREVIDENCIA MUNICIPAL              504,91    70,69
    8847 PREVIDENCIA S/ 13o SALARIO RESCISAO 1.472,65  206,17
    10004 Base Patronal para RPPS          1.977,56   276,86

e a propria folha soma os dois na base patronal. Um RPPS quer assim, numa
linha so no mes; outro quer o 13o na competencia 13. Nao ha resposta certa no
codigo -- e uma escolha, e escolha mora numa configuracao, nao num `if`.

Por isso as regras sao dados: a REGRA GERAL vale para todos, e cada municipio
guarda so o que tem de diferente. Escolher o municipio na tela da folha traz
as regras dele, e trocar uma regra depois da leitura refaz as linhas sem reler
o PDF -- `aplicar` trabalha sobre uma copia da folha lida, que fica intacta.

O que uma regra decide hoje:

* `formato`            qual leitor usar ("" = o programa reconhece sozinho)
* `decimo_na_rescisao` somar o 13o da rescisao a linha do mes, ou separar
* `complementar`       o municipio manda um arquivo alem do PDF (Nova Olimpia)
* `categoria`          a coluna 10 do layout
* `excluir`/`incluir`  verbas que a regra de palavra erra NESTE municipio --
                       somam-se as da regra geral, nao a substituem
* `observacoes`        o que quem faz a arrecadacao precisa lembrar
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .complementar import LinhaComplementar, chave_de_matricula
from .folha import (CATEGORIA_PADRAO, Folha, Segurado, Verba,
                    _caixa_alta_sem_acento, _e_so_decimo_terceiro)
from .municipios import MUNICIPIOS, sem_acento

_log = logging.getLogger(__name__)

ARQUIVO = "regras_municipios.json"

DECIMO_SOMAR = "somar"
DECIMO_SEPARAR = "separar"
NOMES_DECIMO = {
    DECIMO_SOMAR: "Somar à linha do mês",
    DECIMO_SEPARAR: "Separar na competência 13",
}

COMPLEMENTAR_NENHUM = ""
COMPLEMENTAR_CSV = "csv_sisprevweb"
NOMES_COMPLEMENTAR = {
    COMPLEMENTAR_NENHUM: "Nenhum — só o PDF",
    COMPLEMENTAR_CSV: "CSV no layout do SISPREVWEB (base por servidor)",
}

# O tipo de folha que o 13o separado recebe. So "13o salario", sem dizer de
# onde veio: "13o salario (separado de Normal)" tem a palavra NORMAL, e
# `_e_so_decimo_terceiro` leria isso como folha do mes -- ver la por que.
TIPO_DECIMO_SEPARADO = "13º salário"

CAMPOS_SIMPLES = ("formato", "decimo_na_rescisao", "complementar", "categoria")
CAMPOS_LISTA = ("excluir", "incluir")

# O que ja se sabe de cada municipio na primeira vez que o programa abre. So
# vale enquanto nao ha arquivo de regras: depois dele, quem manda e a tela.
PADROES_DE_FABRICA: Dict[str, dict] = {
    "NOVA OLÍMPIA": {
        "complementar": COMPLEMENTAR_CSV,
        "observacoes": "A Dura Lex não imprime a base de cada servidor, só a "
                       "contribuição. O CSV que a prefeitura manda junto traz "
                       "a base exata.",
    },
}


@dataclass
class Regras:
    formato: str = ""
    decimo_na_rescisao: str = DECIMO_SOMAR
    complementar: str = COMPLEMENTAR_NENHUM
    categoria: str = CATEGORIA_PADRAO
    excluir: List[str] = field(default_factory=list)
    incluir: List[str] = field(default_factory=list)
    observacoes: str = ""

    def resumo(self) -> List[str]:
        """Frases curtas para a tela da folha mostrar o que esta valendo."""
        partes = ["Formato: {}".format(self.formato or "reconhecido sozinho"),
                  "13º na rescisão: {}".format(
                      NOMES_DECIMO.get(self.decimo_na_rescisao, "?").lower())]
        if self.complementar:
            partes.append("Pede o CSV complementar")
        if self.excluir:
            partes.append("{} verba(s) fora do RPPS".format(len(self.excluir)))
        if self.incluir:
            partes.append("{} verba(s) a mais no RPPS".format(len(self.incluir)))
        return partes


def _regras_de_dicionario(bruto: dict) -> Regras:
    regras = Regras()
    for chave in CAMPOS_SIMPLES + ("observacoes",):
        if isinstance(bruto.get(chave), str):
            setattr(regras, chave, bruto[chave])
    for chave in CAMPOS_LISTA:
        if isinstance(bruto.get(chave), list):
            setattr(regras, chave, [str(i) for i in bruto[chave] if str(i).strip()])
    return regras


# ---------------------------------------------------------------------- #
# a configuracao gravada
# ---------------------------------------------------------------------- #
class Configuracao:
    """A regra geral, o que cada municipio muda nela, e os municipios a mais."""

    def __init__(self, pasta: Optional[Path] = None,
                 geral: Optional[Regras] = None,
                 municipios: Optional[Dict[str, dict]] = None,
                 extras: Optional[List[str]] = None) -> None:
        self.pasta = Path(pasta) if pasta else None
        self.geral = geral or Regras()
        self.municipios: Dict[str, dict] = municipios or {}
        self.extras: List[str] = extras or []

    # ------------------------------------------------------------------ #
    @classmethod
    def carregar(cls, pasta: Path) -> "Configuracao":
        """Le o arquivo. Sem arquivo, comeca dos padroes de fabrica."""
        alvo = Path(pasta) / ARQUIVO
        try:
            bruto = json.loads(alvo.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls(pasta, municipios=copy.deepcopy(PADROES_DE_FABRICA))
        except (OSError, ValueError) as erro:
            # Arquivo estragado nao derruba o programa, mas tambem nao some em
            # silencio: o log diz, e a primeira gravacao o substitui.
            _log.warning("regras de municipio ilegiveis (%s): %s", alvo, erro)
            return cls(pasta, municipios=copy.deepcopy(PADROES_DE_FABRICA))
        municipios = {}
        for nome, proprias in (bruto.get("municipios") or {}).items():
            if isinstance(proprias, dict):
                municipios[str(nome)] = _limpar_proprias(proprias)
        return cls(pasta,
                   geral=_regras_de_dicionario(bruto.get("geral") or {}),
                   municipios=municipios,
                   extras=[str(m) for m in bruto.get("extras") or []])

    def salvar(self) -> None:
        if self.pasta is None:
            return
        alvo = self.pasta / ARQUIVO
        alvo.parent.mkdir(parents=True, exist_ok=True)
        provisorio = alvo.with_suffix(".tmp")
        provisorio.write_text(json.dumps({
            "geral": asdict(self.geral),
            "municipios": self.municipios,
            "extras": self.extras,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        # Gravar ao lado e trocar: cair no meio de `write_text` deixaria as
        # regras de todos os municipios num arquivo pela metade.
        provisorio.replace(alvo)

    # ------------------------------------------------------------------ #
    def lista_de_municipios(self) -> List[str]:
        """Os da lista do programa mais os acrescentados, em ordem alfabetica."""
        todos = list(MUNICIPIOS) + [m for m in self.extras if m not in MUNICIPIOS]
        return sorted(todos, key=sem_acento)

    def acrescentar(self, nome: str) -> str:
        """Acrescenta um municipio a lista. Devolve o nome como ficou gravado."""
        limpo = " ".join(str(nome or "").upper().split())
        if not limpo:
            raise ValueError("nome vazio")
        existente = next((m for m in self.lista_de_municipios()
                          if sem_acento(m) == sem_acento(limpo)), None)
        if existente:
            return existente
        self.extras.append(limpo)
        return limpo

    def proprias(self, municipio: str) -> dict:
        """So o que este municipio muda na regra geral."""
        return copy.deepcopy(self.municipios.get(municipio, {}))

    def configurado(self, municipio: str) -> bool:
        return bool(self.municipios.get(municipio))

    def definir_proprias(self, municipio: str, proprias: dict) -> None:
        limpas = _limpar_proprias(proprias)
        if limpas:
            self.municipios[municipio] = limpas
        else:
            self.municipios.pop(municipio, None)

    def regras_de(self, municipio: str) -> Regras:
        """A regra geral com o que o municipio muda por cima.

        As listas de verbas SOMAM: excluir a CAPEMISA em Leverger nao pode
        desfazer a exclusao geral do INSS.
        """
        regras = copy.deepcopy(self.geral)
        proprias = self.municipios.get(municipio or "", {})
        for chave in CAMPOS_SIMPLES:
            if chave in proprias:
                setattr(regras, chave, proprias[chave])
        for chave in CAMPOS_LISTA:
            for item in proprias.get(chave, []):
                if item not in getattr(regras, chave):
                    getattr(regras, chave).append(item)
        regras.observacoes = proprias.get("observacoes", "")
        return regras


def _limpar_proprias(proprias: dict) -> dict:
    """Tira o que nao muda nada: chave desconhecida, lista vazia, None."""
    limpas = {}
    for chave in CAMPOS_SIMPLES:
        valor = proprias.get(chave)
        if isinstance(valor, str):
            limpas[chave] = valor
    for chave in CAMPOS_LISTA:
        itens = [str(i).strip() for i in proprias.get(chave) or [] if str(i).strip()]
        if itens:
            limpas[chave] = itens
    observacoes = str(proprias.get("observacoes") or "").strip()
    if observacoes:
        limpas["observacoes"] = observacoes
    return limpas


# ---------------------------------------------------------------------- #
# aplicacao
# ---------------------------------------------------------------------- #
def aplicar(folha: Folha, regras: Regras,
            complementar: Optional[Tuple[str, Sequence[LinhaComplementar]]] = None
            ) -> Folha:
    """Uma COPIA da folha com as regras aplicadas. A folha lida nao muda.

    `complementar` e (nome do arquivo, linhas) do CSV que o municipio mandou.
    Os avisos sao refeitos sobre o resultado: o "13o somado a linha do mes"
    nao pode continuar na tela depois que a regra separou o 13o.
    """
    from . import extracao

    nova = copy.copy(folha)
    nova.segurados = []
    for segurado in folha.segurados:
        copia = replace(segurado, verbas=[replace(v) for v in segurado.verbas])
        _marcar_verbas(copia, regras)
        if regras.decimo_na_rescisao == DECIMO_SEPARAR:
            nova.segurados.extend(_separar_decimo(copia, folha))
        else:
            nova.segurados.append(copia)

    nova.avisos = []
    extracao.refazer_avisos(nova)
    separados = len(nova.segurados) - len(folha.segurados)
    if regras.decimo_na_rescisao == DECIMO_SEPARAR and separados:
        nova.avisos.append(
            "{} segurado(s) tinham previdência de 13º dentro do bloco do mês e "
            "ganharam uma linha própria na competência 13, pela regra do "
            "município.".format(separados))
    if complementar is not None:
        _aplicar_complementar(nova, *complementar)
    return nova


def _marcar_verbas(segurado: Segurado, regras: Regras) -> None:
    """O que a regra do municipio diz de cada desconto. Excluir vence incluir."""
    if not (regras.excluir or regras.incluir):
        return
    for verba in segurado.verbas:
        if verba.tipo != "D":
            continue
        if _casa(verba, regras.excluir):
            verba.forcado = False
        elif _casa(verba, regras.incluir):
            verba.forcado = True


def _casa(verba: Verba, padroes: Sequence[str]) -> bool:
    """So digitos: e o CODIGO da verba. Texto: um pedaco da descricao."""
    descricao = _caixa_alta_sem_acento(verba.descricao)
    for padrao in padroes:
        limpo = _caixa_alta_sem_acento(padrao).strip()
        if not limpo:
            continue
        if limpo.isdigit():
            if str(verba.codigo).strip() == limpo:
                return True
        elif limpo in descricao:
            return True
    return False


def _e_do_decimo(verba: Verba) -> bool:
    return _e_so_decimo_terceiro(verba.descricao or "")


def _separar_decimo(segurado: Segurado, folha: Folha) -> List[Segurado]:
    """O bloco do mes e, se ele tiver previdencia de 13o, o bloco do 13o.

    Vao para o 13o a previdencia do 13o e os proventos de 13o -- estes so para
    a conferencia de proventos continuar fechando. Se TODA a previdencia era do
    13o, o bloco inteiro muda de competencia: deixar uma linha do mes com base
    zero seria exportar um registro que a importacao recusa.
    """
    if folha.e_decimo_terceiro or segurado.e_decimo_terceiro:
        return [segurado]
    previdencia = segurado.verbas_previdencia
    da_previdencia = {id(v) for v in previdencia}
    do_decimo = [v for v in segurado.verbas
                 if _e_do_decimo(v)
                 and (v.tipo == "P" or id(v) in da_previdencia)]
    if not any(v.e_previdencia_do_segurado for v in do_decimo):
        return [segurado]

    separadas = {id(v) for v in do_decimo}
    if all(id(v) in separadas for v in previdencia):
        segurado.tipo_folha = TIPO_DECIMO_SEPARADO
        return [segurado]
    decimo = replace(segurado, verbas=do_decimo,
                     tipo_folha=TIPO_DECIMO_SEPARADO)
    segurado.verbas = [v for v in segurado.verbas if id(v) not in separadas]
    return [segurado, decimo]


# ---------------------------------------------------------------------- #
def _aplicar_complementar(folha: Folha, nome: str,
                          linhas: Sequence[LinhaComplementar]) -> None:
    """A base de cada servidor vem do CSV -- quando o CSV e da mesma folha.

    So troca a base de quem tem a MESMA contribuicao nos dois: contribuicao
    diferente quer dizer que o CSV e o PDF nao falam do mesmo desconto, e ai
    nenhum dos dois pode corrigir o outro em silencio -- vira aviso.
    """
    meses = sorted({(l.ano, l.mes) for l in linhas if l.mes != 13})
    competencia = folha.competencia
    if not _mesma_competencia(folha, linhas):
        folha.avisos.append(
            "O arquivo complementar {} é da competência {}, e a folha é de {}."
            " Ele NÃO foi usado — anexe o CSV da mesma competência da "
            "folha.".format(nome, ", ".join("{:02d}/{}".format(m, a)
                                            for a, m in meses), competencia))
        return

    indice: Dict[tuple, LinhaComplementar] = {}
    for linha in linhas:
        indice[(linha.chave, linha.mes == 13)] = linha

    usadas = set()
    ajustados, diferenca = 0, 0.0
    divergentes: List[str] = []
    fora_do_csv: List[str] = []
    fontes_diferentes: List[str] = []
    # O CSV sem nenhuma linha de 13o nao fala do 13o: os 59 segurados de 13o
    # da folha de Nova Olimpia nao estao "fora do CSV", estao fora do assunto.
    tem_decimo = any(linha.mes == 13 for linha in linhas)
    for segurado in folha.segurados:
        chave = (chave_de_matricula(segurado.matricula),
                 segurado.e_decimo_terceiro or folha.e_decimo_terceiro)
        if chave[1] and not tem_decimo:
            continue
        linha = indice.get(chave)
        if linha is None:
            if segurado.contribuicao_do_segurado > 0:
                fora_do_csv.append(segurado.matricula or segurado.nome)
            continue
        usadas.add(chave)
        if abs(linha.segurado - segurado.contribuicao_do_segurado) > 0.011:
            divergentes.append("{} ({} no PDF, {} no CSV)".format(
                segurado.matricula, _moeda(segurado.contribuicao_do_segurado),
                _moeda(linha.segurado)))
            continue
        if not segurado.verbas_previdencia:
            continue
        antes = segurado.base_de_contribuicao
        _definir_base(segurado, linha.base)
        ajustados += 1
        diferenca += abs(linha.base - antes)
        numero = str(getattr(segurado.fonte, "numero", "") or "")
        if linha.fonte and numero and numero != "0" and \
                chave_de_matricula(linha.fonte) != chave_de_matricula(numero):
            fontes_diferentes.append("{} ({} na folha, {} no CSV)".format(
                segurado.matricula, numero, linha.fonte))

    so_no_csv = [l.matricula for c, l in indice.items()
                 if c not in usadas and l.segurado > 0]

    folha.avisos.append(
        "Arquivo complementar {}: a base de {} segurado(s) veio do CSV (a "
        "deduzida da folha diferia {} no total).".format(
            nome, ajustados, _moeda(diferenca)))
    if divergentes:
        folha.avisos.append(
            "{} segurado(s) com contribuição diferente no PDF e no CSV — a "
            "base deles ficou a da folha: {}.".format(
                len(divergentes), _resumir(divergentes)))
    if fora_do_csv:
        folha.avisos.append(
            "{} segurado(s) com contribuição na folha e fora do CSV: "
            "{}.".format(len(fora_do_csv), _resumir(fora_do_csv)))
    if so_no_csv:
        folha.avisos.append(
            "{} matrícula(s) com contribuição no CSV e fora da folha: "
            "{}.".format(len(so_no_csv), _resumir(so_no_csv)))
    if fontes_diferentes:
        folha.avisos.append(
            "{} segurado(s) com fonte pagadora diferente na folha e no CSV: "
            "{}.".format(len(fontes_diferentes), _resumir(fontes_diferentes)))


def _mesma_competencia(folha: Folha,
                       linhas: Sequence[LinhaComplementar]) -> bool:
    """O CSV fala do mesmo mes que a folha? Sem competencia na folha, sim."""
    meses = {(l.ano, l.mes) for l in linhas if l.mes != 13}
    competencia = folha.competencia
    return (competencia is None or not meses
            or (competencia.ano, competencia.mes) in meses)


def fontes_do_complementar(folha: Folha,
                           complementar: Optional[Tuple[str, Sequence[LinhaComplementar]]]
                           ) -> Dict[str, str]:
    """{chave da fonte da folha: codigo} tirado do CSV complementar.

    Nova Olimpia nao tem catalogo de fontes na pasta, mas o CSV dela traz o
    codigo de cada servidor -- e ele bate com o numero da fonte da folha em 343
    dos 347. Uma fonte so recebe codigo quando TODOS os seus servidores que
    estao no CSV dizem o mesmo: dois codigos para o mesmo grupo e sinal de que
    o grupo da folha nao e o do SISPREVWEB, e ai quem decide e a pessoa.
    """
    if not complementar:
        return {}
    _nome, linhas = complementar
    if not _mesma_competencia(folha, linhas):
        return {}
    por_matricula = {chave_de_matricula(l.matricula): l.fonte.strip()
                     for l in linhas if l.fonte.strip()}
    codigos: Dict[str, set] = {}
    for segurado in folha.segurados:
        if segurado.fonte is None:
            continue
        codigo = por_matricula.get(chave_de_matricula(segurado.matricula))
        if codigo:
            codigos.setdefault(segurado.fonte.chave, set()).add(codigo)
    return {chave: next(iter(achados)) for chave, achados in codigos.items()
            if len(achados) == 1}


def _definir_base(segurado: Segurado, base: float) -> None:
    """A base do segurado passa a ser `base`, mexendo so na primeira verba."""
    previdencias = segurado.verbas_previdencia
    outras = sum(v.base or 0.0 for v in previdencias[1:])
    previdencias[0].base = round(base - outras, 2)


def _moeda(valor: float) -> str:
    return "{:,.2f}".format(float(valor or 0)).replace(",", "\x00") \
        .replace(".", ",").replace("\x00", ".")


def _resumir(itens: Sequence, limite: int = 10) -> str:
    textos = [str(i) for i in itens]
    if len(textos) <= limite:
        return ", ".join(textos)
    return "{} ... (+{})".format(", ".join(textos[:limite]), len(textos) - limite)
