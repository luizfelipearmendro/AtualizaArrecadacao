# -*- coding: utf-8 -*-
"""O que se le de uma folha de pagamento: competencia, segurado e contribuicao.

Modelos sem dependencia de PDF nem de planilha, de proposito: `extracao` os
preenche lendo o PDF, `layout` os traduz para as colunas do arquivo de
importacao, e a tela so os exibe. Trocar o gerador da folha mexe em `extracao`;
trocar o layout do SISPREVWEB mexe em `layout`; nenhum dos dois mexe aqui.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .fontes import FonteDaFolha

# O unico valor que a Categoria assume nesta prefeitura. O layout admite
# Efetivo, Comissionado, Estavel, Estavel/Quadro Suplementar e Eletivo, e a
# folha tem colunas que PARECEM responder isso -- "Situacao" (Ativo,
# Exonerado) e "Forma de ingresso" -- mas nenhuma delas e a categoria: a
# primeira e a situacao funcional e a segunda e como a pessoa entrou. Quem
# confere a folha ja sabia; quem le o codigo depois, nao -- e e por isso que
# esta escrito aqui, e nao deduzido de uma coluna que por acaso bate.
CATEGORIA_PADRAO = "Efetivo"

CATEGORIAS_ACEITAS = ("Efetivo", "Comissionado", "Estável",
                      "Estável/Quadro Suplementar", "Eletivo")

# Mes 13 e o 13o salario -- e a propria folha que diz qual e, no subtitulo
# abaixo do "FOLHA DE PAGAMENTO - 08/2026".
MES_DECIMO_TERCEIRO = 13


@dataclass(frozen=True)
class Competencia:
    """Ano e mes que vao nas colunas 03 e 04 do layout."""

    ano: int
    mes: int

    def __str__(self) -> str:
        return "{:02d}/{:04d}".format(self.mes, self.ano)

    @property
    def valida(self) -> bool:
        return 1900 <= self.ano <= 2999 and 1 <= self.mes <= 13


@dataclass
class Verba:
    """Uma linha do calculo mensal: o que foi pago ou descontado."""

    codigo: str
    descricao: str
    tipo: str                    # P provento, D desconto, N nota/base, B, I
    referencia: Optional[float] = None
    base: Optional[float] = None
    integral: Optional[float] = None
    valor: Optional[float] = None

    @property
    def e_previdencia_do_segurado(self) -> bool:
        """Desconto previdenciario na folha -- a coluna 06 do layout.

        Reconhecida pela DESCRICAO, e nao pela faixa de codigo. A tentacao e
        dizer "codigo 88xx e previdencia", e nesta folha isso pega junto as
        consignacoes 8859, 8865, 8866 e 8871 -- emprestimo de banco entrando
        como contribuicao previdenciaria. Ja pela descricao as previdencias sao
        8850, 8851 (efetivo), 8857 (sobre ferias), 8873 (auxilio-doenca), 8844
        (13o adiantamento) e 8847 (13o rescisao), e nenhuma consignacao se
        chama previdencia.
        """
        return self.tipo == "D" and "PREVIDENCIA" in _caixa_alta_sem_acento(self.descricao)


@dataclass
class Segurado:
    """Um bloco de funcionario da folha, com o que dele interessa a arrecadacao."""

    matricula: str = ""
    nome: str = ""
    cpf: str = ""
    situacao: str = ""            # Ativo, Exonerado -- situacao FUNCIONAL
    estrutura: str = ""           # "1.02.001": a chave da fonte pagadora
    unidade: str = ""             # "GABINETE DO EXECUTIVO": so para leitura
    admissao: str = ""
    regime: str = ""              # "RPPS - Regime proprio de previdencia social"
    ingresso: str = ""            # "Nomeacao para cargo efetivo"
    cargo: str = ""
    # O grupo de fonte pagadora em que a folha pos este servidor. E' o que
    # casa com o cadastro do SISPREVWEB -- ver `arrecadacao.fontes`. Mais fino
    # que a estrutura: a folha mensal tem 22 estruturas e 59 fontes.
    fonte: Optional[FonteDaFolha] = None
    verbas: List[Verba] = field(default_factory=list)
    pagina: int = 0

    # ------------------------------------------------------------------ #
    @property
    def verbas_previdencia(self) -> List[Verba]:
        return [v for v in self.verbas if v.e_previdencia_do_segurado]

    @property
    def base_de_contribuicao(self) -> float:
        """Coluna 05: a base de calculo do desconto previdenciario.

        Somada, e nao a da primeira verba. Cinquenta servidores desta folha tem
        DUAS previdencias no mesmo mes -- quem entrou em auxilio-doenca no meio
        do mes desconta 8850 sobre os dias trabalhados e 8873 sobre o
        beneficio, e quem saiu de ferias desconta 8850 e 8857. Levar so uma das
        duas recolhe menos do que foi descontado em folha.
        """
        return round(sum(v.base or 0.0 for v in self.verbas_previdencia), 2)

    @property
    def contribuicao_do_segurado(self) -> float:
        """Coluna 06: o desconto previdenciario em folha."""
        return round(sum(v.valor or 0.0 for v in self.verbas_previdencia), 2)

    @property
    def total_proventos(self) -> float:
        """Tudo o que foi pago no mes -- o "Total de proventos" do rodape.

        NAO vai no arquivo: e conferencia. Existe porque a pergunta aparece
        toda vez que alguem compara a tela com a folha -- a folha mensal de
        08/2026 fecha 4.767.480,36 de proventos e 4.126.327,68 de base, e a
        diferenca assusta quem nao sabe de onde ela vem. Sao coisas
        diferentes: proventos e o que se pagou; base e o que a folha usou para
        calcular o desconto previdenciario, e so isso e que o layout pede.

        A diferenca sao as verbas que nao compoem a base -- aulas excedentes,
        horas extras, 1/3 de ferias, insalubridade, gratificacoes -- e quem
        tem cargo efetivo exercendo comissionado, que contribui sobre o
        vencimento do efetivo. Com os dois numeros lado a lado na tela, isso
        se ve; com um so, vira desconfianca da leitura do PDF.
        """
        return round(sum(v.valor or 0.0 for v in self.verbas if v.tipo == "P"), 2)

    @property
    def tem_previdencia(self) -> bool:
        return bool(self.verbas_previdencia)

    @property
    def codigos_previdencia(self) -> str:
        """Os codigos somados, para quem conferir a linha na tela."""
        return " + ".join(v.codigo for v in self.verbas_previdencia)


@dataclass
class Folha:
    """Uma folha de pagamento lida por inteiro."""

    arquivo: str = ""
    competencia: Optional[Competencia] = None
    tipo: str = ""                # "Mensal", "Rescisão", "13º salário"
    entidade: str = ""            # "DE ARIPUANÃ-MT"
    segurados: List[Segurado] = field(default_factory=list)
    paginas_sem_texto: List[int] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    @property
    def total_segurados(self) -> int:
        return len(self.segurados)

    @property
    def total_proventos(self) -> float:
        """O "Total de proventos" do rodape da folha. Conferencia, nao saida."""
        return round(sum(s.total_proventos for s in self.segurados), 2)

    @property
    def total_base(self) -> float:
        return round(sum(s.base_de_contribuicao for s in self.segurados), 2)

    @property
    def fora_da_base(self) -> float:
        """Quanto foi pago sem entrar na base do desconto previdenciario."""
        return round(self.total_proventos - self.total_base, 2)

    @property
    def total_contribuicao(self) -> float:
        return round(sum(s.contribuicao_do_segurado for s in self.segurados), 2)

    @property
    def sem_previdencia(self) -> List[Segurado]:
        """Quem nao teve desconto previdenciario nenhum no mes.

        Nao e erro por si: quem ficou o mes inteiro em licenca sem vencimento
        nao contribui. E' informacao para a tela mostrar antes de exportar,
        porque linha com contribuicao zero costuma ser recusada na importacao.
        """
        return [s for s in self.segurados if not s.tem_previdencia]

    @property
    def fontes(self) -> List[FonteDaFolha]:
        """As fontes pagadoras desta folha, distintas, na ordem em que aparecem.

        E' o que a tela precisa saber: quais codigos de integracao esta folha
        vai exigir. Distintas pela chave (numero + nome), e nao pelo texto
        cru -- o PDF corta o nome longo na largura da coluna, e a mesma fonte
        aparece com duas grafias na mesma folha.
        """
        vistas: List[FonteDaFolha] = []
        conhecidas = set()
        for segurado in self.segurados:
            fonte = segurado.fonte
            if fonte is not None and fonte.chave not in conhecidas:
                conhecidas.add(fonte.chave)
                vistas.append(fonte)
        return vistas

    @property
    def sem_fonte(self) -> List["Segurado"]:
        """Quem a folha nao colocou em grupo nenhum de fonte pagadora."""
        return [s for s in self.segurados if s.fonte is None]

    @property
    def estruturas(self) -> List[Tuple[str, str]]:
        """(estrutura, unidade) distintas, na ordem em que aparecem.

        E' o que a tela de fontes pagadoras precisa saber: quais codigos de
        integracao esta folha vai exigir.
        """
        vistas: List[Tuple[str, str]] = []
        conhecidas = set()
        for segurado in self.segurados:
            if segurado.estrutura and segurado.estrutura not in conhecidas:
                conhecidas.add(segurado.estrutura)
                vistas.append((segurado.estrutura, segurado.unidade))
        return vistas

    def competencia_de_saida(self) -> Optional[Competencia]:
        """A competencia como ela vai para o arquivo.

        O mes do cabecalho e o mes do PAGAMENTO -- a folha de 13o de agosto
        tambem diz "08/2026" no topo. O layout, porem, reserva o mes 13 para o
        13o salario, e e o subtitulo da folha ("(13o salario)") que diz que ela
        e essa. Sem esta troca, o 13o entraria como uma segunda competencia 08
        do mesmo segurado e a importacao recusaria a linha repetida.
        """
        if self.competencia is None:
            return None
        if self.e_decimo_terceiro:
            return Competencia(ano=self.competencia.ano, mes=MES_DECIMO_TERCEIRO)
        return self.competencia

    @property
    def e_decimo_terceiro(self) -> bool:
        texto = _caixa_alta_sem_acento(self.tipo)
        return "13" in texto and "SALARIO" in texto


# ---------------------------------------------------------------------- #
# apoio
# ---------------------------------------------------------------------- #
def _caixa_alta_sem_acento(valor: str) -> str:
    decomposto = unicodedata.normalize("NFKD", str(valor or ""))
    return "".join(c for c in decomposto if not unicodedata.combining(c)).upper()


_NUMERO = re.compile(r"^-?[\d.]*\d(?:,\d+)?$")


def numero(texto: str) -> Optional[float]:
    """Converte "4.810,11" em 4810.11. Devolve None se nao for numero.

    Formato brasileiro: ponto separa milhar, virgula separa decimal. Entregar
    "4.810,11" a `float()` direto levanta excecao; pior, "1069,68" -- que a
    folha escreve SEM o ponto de milhar na coluna de referencia -- viraria
    106968 se alguem apenas apagasse as virgulas.
    """
    limpo = (texto or "").replace("R$", "").strip()
    if not limpo or not _NUMERO.match(limpo):
        return None
    try:
        return float(limpo.replace(".", "").replace(",", "."))
    except ValueError:
        return None
