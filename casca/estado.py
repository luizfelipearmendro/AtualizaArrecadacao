# -*- coding: utf-8 -*-
"""Estado compartilhado entre as telas e o gerenciador de trabalho.

Duas responsabilidades:

* **Estado** guarda o que passa de uma tela para outra -- a folha lida e as
  linhas ja montadas, para que a tela de fontes pagadoras possa recalcular os
  codigos sem reler as 225 paginas do PDF.

* **Trabalho** roda a tarefa demorada em uma thread e conversa com a janela por
  uma fila. O trabalho pertence ao APLICATIVO, nao a tela: ir ate o cadastro de
  fontes enquanto uma folha e lida nao pode interromper a leitura. Um de cada
  vez -- comecar outro enquanto um roda e recusado com aviso, em vez de
  enfileirar em silencio.

Copiado do AutoArial e enxugado: `Estado` guarda outra coisa, `Trabalho` e o
mesmo codigo, porque o problema que ele resolve e o mesmo.
"""

from __future__ import annotations

import queue
import threading
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional


# ---------------------------------------------------------------------- #
# estado compartilhado
# ---------------------------------------------------------------------- #
@dataclass
class Estado:
    """Memoria viva do aplicativo enquanto ele esta aberto."""

    pasta_base: Path = field(default_factory=Path.cwd)
    # DUAS folhas: a lida do PDF, que nao muda, e a que as telas mostram, com
    # as regras do municipio aplicadas (`regras.aplicar`). Trocar uma regra
    # refaz a segunda a partir da primeira -- sem reler o PDF, e sem aplicar a
    # regra nova por cima da velha.
    folha_lida: Any = None             # arrecadacao.folha.Folha
    folha: Any = None                  # a mesma, com as regras aplicadas
    # O arquivo complementar (o CSV de Nova Olimpia): (nome, linhas).
    complementar: Any = None
    caminho_complementar: str = ""
    # O cadastro de segurados exportado pelo SISPREVWEB: (caminho, segurados).
    # Anexado DEPOIS da leitura, para trocar a matricula da folha pelo codigo
    # que o importador procura -- ver `arrecadacao.segurados_sisprev`. E do
    # municipio: trocar de municipio o descarta.
    cadastro_sisprev: Any = None
    linhas: List[Any] = field(default_factory=list)   # layout.Linha
    caminho_pdf: str = ""
    ultima_exportacao: str = ""
    # O municipio escolhido -- deduzido do cabecalho da folha e corrigivel na
    # tela. Fica AQUI, e nao em cada tela, porque as duas o usam para a mesma
    # coisa: a de fontes para saber que catalogo importar, a da folha para
    # saber contra qual catalogo casar. Dois seletores independentes seriam
    # dois municipios diferentes, e o casamento sairia do cadastro errado.
    municipio: str = ""
    # {chave da fonte -> fontes.Correspondencia} da folha carregada
    correspondencias: dict = field(default_factory=dict)

    def tem_folha(self) -> bool:
        return self.folha is not None and bool(getattr(self.folha, "segurados", []))

    def descrever_folha(self) -> str:
        """Uma linha para a barra lateral dizer o que esta carregado."""
        if not self.tem_folha():
            return "nenhuma folha lida"
        competencia = self.folha.competencia_de_saida()
        return "{} · {} segurado(s)".format(
            competencia or "sem competência", self.folha.total_segurados)

    def limpar(self) -> None:
        self.folha_lida = None
        self.folha = None
        self.complementar = None
        self.linhas = []
        self.caminho_pdf = ""
        self.correspondencias = {}


# ---------------------------------------------------------------------- #
# gerenciador de trabalho
# ---------------------------------------------------------------------- #
@dataclass
class Evento:
    """Mensagem da thread de trabalho para a janela."""

    tipo: str          # "progresso" | "fim" | "erro"
    dono: str          # identificador da tela que pediu o trabalho
    dado: Any = None


class Trabalho:
    """Executa uma tarefa longa por vez, fora da thread da janela."""

    def __init__(self) -> None:
        self.fila: "queue.Queue[Evento]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self.dono: str = ""
        self.rotulo: str = ""
        self.feitos: int = 0
        self.total: int = 0
        self.cancelar: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------ #
    @property
    def ocupado(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def iniciar(self, dono: str, rotulo: str, tarefa: Callable[[Callable], Any],
                cancelar: Optional[Callable[[], None]] = None) -> bool:
        """Dispara `tarefa` em segundo plano. False se ja houver outra rodando.

        `tarefa` recebe uma funcao `progresso(feitos, total, texto)` e devolve
        o resultado, que chega a janela no evento "fim".
        """
        if self.ocupado:
            return False

        self.dono, self.rotulo = dono, rotulo
        self.feitos, self.total = 0, 0
        self.cancelar = cancelar

        def progresso(feitos: int, total: int, texto: str = "") -> None:
            self.feitos, self.total = feitos, total
            self.fila.put(Evento("progresso", dono, (feitos, total, texto)))

        def trabalhador() -> None:
            try:
                self.fila.put(Evento("fim", dono, tarefa(progresso)))
            except Exception as exc:
                self.fila.put(Evento(
                    "erro", dono, "{}\n\n{}".format(exc, traceback.format_exc())))

        self._thread = threading.Thread(target=trabalhador, daemon=True)
        self._thread.start()
        return True

    def pedir_cancelamento(self) -> None:
        if self.cancelar is not None:
            self.cancelar()

    def eventos(self) -> List[Evento]:
        """Esvazia a fila. Chamado pela janela, na thread dela."""
        pendentes: List[Evento] = []
        while True:
            try:
                pendentes.append(self.fila.get_nowait())
            except queue.Empty:
                return pendentes
