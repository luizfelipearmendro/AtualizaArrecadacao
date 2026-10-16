# -*- coding: utf-8 -*-
r"""O catalogo de fontes pagadoras do SISPREVWEB, e como a folha casa com ele.

A coluna "Identificador da Fonte Pagadora (Codigo de Integracao)" e NUMERICA e
aponta para um cadastro que vive no SISPREVWEB -- nao na folha. O SISPREVWEB
exporta esse cadastro em duas colunas, FONTE_PAG_ID e NOME; e desse arquivo que
este modulo vive.

O QUE A FOLHA TRAZ
------------------
A folha agrupa os servidores por fonte, e escreve o grupo como cabecalho, logo
abaixo da estrutura ADM:

    1.02.001 - GABINETE DO EXECUTIVO
    2 - 1 - 2002 -GABINETE EFETIVOS F 1.500      <- a fonte
    Funcionario(a)  Matricula  ...

Tres campos: a ordem do grupo na folha (2), o NUMERO da fonte (1) e o nome
(2002 -GABINETE EFETIVOS F 1.500). No SISPREVWEB a mesma fonte se chama
"001 - 2002 -GABINETE EFETIVOS F 1.500" e tem codigo 5085. Ou seja: o numero da
folha, com zeros a esquerda, e o comeco do nome do catalogo.

COMO CASA
---------
Pelo numero E pelo nome, nessa ordem:

1. numero igual e nome igual (sem acento, sem pontuacao, sem caixa) -- 50 das
   59 fontes da folha mensal de Aripuana;
2. numero igual e nome do catalogo COMECANDO pelo da folha: o PDF trunca nome
   longo na largura da coluna, e "2072- SAUDE VIG EPID. EFETIVOS" e o mesmo
   "2072- SAUDE VIG EPID. EFETIVOS F.2.600.0000605" -- mais 1;
3. numero igual e um unico candidato, com o nome diferente: casa, mas fica
   marcado, porque nome diferente e a assinatura de fonte trocada.

Fora isso NAO casa sozinho, e nao ha o que inventar:

* o mesmo numero com varios candidatos -- o catalogo de Aripuana tem
  "351 - 2061 - SAUDE - SAUDE BUCAL" duas vezes, com codigos 5144 e 5048, e
  ainda as variantes "- FERIAS" e "- AUX. DOENCA". Qual das duas e a certa e
  informacao que nao esta em lugar nenhum do arquivo; a tela mostra as duas e
  quem sabe escolhe;
* o numero que nao existe no catalogo -- 5 das 59, fontes novas que ainda nao
  foram exportadas. Quem sabe digita o codigo.

As duas escolhas ficam gravadas por municipio e sao reaproveitadas na folha
seguinte.

POR QUE MUNICIPIO
-----------------
Sao 29 prefeituras, e os nomes das fontes se repetem entre elas. O catalogo e
guardado por municipio e o casamento so olha o do municipio escolhido; sem
isso, "001 - 2002 - GABINETE EFETIVOS" de uma cidade casaria com o codigo de
outra -- e um codigo de fonte errado nao rejeita a importacao, ele credita a
contribuicao na fonte errada, que e um problema descoberto meses depois, na
conciliacao.

ONDE MORA
---------
`%LOCALAPPDATA%\AtualizaArrecadacao\catalogo_fontes.json`, e nao ao lado do
executavel, porque a pasta do programa e substituida inteira a cada versao --
era assim que o cadastro se perderia na primeira atualizacao.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_log = logging.getLogger(__name__)

ARQUIVO = "catalogo_fontes.json"

# As duas colunas do arquivo exportado do SISPREVWEB. Sao exigidas pelo nome, e
# nao pela posicao: quem exporta pode reordenar, e uma planilha com as colunas
# trocadas importaria nome como codigo sem reclamar de nada.
COLUNA_CODIGO = "FONTE_PAG_ID"
COLUNA_NOME = "NOME"

# "001 - 2002 -GABINETE EFETIVOS F 1.500" -> numero 1, resto o nome
RE_NOME_CATALOGO = re.compile(r"^(\d+)\s*-\s*(.*)$")
# "... MAC (RECURSO PRÓPRIO)" -> "... MAC": o complemento que so a folha tem.
RE_SUFIXO_ENTRE_PARENTESES = re.compile(r"\s*\([^()]*\)\s*$")

# Como a linha da fonte aparece na folha:
# "2 - 1 - 2002 -GABINETE EFETIVOS F 1.500"
#  ^   ^   ^-- o nome, que comeca pelo codigo do projeto/atividade
#  |   +------ o numero da fonte: o que casa com o catalogo
#  +---------- a ordem do grupo na folha, que nao serve para nada aqui
# "<ordem na folha> - <numero da fonte> - <nome>". O nome NAO precisa comecar
# com numero: na prefeitura ele comeca ("2 - 1 - 2002 -GABINETE EFETIVOS"),
# mas na camara nao ("3 - 2-Servidores Efetivos"), e exigir os 3 digitos
# deixava a folha da camara inteira sem fonte pagadora. Os espacos em volta
# dos tracinhos tambem sao opcionais, pelo mesmo motivo.
RE_FONTE_NA_FOLHA = re.compile(r"^(\d+)\s*-\s*(\d+)\s*-\s*(\S.*)$")


# ---------------------------------------------------------------------- #
# apoio
# ---------------------------------------------------------------------- #
def normalizar(texto: str) -> str:
    """Caixa alta, sem acento e sem pontuacao -- a forma que se compara.

    A folha escreve "SINFRA - GESTAO" com til e o SISPREVWEB sem; uma escreve
    "F.1.500.1002" e a outra "F 1.500.1002". Comparar o texto cru faz 59 fontes
    virarem 59 pendencias.
    """
    decomposto = unicodedata.normalize("NFKD", str(texto or ""))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", sem_acento.upper()).split())


def _numero_e_resto(nome: str) -> Tuple[Optional[int], str]:
    achado = RE_NOME_CATALOGO.match((nome or "").strip())
    if not achado:
        return (None, (nome or "").strip())
    return (int(achado.group(1)), achado.group(2).strip())


# ---------------------------------------------------------------------- #
# modelos
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class Fonte:
    """Uma linha do arquivo exportado do SISPREVWEB."""

    codigo: str                   # FONTE_PAG_ID: "5085"
    nome: str                     # NOME: "001 - 2002 -GABINETE EFETIVOS F 1.500"

    @property
    def numero(self) -> Optional[int]:
        return _numero_e_resto(self.nome)[0]

    @property
    def comparavel(self) -> str:
        """O nome sem o numero da frente, normalizado."""
        return normalizar(_numero_e_resto(self.nome)[1])


@dataclass(frozen=True)
class FonteDaFolha:
    """O cabecalho de grupo que a folha traz."""

    numero: int
    nome: str                     # "2002 -GABINETE EFETIVOS F 1.500"
    bruto: str = ""               # a linha inteira, para quem conferir no PDF
    # Fonte que a folha NAO traz: o PDF inteiro e de uma fonte so e nao
    # escreve qual. Acontece na folha da camara -- das tres que temos, duas
    # vem sem grupo nenhum. Nao tendo numero para procurar no catalogo, a
    # escolha e feita a mao, e por isso a marca: ver `Cadastro.casar`.
    folha_inteira: bool = False

    @property
    def chave(self) -> str:
        """Identifica a fonte entre folhas do mesmo municipio."""
        return "{}|{}".format(self.numero, normalizar(self.nome))

    def __str__(self) -> str:
        if self.folha_inteira:
            return self.nome
        return "{:03d} - {}".format(self.numero, self.nome)


# Como o codigo foi obtido. Vai para a tela, porque "casou pelo numero mas o
# nome nao bate" e "casou inteiro" merecem confianca diferente.
POR_NOME = "catálogo"
POR_TRUNCADO = "catálogo (nome truncado na folha)"
POR_SEM_SUFIXO = "catálogo (sem o complemento entre parênteses)"
POR_NUMERO = "catálogo (só o número — o nome não confere)"
POR_ESCOLHA = "escolhido por você"
# O CSV que o municipio manda junto ja traz o codigo de cada servidor -- ver
# `regras.fontes_do_complementar`. Vale onde nao ha catalogo nem escolha.
POR_COMPLEMENTAR = "arquivo complementar do município"
SEM_CATALOGO = "catálogo não importado"
AMBIGUO = "mais de uma fonte com este número"
AUSENTE = "número não existe no catálogo"
SEM_GRUPO = "a folha não diz a fonte — escolha no catálogo"


@dataclass
class Correspondencia:
    """O que se sabe sobre a fonte de um grupo da folha."""

    fonte: FonteDaFolha
    codigo: str = ""
    origem: str = ""
    candidatos: List[Fonte] = field(default_factory=list)

    @property
    def resolvida(self) -> bool:
        return bool(self.codigo)

    @property
    def confiavel(self) -> bool:
        """Casou inteiro, ou foi a pessoa que escolheu."""
        return self.origem in (POR_NOME, POR_TRUNCADO, POR_SEM_SUFIXO,
                               POR_ESCOLHA)


# ---------------------------------------------------------------------- #
# o cadastro
# ---------------------------------------------------------------------- #
@dataclass
class Cadastro:
    """O catalogo de cada municipio, mais as escolhas feitas a mao."""

    catalogo: Dict[str, List[Fonte]] = field(default_factory=dict)
    escolhas: Dict[str, Dict[str, str]] = field(default_factory=dict)
    caminho: Optional[Path] = None

    # ------------------------------------------------------------------ #
    # disco
    # ------------------------------------------------------------------ #
    @classmethod
    def carregar(cls, pasta: Path) -> "Cadastro":
        """Le o cadastro. Arquivo ausente ou defeituoso vira cadastro vazio."""
        caminho = Path(pasta) / ARQUIVO
        cadastro = cls(caminho=caminho)
        try:
            bruto = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cadastro
        if not isinstance(bruto, dict):
            return cadastro

        for municipio, fontes in (bruto.get("catalogo") or {}).items():
            lidas = []
            for item in fontes if isinstance(fontes, list) else []:
                try:
                    codigo = str(item["codigo"]).strip()
                    nome = str(item["nome"]).strip()
                except (TypeError, KeyError):
                    continue
                if codigo and nome:
                    lidas.append(Fonte(codigo=codigo, nome=nome))
            if lidas:
                cadastro.catalogo[str(municipio)] = lidas

        for municipio, escolhas in (bruto.get("escolhas") or {}).items():
            if isinstance(escolhas, dict):
                cadastro.escolhas[str(municipio)] = {
                    str(c): str(v).strip() for c, v in escolhas.items()
                    if str(v).strip()}
        return cadastro

    def salvar(self) -> bool:
        """Grava. False se nao deu (disco cheio, perfil sem escrita)."""
        if self.caminho is None:
            return False
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            self.caminho.write_text(
                json.dumps({
                    "versao": 2,
                    "catalogo": {
                        municipio: [{"codigo": f.codigo, "nome": f.nome}
                                    for f in fontes]
                        for municipio, fontes in sorted(self.catalogo.items())},
                    "escolhas": {municipio: dict(sorted(escolhas.items()))
                                 for municipio, escolhas
                                 in sorted(self.escolhas.items())},
                }, indent=1, ensure_ascii=False),
                encoding="utf-8")
            return True
        except OSError as erro:
            _log.warning("catalogo de fontes nao gravado: %s", erro)
            return False

    # ------------------------------------------------------------------ #
    # o catalogo
    # ------------------------------------------------------------------ #
    def fontes_de(self, municipio: str) -> List[Fonte]:
        return self.catalogo.get(municipio or "", [])

    def municipios_com_catalogo(self) -> List[str]:
        return sorted(m for m, f in self.catalogo.items() if f)

    def definir_catalogo(self, municipio: str, fontes: Sequence[Fonte]) -> None:
        """Substitui o catalogo do municipio. Nao mistura com o que havia.

        Substituir, e nao somar: o arquivo exportado e a verdade inteira
        daquele municipio, e somar deixaria para sempre a fonte que foi
        removida do SISPREVWEB -- casando, e creditando em codigo que nao
        existe mais.
        """
        if municipio:
            self.catalogo[municipio] = list(fontes)

    def esquecer(self, municipio: str) -> None:
        self.catalogo.pop(municipio, None)
        self.escolhas.pop(municipio, None)

    # ------------------------------------------------------------------ #
    # as escolhas feitas a mao
    # ------------------------------------------------------------------ #
    def escolher(self, municipio: str, fonte: FonteDaFolha, codigo: str) -> None:
        """Guarda o codigo que a pessoa informou para esta fonte."""
        codigo = (codigo or "").strip()
        escolhas = self.escolhas.setdefault(municipio or "", {})
        if codigo:
            escolhas[fonte.chave] = codigo
        else:
            escolhas.pop(fonte.chave, None)

    def escolha_de(self, municipio: str, fonte: FonteDaFolha) -> str:
        return self.escolhas.get(municipio or "", {}).get(fonte.chave, "")

    # ------------------------------------------------------------------ #
    # o casamento
    # ------------------------------------------------------------------ #
    def casar(self, municipio: str, fonte: FonteDaFolha) -> Correspondencia:
        """O codigo desta fonte, e por que ele foi escolhido."""
        escolhido = self.escolha_de(municipio, fonte)
        if fonte.folha_inteira:
            # Sem numero no PDF nao ha o que procurar: os candidatos sao TODAS
            # as fontes do municipio, e quem escolhe e a pessoa. A escolha fica
            # gravada pela chave, entao a folha do mes seguinte ja vem
            # resolvida.
            todas = self._catalogo_ordenado(municipio, fonte.nome)
            return Correspondencia(
                fonte=fonte, codigo=escolhido,
                origem=POR_ESCOLHA if escolhido else (
                    SEM_CATALOGO if not todas else SEM_GRUPO),
                candidatos=todas)

        candidatos = [f for f in self.fontes_de(municipio)
                      if f.numero == fonte.numero]
        if escolhido:
            return Correspondencia(fonte=fonte, codigo=escolhido,
                                   origem=POR_ESCOLHA, candidatos=candidatos)

        if not self.fontes_de(municipio):
            return Correspondencia(fonte=fonte, origem=SEM_CATALOGO)
        if not candidatos:
            return Correspondencia(fonte=fonte, origem=AUSENTE)

        alvo = normalizar(fonte.nome)
        exatos = [f for f in candidatos if f.comparavel == alvo]
        if len(exatos) == 1:
            return Correspondencia(fonte=fonte, codigo=exatos[0].codigo,
                                   origem=POR_NOME, candidatos=candidatos)
        if not exatos:
            # A folha as vezes acrescenta ao nome um complemento que o catalogo
            # nao tem: "MEDIA E ALTA COMPLEXIDADE- MAC (RECURSO PROPRIO)" na
            # folha de Rosario, "MEDIA E ALTA COMPLEXIDADE- MAC" no SISPREVWEB.
            # Tirar o parenteses do FIM e comparar de novo so vale quando sobra
            # UM candidato -- continua sendo casamento por nome, que e o
            # criterio confiavel, e nao palpite.
            sem_sufixo = normalizar(RE_SUFIXO_ENTRE_PARENTESES.sub("", fonte.nome))
            iguais = [f for f in candidatos if f.comparavel == sem_sufixo]
            if sem_sufixo != alvo and len(iguais) == 1:
                return Correspondencia(fonte=fonte, codigo=iguais[0].codigo,
                                       origem=POR_SEM_SUFIXO,
                                       candidatos=candidatos)

            # o PDF corta o nome na largura da coluna
            comecam = [f for f in candidatos if f.comparavel.startswith(alvo)]
            if len(comecam) == 1:
                return Correspondencia(fonte=fonte, codigo=comecam[0].codigo,
                                       origem=POR_TRUNCADO,
                                       candidatos=candidatos)
            if not comecam and len(candidatos) == 1:
                return Correspondencia(fonte=fonte, codigo=candidatos[0].codigo,
                                       origem=POR_NUMERO,
                                       candidatos=candidatos)

        return Correspondencia(fonte=fonte, origem=AMBIGUO,
                               candidatos=exatos or candidatos)

    def _catalogo_ordenado(self, municipio: str,
                           entidade: str) -> List[Fonte]:
        """O catalogo do municipio, com o mais provavel primeiro.

        Quem precisa desta lista esta resolvendo uma folha que nao diz a fonte,
        e a folha da camara e o caso de longe mais comum. Entao, quando a
        entidade do PDF fala em camara, as fontes do catalogo que tambem falam
        sobem para o topo -- num catalogo de 60 linhas isso e a diferenca entre
        achar e rolar. O resto da lista continua inteiro logo abaixo: a
        sugestao e um atalho, e nao um filtro.
        """
        todas = list(self.fontes_de(municipio))
        texto = normalizar(entidade)
        # So palavras que de fato separam uma fonte das outras. Usar todas as
        # palavras da entidade nao serviria: "CAMARA MUNICIPAL DE BARRA DO
        # GARCAS" tem "municipal" e "barra", que casam com metade do catalogo
        # de Barra do Garcas e sugerem tudo -- que e o mesmo que nao sugerir.
        # Em CAIXA ALTA: e assim que `normalizar` devolve os dois lados.
        pistas = [p for p in ("CAMARA", "LEGISLATIV", "VEREADOR")
                  if p in texto]
        if not pistas:
            return todas
        provaveis = [f for f in todas
                     if any(p in f.comparavel for p in pistas)]
        if not provaveis:
            return todas
        return provaveis + [f for f in todas if f not in provaveis]

    def casar_todas(self, municipio: str,
                    fontes: Iterable[FonteDaFolha]) -> Dict[str, Correspondencia]:
        """Uma correspondencia por fonte distinta, indexada pela chave."""
        resultado: Dict[str, Correspondencia] = {}
        for fonte in fontes:
            if fonte.chave not in resultado:
                resultado[fonte.chave] = self.casar(municipio, fonte)
        return resultado


# ---------------------------------------------------------------------- #
# importacao do arquivo exportado do SISPREVWEB
# ---------------------------------------------------------------------- #
class ArquivoInvalido(Exception):
    """O arquivo nao tem a cara do que o SISPREVWEB exporta."""


def _indice_das_colunas(cabecalho: Sequence) -> Tuple[int, int]:
    """Onde estao FONTE_PAG_ID e NOME. Levanta se faltar alguma.

    Pelo nome e nao pela posicao, e sem exigir acento nem caixa: a planilha
    passa por mais de uma mao antes de chegar aqui.
    """
    limpos = [normalizar(c) for c in cabecalho]
    try:
        indice_codigo = limpos.index(normalizar(COLUNA_CODIGO))
    except ValueError:
        indice_codigo = -1
    try:
        indice_nome = limpos.index(normalizar(COLUNA_NOME))
    except ValueError:
        indice_nome = -1

    if indice_codigo < 0 or indice_nome < 0:
        faltando = [c for c, i in ((COLUNA_CODIGO, indice_codigo),
                                   (COLUNA_NOME, indice_nome)) if i < 0]
        raise ArquivoInvalido(
            "O arquivo precisa das colunas {} e {}, com esses nomes na "
            "primeira linha.\n\nFaltou: {}.\nEncontrei: {}.".format(
                COLUNA_CODIGO, COLUNA_NOME, ", ".join(faltando),
                ", ".join(str(c) for c in cabecalho[:8]) or "(nada)"))
    return (indice_codigo, indice_nome)


def _linhas_do_csv(caminho: Path) -> List[List[str]]:
    """Le o CSV adivinhando separador e codificacao.

    O SISPREVWEB exporta com BOM e ponto-e-virgula; a mesma planilha reaberta e
    salva no Excel de outra maquina sai em cp1252 e, as vezes, com virgula.
    """
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = caminho.read_text(encoding=codificacao)
            break
        except UnicodeDecodeError:
            continue
        except OSError as erro:
            # Arquivo sumido, sem permissao ou aberto de forma exclusiva: dizer
            # "nao consegui ler como texto" mandaria procurar codificacao onde
            # o problema e outro.
            raise ArquivoInvalido("{}: {}".format(caminho.name, erro))
    else:
        raise ArquivoInvalido(
            "Não reconheci a codificação do arquivo. Salve como CSV UTF-8 ou "
            "como .xlsx e tente de novo.")

    amostra = texto[:4000]
    separador = ";" if amostra.count(";") >= amostra.count(",") else ","
    return [linha for linha in csv.reader(io.StringIO(texto),
                                          delimiter=separador)]


def _linhas_do_xlsx(caminho: Path) -> List[List]:
    try:
        import openpyxl
    except ImportError as erro:        # pragma: no cover
        raise ArquivoInvalido(
            "Falta a biblioteca openpyxl para ler .xlsx: {}".format(erro))
    livro = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        aba = livro[livro.sheetnames[0]]
        return [list(linha) for linha in aba.iter_rows(values_only=True)]
    finally:
        livro.close()


def ler_arquivo(caminho: Path) -> Tuple[List[Fonte], List[str]]:
    """Le o arquivo exportado. Devolve (fontes, avisos).

    Os avisos contam o que foi deixado de fora e por que -- linha sem codigo,
    codigo repetido. Importar 1.215 fontes e dizer so "pronto" esconde
    justamente o que precisaria ser olhado.
    """
    caminho = Path(caminho)
    if caminho.suffix.lower() in (".xlsx", ".xlsm"):
        linhas = _linhas_do_xlsx(caminho)
    else:
        linhas = _linhas_do_csv(caminho)

    linhas = [l for l in linhas if l and any(
        str(c).strip() for c in l if c is not None)]
    if not linhas:
        raise ArquivoInvalido("O arquivo está vazio.")

    indice_codigo, indice_nome = _indice_das_colunas(linhas[0])

    fontes: List[Fonte] = []
    vistos: Dict[str, str] = {}
    sem_codigo = 0
    repetidos: List[str] = []
    for linha in linhas[1:]:
        codigo = str(linha[indice_codigo]).strip() if \
            len(linha) > indice_codigo and linha[indice_codigo] is not None else ""
        nome = str(linha[indice_nome]).strip() if \
            len(linha) > indice_nome and linha[indice_nome] is not None else ""
        # "5085.0": o Excel guarda numero inteiro como float, e o codigo e texto
        if codigo.endswith(".0") and codigo[:-2].isdigit():
            codigo = codigo[:-2]
        if not codigo or not nome:
            sem_codigo += 1
            continue
        if codigo in vistos:
            if vistos[codigo] != nome:
                repetidos.append(codigo)
            continue
        vistos[codigo] = nome
        fontes.append(Fonte(codigo=codigo, nome=nome))

    if not fontes:
        raise ArquivoInvalido(
            "Nenhuma fonte foi lida. As colunas {} e {} existem, mas estão "
            "vazias.".format(COLUNA_CODIGO, COLUNA_NOME))

    avisos: List[str] = []
    if sem_codigo:
        avisos.append("{} linha(s) sem código ou sem nome, ignoradas.".format(
            sem_codigo))
    if repetidos:
        avisos.append(
            "{} código(s) repetidos com nomes diferentes; ficou o primeiro de "
            "cada: {}.".format(len(repetidos), ", ".join(repetidos[:6])))
    sem_numero = sum(1 for f in fontes if f.numero is None)
    if sem_numero:
        avisos.append(
            "{} fonte(s) não começam com número e por isso não casam sozinhas "
            "com a folha — só por escolha manual.".format(sem_numero))
    return (fontes, avisos)
