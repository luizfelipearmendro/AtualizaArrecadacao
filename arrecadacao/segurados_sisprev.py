# -*- coding: utf-8 -*-
r"""Troca a matricula da folha pela do cadastro de segurados do SISPREVWEB.

O importador do SISPREVWEB acha o segurado pelo campo 01 -- o "Identificador
do Segurado". A folha traz ali a matricula da PREFEITURA, e o SISPREVWEB guarda
o codigo DELE: quase nunca sao o mesmo numero. Na folha de Colniza de 07/2026,
529 dos 600 e poucos registros voltaram com "segurado nao encontrado" por isso
e so por isso.

O SISPREVWEB exporta o cadastro num CSV (o "MODELO SISPREV"):

    CODIGO_ORGAO;NOME;ANO;MES;REMUNERACAO;...;FONTE_PAG;CATEGORIA;DATA_ADMISSAO
    3995;ABIGAIR FIRMINO;2026;9;0;...;061010 - FUNDEB 70 % - EFETIVOS;EFETIVO;20/03/2008

`CODIGO_ORGAO` e o identificador que o importador procura. As colunas sao
achadas pelo NOME na primeira linha, como no catalogo de fontes -- ver
`fontes.ler_arquivo` --, e as outras sao ignoradas.

**Como casa: nome + data de admissao.** Nenhum dos dois sozinho basta. O nome
se repete (homonimos, e a mesma pessoa com dois vinculos); a admissao se repete
muito mais. Juntos, identificam o vinculo. O nome e comparado sem acento, sem
pontuacao e sem as particulas DA, DE, DO, DAS, DOS e E -- a folha escreve
"RAILDA ALBUQUERQUE DA SILVA" e o SISPREVWEB "RAILDA ALBUQUERQUE SILVA".

O CSV do SISPREVWEB repete o segurado uma vez por fonte pagadora em que ele
aparece: o de Colniza tem 753 linhas e 100 codigos repetidos, com o mesmo nome
e a mesma admissao. Repetido assim e um cadastro so, e nao "mais de um".

Cada linha da folha sai com uma de tres situacoes:

* **Matrícula encontrada** -- casou, e o codigo do SISPREVWEB e o mesmo da
  folha. Nada muda.
* **Matrícula diferente** -- casou, e o codigo e outro. A linha sai com o
  codigo do SISPREVWEB no arquivo ajustado.
* **Segurado não encontrado** -- nao casou, ou casou com mais de um cadastro e
  nao ha como escolher. A matricula da folha fica como esta, e a observacao diz
  por que. Quando ha no cadastro alguem com a MESMA admissao e nome parecido
  -- "MARIA LUCIANA ANTUNES DE OLIVEIRA" na folha, "MARIA LUCIANA ANTUNES
  ALVES" no SISPREVWEB, sobrenome de casada --, o codigo dele vai como
  SUGESTAO, numa coluna propria, para quem conferir decidir.

O programa NAO casa sozinho por nome parecido, nem so pelo nome quando a
admissao diverge. Trocar a matricula
pela de outra pessoa nao da erro na importacao -- credita a contribuicao no
segurado errado, e isso so aparece quando ele pedir a aposentadoria.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .layout import Linha

COLUNA_CODIGO = "CODIGO_ORGAO"
COLUNA_NOME = "NOME"
COLUNA_ADMISSAO = "DATA_ADMISSAO"

ENCONTRADA = "Matrícula encontrada"
DIFERENTE = "Matrícula diferente"
NAO_ENCONTRADO = "Segurado não encontrado"
SITUACOES = (ENCONTRADA, DIFERENTE, NAO_ENCONTRADO)

# O que nao distingue uma pessoa de outra e a folha e o SISPREVWEB escrevem
# cada um de um jeito.
PARTICULAS = frozenset(("DA", "DE", "DO", "DAS", "DOS", "E", "D"))

# Quao parecido o nome tem de ser para virar sugestao, entre quem tem a mesma
# admissao. 0,75 pega o sobrenome trocado no casamento ("ANTUNES DE OLIVEIRA"
# por "ANTUNES ALVES") e deixa de fora quem so divide o dia da posse -- num
# concurso, sao dezenas.
SEMELHANCA_MINIMA = 0.75


class CadastroInvalido(ValueError):
    """O arquivo nao e o CSV de segurados do SISPREVWEB."""


@dataclass(frozen=True)
class SeguradoSisprev:
    codigo: str
    nome: str
    admissao: Optional[date]
    linha: int = 0                # no arquivo, para quem for conferir


@dataclass
class Comparacao:
    """O resultado de uma linha da folha contra o cadastro."""

    linha: Linha
    situacao: str
    codigo_sisprev: str = ""
    observacao: str = ""
    sugestao: str = ""            # "17231 - MARIA LUCIANA ANTUNES ALVES"

    @property
    def matricula_ajustada(self) -> str:
        return self.codigo_sisprev if self.situacao == DIFERENTE \
            else self.linha.matricula


@dataclass
class Resultado:
    arquivo: str
    comparacoes: List[Comparacao] = field(default_factory=list)
    # Quem esta no cadastro e nao apareceu na folha. Nao e erro -- aposentado,
    # exonerado, cedido --, mas e a lista que responde "por que o SISPREVWEB
    # tem 750 e a folha 640".
    fora_da_folha: List[SeguradoSisprev] = field(default_factory=list)

    def contagem(self) -> Dict[str, int]:
        quantos = {s: 0 for s in SITUACOES}
        for comparacao in self.comparacoes:
            quantos[comparacao.situacao] += 1
        return quantos

    def linhas_ajustadas(self) -> List[Linha]:
        """As linhas do layout com o codigo do SISPREVWEB no campo 01."""
        return [replace(c.linha, matricula=c.matricula_ajustada)
                for c in self.comparacoes]


# ---------------------------------------------------------------------- #
# leitura
# ---------------------------------------------------------------------- #
def ler_cadastro(caminho: str) -> List[SeguradoSisprev]:
    """Os segurados do CSV exportado pelo SISPREVWEB."""
    linhas = _linhas_do_csv(Path(caminho))
    if not linhas:
        raise CadastroInvalido("{} está vazio.".format(Path(caminho).name))
    cabecalho = [str(c or "").strip().upper() for c in linhas[0]]
    faltando = [c for c in (COLUNA_CODIGO, COLUNA_NOME, COLUNA_ADMISSAO)
                if c not in cabecalho]
    if faltando:
        raise CadastroInvalido(
            "{} não parece o cadastro de segurados do SISPREVWEB: faltam as "
            "colunas {} na primeira linha.".format(
                Path(caminho).name, ", ".join(faltando)))
    i_codigo = cabecalho.index(COLUNA_CODIGO)
    i_nome = cabecalho.index(COLUNA_NOME)
    i_admissao = cabecalho.index(COLUNA_ADMISSAO)

    segurados: List[SeguradoSisprev] = []
    for numero, campos in enumerate(linhas[1:], start=2):
        campos = list(campos) + [""] * (len(cabecalho) - len(campos))
        codigo = str(campos[i_codigo] or "").strip()
        nome = str(campos[i_nome] or "").strip()
        if not codigo and not nome:
            continue
        segurados.append(SeguradoSisprev(
            codigo=codigo, nome=nome, admissao=data(campos[i_admissao]),
            linha=numero))
    if not segurados:
        raise CadastroInvalido(
            "{} não tem nenhum segurado.".format(Path(caminho).name))
    return segurados


def _linhas_do_csv(caminho: Path) -> List[List[str]]:
    bruto = caminho.read_bytes()
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:                                         # pragma: no cover
        texto = bruto.decode("latin-1", errors="replace")
    amostra = texto[:4000]
    separador = ";" if amostra.count(";") >= amostra.count(",") else ","
    return [l for l in csv.reader(io.StringIO(texto), delimiter=separador)
            if any(str(c).strip() for c in l)]


# ---------------------------------------------------------------------- #
# comparacao
# ---------------------------------------------------------------------- #
def nome_comparavel(texto: str) -> str:
    """"José  da Silva-Júnior" -> "JOSE SILVA JUNIOR"."""
    decomposto = unicodedata.normalize("NFKD", str(texto or ""))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    palavras = re.sub(r"[^A-Za-z0-9]+", " ", sem_acento.upper()).split()
    return " ".join(p for p in palavras if p not in PARTICULAS)


def _semelhanca(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _unicos(segurados: Sequence[SeguradoSisprev]) -> List[SeguradoSisprev]:
    """Um por codigo -- o CSV repete o segurado a cada fonte pagadora."""
    vistos: Dict[str, SeguradoSisprev] = {}
    for segurado in segurados:
        vistos.setdefault(segurado.codigo, segurado)
    return list(vistos.values())


def data(texto) -> Optional[date]:
    """"20/03/2008", "2008-03-20", ou a data que o openpyxl ja entregou."""
    if isinstance(texto, datetime):
        return texto.date()
    if isinstance(texto, date):
        return texto
    limpo = str(texto or "").strip().split(" ")[0]
    for forma in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(limpo, forma).date()
        except ValueError:
            continue
    return None


def _mesma_matricula(a: str, b: str) -> bool:
    """"000984" na folha e "984" no SISPREVWEB sao a mesma matricula."""
    a, b = str(a or "").strip(), str(b or "").strip()
    return (a.lstrip("0") or a) == (b.lstrip("0") or b)


def _texto_data(valor: Optional[date]) -> str:
    return valor.strftime("%d/%m/%Y") if valor else "sem data"


def comparar(linhas: Sequence[Linha], cadastro: Sequence[SeguradoSisprev],
             arquivo: str = "") -> Resultado:
    """Casa cada linha da folha com o cadastro, por nome + admissao."""
    cadastro = _unicos(cadastro)
    por_chave: Dict[Tuple[str, Optional[date]], List[SeguradoSisprev]] = {}
    por_nome: Dict[str, List[SeguradoSisprev]] = {}
    por_admissao: Dict[Optional[date], List[SeguradoSisprev]] = {}
    for segurado in cadastro:
        nome = nome_comparavel(segurado.nome)
        por_chave.setdefault((nome, segurado.admissao), []).append(segurado)
        por_nome.setdefault(nome, []).append(segurado)
        por_admissao.setdefault(segurado.admissao, []).append(segurado)

    resultado = Resultado(arquivo=arquivo)
    usados: set = set()
    # Um codigo do SISPREVWEB so pode ir para UMA linha: duas linhas com o
    # mesmo identificador na mesma competencia o importador recusa, e somar as
    # duas num segurado so seria inventar. A segunda vira "nao encontrado".
    dono_do_codigo: Dict[str, Linha] = {}

    for linha in linhas:
        nome = nome_comparavel(linha.nome)
        admissao = data(linha.admissao)
        candidatos = por_chave.get((nome, admissao), []) if admissao else []

        # A mesma pessoa com dois vinculos admitidos no mesmo dia: se a
        # matricula da folha e uma delas, e essa; senao nao ha como escolher.
        if len(candidatos) > 1:
            iguais = [c for c in candidatos
                      if _mesma_matricula(c.codigo, linha.matricula)]
            if len(iguais) == 1:
                candidatos = iguais
            else:
                livres = [c for c in candidatos if c.codigo not in dono_do_codigo]
                if len(livres) == 1:
                    candidatos = livres

        if len(candidatos) == 1:
            achado = candidatos[0]
            if achado.codigo in dono_do_codigo:
                resultado.comparacoes.append(Comparacao(
                    linha, NAO_ENCONTRADO, achado.codigo,
                    "o código {} do SISPREVWEB já foi para outra linha da "
                    "folha (matrícula {})".format(
                        achado.codigo,
                        dono_do_codigo[achado.codigo].matricula)))
                continue
            dono_do_codigo[achado.codigo] = linha
            usados.add(achado.linha)
            igual = _mesma_matricula(achado.codigo, linha.matricula)
            resultado.comparacoes.append(Comparacao(
                linha, ENCONTRADA if igual else DIFERENTE, achado.codigo))
            continue

        if len(candidatos) > 1:
            observacao = "mais de um cadastro com o mesmo nome e admissão: " \
                "códigos {}".format(", ".join(c.codigo for c in candidatos))
        elif not admissao:
            observacao = "a folha não trouxe a data de admissão"
            homonimos = por_nome.get(nome, [])
            if homonimos:
                observacao += "; o nome existe no SISPREVWEB ({})".format(
                    "; ".join("código {}, admissão {}".format(
                        h.codigo, _texto_data(h.admissao)) for h in homonimos))
        elif nome in por_nome:
            observacao = "o nome existe no SISPREVWEB com outra admissão: {}" \
                .format("; ".join("código {}, admissão {}".format(
                    h.codigo, _texto_data(h.admissao))
                    for h in por_nome[nome]))
        else:
            observacao = "nome não encontrado no SISPREVWEB"
        resultado.comparacoes.append(Comparacao(
            linha, NAO_ENCONTRADO, "", observacao,
            _sugerir(nome, por_admissao.get(admissao, []) if admissao else [],
                     dono_do_codigo)))

    resultado.fora_da_folha = [s for s in cadastro if s.linha not in usados]
    return resultado


def _sugerir(nome: str, mesma_admissao: Sequence[SeguradoSisprev],
             dono_do_codigo: Dict[str, Linha]) -> str:
    """O cadastro de mesma admissao com o nome mais parecido, se houver um."""
    notas = sorted(((_semelhanca(nome, nome_comparavel(s.nome)), s)
                    for s in mesma_admissao if s.codigo not in dono_do_codigo),
                   key=lambda par: -par[0])
    if not notas or notas[0][0] < SEMELHANCA_MINIMA:
        return ""
    melhor = notas[0][1]
    return "{} - {}".format(melhor.codigo, melhor.nome)
