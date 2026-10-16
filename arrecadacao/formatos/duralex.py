# -*- coding: utf-8 -*-
"""O "Resumo da Folha de Pagamento - Previdencia" da Dura Lex -- Nova Olimpia.

    Codigo Nome Tipo Func. Funcao Faixa: D-09 Categoria SF IR Salario Base H.Mes
    000419 FULANO DE TAL DOS SANTOS 02 EST.ATIVO AGENTE ... 4.402,23 200
    Admissao: 30/05/2000 ...
    G A N H O S                         D E S C O N T O S
    1 SALARIO MENSAL 30 4.402,23        149 EMPRESTIMO CEF 358,63
    156 DIF. RGA 13o SALARIO. 730,65    210 EMPRESTIMO BCO DO BRASIL 925,99
    Ganhos Descontos Sal.Familia Pasep IRRF FGTS PREVIDENCIA Liquido
    5.993,40 1.284,62 0,00 0,00 92,05 0,00 718,60 3.898,13

O relatorio ja vem FILTRADO pelo regime proprio ("Previdencia: 2-INSTITUTO
PREVIDENCIARIO MUNICIPAL - SIMPREV"), e e isso que o diferencia de todos os
outros: a contribuicao NAO e uma verba. Aparece so como valor, na coluna
"PREVIDENCIA" do rodape do servidor, ja somada a parte do 13o. E a base de
calculo nao aparece por servidor em lugar nenhum -- so nos resumos de cada
secao e no geral:

    TOTAL DAS BASES          Valor Base 11.930,00
    TOTAL DAS BASES - 13 SAL. Valor Base    730,65
    RECOLHIMENTO FUNCIONARIOS  1.670,19
    13 - RECOLHIMENTO FUNCIONARIOS 102,29

O que se faz com isso, e o limite do que da para fazer:

* a parte do 13o e separavel EXATAMENTE: o provento de 13o ("DIF. RGA 13o
  SALARIO. 730,65") e a base do 13o, e a contribuicao dele e a aliquota sobre
  ele -- 730,65 x 14% = 102,29, o numero do resumo. Ela sai num segurado a
  parte, de tipo "13o Salario", que o layout poe na competencia 13;
* a base MENSAL nao. A folha nao diz quais verbas a compoem -- a comissao de
  cargo de um servidor entra, a de outro nao --, entao ela e DEDUZIDA da
  contribuicao: (previdencia - parte do 13o) / aliquota. A Dura Lex TRUNCA o
  desconto ao centavo, entao a base verdadeira esta entre c/aliquota e
  (c + 0,01)/aliquota -- ate 7,1 centavos acima da deduzida, a 14%. Para o
  erro nao se acumular, cada secao e calibrada contra a base que o proprio
  resumo da secao imprime: a sobra vai para a maior base da secao, e a secao
  -- e o municipio -- fecham com o numero da folha. Servidor a servidor, a
  base pode ficar ate esses 7 centavos longe da verdadeira; a contribuicao,
  nao: ela e lida, e nao deduzida.

A aliquota tambem vem da folha: RECOLHIMENTO FUNCIONARIOS / TOTAL DAS BASES
do resumo geral, arredondada a duas casas de percentual.
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Sequence

from ..folha import Competencia, Folha, Segurado, Verba, _e_so_decimo_terceiro, numero
from ..fontes import FonteDaFolha
from ..leitor_pdf import Coluna, Linha, localizar_colunas

NOME = "Dura Lex"

RE_ENTIDADE = re.compile(r"^((?:PREFEITURA|C.MARA)\b.+)$", re.IGNORECASE)
RE_REFERENCIA = re.compile(r"Refer.ncia:\s*(\d{4})/(\d{1,2})", re.IGNORECASE)
RE_TIPO = re.compile(r"Tipo\s+da\s+Folha:\s*(.+?)\s+Refer.ncia:", re.IGNORECASE)
RE_SECAO = re.compile(r"^Se..o:\s*(\d+)\s+(.+)$", re.IGNORECASE)
RE_CABECALHO_SERVIDOR = re.compile(r"^C.digo\s+Nome\s+Tipo\b", re.IGNORECASE)
RE_SERVIDOR = re.compile(r"^(\d+)\s+(.+)$")
RE_ADMISSAO = re.compile(r"^Admiss.o:\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
RE_GANHOS = re.compile(r"^G\s+A\s+N\s+H\s+O\s+S\b")
RE_RODAPE = re.compile(r"^Ganhos\s+Descontos\b.*\bPREVID", re.IGNORECASE)
# "TOTAIS DA SECAO: ...", "TOTAIS DA DIVISAO: ...", "TOTAIS DA FOLHA".
RE_TOTAIS = re.compile(r"^TOTAIS\s+DA\s+(\S+)", re.IGNORECASE)
RE_BASE_MENSAL = re.compile(r"^TOTAL\s+DAS\s+BASES\s+Valor\s+Base\s+([\d.,]+)",
                            re.IGNORECASE)
RE_RECOLHIMENTO = re.compile(r"^RECOLHIMENTO\s+FUNCIONARIOS\s+([\d.,]+)",
                             re.IGNORECASE)
RE_DINHEIRO = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d\d$")

# Ganhos acabam antes de x=295 e descontos comecam depois de x=310, nas duas
# folhas (camara e prefeitura).
MEIO_DA_LINHA = 303.0
ALIQUOTA_PADRAO = 14.0


def pontuar(linhas: Sequence[tuple]) -> int:
    return sum(1 for linha, _p in linhas if RE_RODAPE.match(linha.texto.strip()))


def ler(linhas: Sequence[tuple], folha: Folha) -> List[Segurado]:
    for linha, _pagina in linhas[:12]:
        texto = linha.texto.strip()
        if not folha.entidade and RE_ENTIDADE.match(texto):
            folha.entidade = texto
        achado = RE_REFERENCIA.search(texto)
        if achado and folha.competencia is None:
            folha.competencia = Competencia(ano=int(achado.group(1)),
                                            mes=int(achado.group(2)))
            tipo = RE_TIPO.search(texto)
            folha.tipo = tipo.group(1).strip() if tipo else "Mensal"
    aliquota = _aliquota(linhas)
    return _ler_segurados(linhas, aliquota)


def _aliquota(linhas: Sequence[tuple]) -> float:
    """RECOLHIMENTO FUNCIONARIOS / TOTAL DAS BASES do ULTIMO resumo (o geral)."""
    base = recolhido = None
    for linha, _pagina in linhas:
        texto = linha.texto.strip()
        achado = RE_BASE_MENSAL.match(texto)
        if achado:
            base = numero(achado.group(1))
        achado = RE_RECOLHIMENTO.match(texto)
        if achado:
            recolhido = numero(achado.group(1))
    if base and recolhido:
        return round(recolhido * 100 / base, 2)
    return ALIQUOTA_PADRAO


class _Bloco:
    def __init__(self, segurado: Segurado, secao: str):
        self.segurado = segurado
        self.secao = secao
        self.previdencia: Optional[float] = None
        self.base_mensal = 0.0


def _ler_segurados(linhas: Sequence[tuple], aliquota: float) -> List[Segurado]:
    blocos: List[_Bloco] = []
    atual: Optional[_Bloco] = None
    fonte: Optional[FonteDaFolha] = None
    secao = ""
    base_da_secao: Dict[str, float] = {}
    colunas_rodape: Dict[str, Coluna] = {}
    inicio_do_tipo = 0.0
    esperando = ""
    # O resumo da camara traz tambem o INSS ("RESUMO INSTITUTO NACIONAL DE
    # SEGURIDADE SOCIAL"), com "TOTAL DAS BASES" proprio. So vale o do RPPS.
    no_resumo_do_inss = False
    resumo_da_secao = ""

    for linha, pagina in linhas:
        texto = linha.texto.strip()

        if texto.startswith("*****") and "RESUMO" in texto.upper():
            no_resumo_do_inss = "NACIONAL" in texto.upper()
            continue
        if no_resumo_do_inss:
            continue

        achado = RE_SECAO.match(texto)
        if achado:
            secao = achado.group(1)
            fonte = FonteDaFolha(numero=int(achado.group(1)),
                                 nome=achado.group(2).strip(), bruto=texto)
            continue

        achado = RE_TOTAIS.match(texto)
        if achado:
            # Os totais e o resumo tem linhas com cara de verba e de rodape:
            # nada dali e de servidor. E so o resumo da SECAO conta para a
            # calibragem -- o da divisao vem logo depois, com a soma de varias
            # secoes, e sobrescreveria o da ultima delas.
            atual, esperando = None, ""
            resumo_da_secao = secao if achado.group(1).upper().startswith("SE") else ""
            continue

        achado = RE_BASE_MENSAL.match(texto)
        if achado:
            if resumo_da_secao:
                base_da_secao[resumo_da_secao] = numero(achado.group(1)) or 0.0
                resumo_da_secao = ""
            continue

        if RE_CABECALHO_SERVIDOR.match(texto):
            tipo = next((p for p in linha.palavras if p.texto == "Tipo"), None)
            inicio_do_tipo = tipo.x0 if tipo else 245.0
            esperando = "servidor"
            continue

        if esperando == "servidor":
            esperando = ""
            novo = _abrir(linha, inicio_do_tipo, pagina, fonte, secao)
            # O bloco que atravessa a pagina tem o cabecalho do servidor
            # REIMPRESSO no topo da seguinte: as verbas ficam numa metade e o
            # rodape com a previdencia na outra. A mesma matricula reabrindo
            # antes de o rodape anterior chegar e continuacao, nao outro bloco.
            if (novo is not None and atual is not None
                    and atual.previdencia is None
                    and atual.segurado.matricula == novo.segurado.matricula):
                esperando = "verbas"
                continue
            atual = novo
            if atual is not None:
                blocos.append(atual)
            continue

        if atual is None:
            continue

        achado = RE_ADMISSAO.match(texto)
        if achado:
            atual.segurado.admissao = achado.group(1)
            continue

        if RE_GANHOS.match(texto):
            esperando = "verbas"
            continue

        if RE_RODAPE.match(texto):
            colunas_rodape = localizar_colunas(
                linha, (("previdencia", "PREVIDÊNCIA"),),
                pela_direita=("previdencia",))
            esperando = "rodape"
            continue

        if esperando == "rodape":
            esperando = ""
            atual.previdencia = _valor_na_coluna(linha, colunas_rodape)
            atual = None
            continue

        if esperando == "verbas":
            atual.segurado.verbas.extend(_ler_verbas(linha))

    _calibrar(blocos, base_da_secao, aliquota)
    return _segurados(blocos, aliquota)


def _abrir(linha: Linha, inicio_do_tipo: float, pagina: int,
           fonte: Optional[FonteDaFolha], secao: str) -> Optional[_Bloco]:
    """"000419 FULANO DE TAL DOS SANTOS 02 EST.ATIVO AGENTE ..."

    O nome acaba onde comeca a coluna "Tipo" do cabecalho; depois dela vem o
    tipo de funcionario ("02 EST.ATIVO"), que e a categoria no RPPS.
    """
    antes = [p.texto for p in linha.palavras if p.x0 < inicio_do_tipo - 2]
    depois = [p.texto for p in linha.palavras if p.x0 >= inicio_do_tipo - 2]
    achado = RE_SERVIDOR.match(" ".join(antes))
    if achado is None:
        return None
    segurado = Segurado(matricula=achado.group(1), nome=achado.group(2).strip(),
                        regime=" ".join(depois[1:2]), fonte=fonte,
                        unidade=fonte.nome if fonte else "", pagina=pagina)
    return _Bloco(segurado, secao)


def _valor_na_coluna(linha: Linha, colunas: Dict[str, Coluna]) -> Optional[float]:
    coluna = colunas.get("previdencia")
    if coluna is None:
        return None
    for celula in linha.celulas:
        if abs(celula.x1 - coluna.x1) < 8:
            return numero(celula.texto)
    return None


def _ler_verbas(linha: Linha) -> List[Verba]:
    verbas = []
    for lado, tipo in (([p for p in linha.palavras if p.x0 < MEIO_DA_LINHA], "P"),
                       ([p for p in linha.palavras if p.x0 >= MEIO_DA_LINHA], "D")):
        textos = [p.texto for p in lado]
        if len(textos) < 2 or not RE_DINHEIRO.match(textos[-1]):
            continue
        corpo = textos[:-1]
        referencia = None
        if corpo and re.match(r"^\d+(?:,\d+)?$", corpo[-1]) and len(corpo) > 1:
            referencia = numero(corpo[-1])
            corpo = corpo[:-1]
        # A prefeitura numera as verbas ("1 SALARIO MENSAL"); a camara nao
        # ("SUBSIDIO 30 6.086,94").
        codigo = corpo[0] if corpo and corpo[0].isdigit() else ""
        descricao = " ".join(corpo[1:] if codigo else corpo)
        verbas.append(Verba(codigo=codigo, descricao=descricao, tipo=tipo,
                            referencia=referencia, valor=numero(textos[-1])))
    return verbas


def _do_decimo(bloco: _Bloco) -> float:
    return round(sum(v.valor or 0.0 for v in bloco.segurado.verbas
                     if v.tipo == "P" and _e_so_decimo_terceiro(v.descricao)), 2)


def _contribuicao_do_decimo(bloco: _Bloco, aliquota: float) -> float:
    """A aliquota sobre o 13o, TRUNCADA ao centavo -- como a Dura Lex faz.

    Arredondando, as 59 parcelas de 13o somam 6.193,18; truncando, 6.192,93,
    que e o "13 - RECOLHIMENTO FUNCIONARIOS" do resumo.
    """
    return math.floor(_do_decimo(bloco) * aliquota + 1e-6) / 100


def _base_mensal(bloco: _Bloco, aliquota: float) -> float:
    contribuicao = (bloco.previdencia or 0.0) - _contribuicao_do_decimo(bloco, aliquota)
    return round(max(contribuicao, 0.0) * 100 / aliquota, 2)


def _calibrar(blocos: Sequence[_Bloco], base_da_secao: Dict[str, float],
              aliquota: float) -> None:
    """Guarda em cada bloco a base mensal, com a secao fechando na da folha.

    A sobra so e distribuida se couber no erro do truncamento (um centavo de
    desconto por servidor, 1/aliquota de base); mais que isso e sinal de verba
    que a deducao nao enxerga, e a base fica como deduzida -- o total que a
    tela mostra vai entao divergir do resumo, e e bom que divirja.
    """
    por_secao: Dict[str, List[_Bloco]] = {}
    for bloco in blocos:
        bloco.base_mensal = _base_mensal(bloco, aliquota)
        por_secao.setdefault(bloco.secao, []).append(bloco)

    for secao, grupo in por_secao.items():
        impressa = base_da_secao.get(secao)
        com_base = [b for b in grupo if b.base_mensal]
        if impressa is None or not com_base:
            continue
        sobra = round(impressa - sum(b.base_mensal for b in com_base), 2)
        if abs(sobra) <= len(com_base) * (1.0 / aliquota + 0.01) + 1e-9:
            maior = max(com_base, key=lambda b: b.base_mensal)
            maior.base_mensal = round(maior.base_mensal + sobra, 2)


def _segurados(blocos: Sequence[_Bloco], aliquota: float) -> List[Segurado]:
    """Um segurado do mes por bloco, e um de 13o para quem recebeu 13o."""
    segurados: List[Segurado] = []
    for bloco in blocos:
        mensal = bloco.segurado
        decimo = _do_decimo(bloco)
        contribuicao_decimo = _contribuicao_do_decimo(bloco, aliquota)
        if bloco.previdencia:
            valor = round(bloco.previdencia - contribuicao_decimo, 2)
            if valor > 0:
                mensal.verbas.append(Verba(
                    codigo="", descricao="PREVIDENCIA (rodapé da folha)",
                    tipo="D", referencia=aliquota, base=bloco.base_mensal,
                    valor=valor))
        segurados.append(mensal)

        if decimo and bloco.previdencia:
            verbas_13 = [v for v in mensal.verbas if v.tipo == "P"
                         and _e_so_decimo_terceiro(v.descricao)]
            mensal.verbas = [v for v in mensal.verbas if v not in verbas_13]
            segurados.append(Segurado(
                matricula=mensal.matricula, nome=mensal.nome,
                admissao=mensal.admissao, regime=mensal.regime,
                fonte=mensal.fonte, unidade=mensal.unidade,
                pagina=mensal.pagina, tipo_folha="13º Salário",
                verbas=verbas_13 + [Verba(
                    codigo="", descricao="PREVIDENCIA 13 SALARIO (rodapé da folha)",
                    tipo="D", referencia=aliquota, base=decimo,
                    valor=contribuicao_decimo)]))
    return segurados
