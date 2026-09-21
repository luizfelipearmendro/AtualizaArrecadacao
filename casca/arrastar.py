# -*- coding: utf-8 -*-
"""Arrastar arquivos para dentro da janela.

A biblioteca (`tkinterdnd2`) sempre esteve no pacote e a raiz sempre foi
`TkinterDnD.Tk()` -- mas nenhuma tela da casca registrava alvo de soltura, so a
interface antiga. Daí o programa anunciar "drag and drop: disponivel" no
autoteste e nao aceitar arquivo arrastado em lugar nenhum.

Duas coisas que este modulo resolve e que sao faceis de errar:

* **Vários arquivos.** O Tcl entrega os caminhos em uma string unica, com
  chaves em volta dos que tem espaco. Separar com `split()` quebra em cada
  espaco; e `tk.splitlist`, que parecia a saida obvia, interpreta a barra
  invertida como escape e corrompe caminho do Windows. O porque esta em
  `caminhos_do_evento`.
* **Filtrar por extensao no destino.** Quem arrasta uma planilha para a area
  das folhas espera um aviso, nao um erro no meio da conferencia.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Sequence

log = logging.getLogger(__name__)

try:
    from tkinterdnd2 import DND_FILES        # type: ignore
    DISPONIVEL = True
except Exception:                            # pacote ausente
    DND_FILES = "DND_Files"
    DISPONIVEL = False


def caminhos_do_evento(dados: str) -> List[Path]:
    """Os caminhos de um `<<Drop>>`, na ordem em que vieram.

    Escrito a mao, e NAO com `tk.splitlist`. O Tcl trata a barra invertida de um
    item sem chaves como escape: `C:\\folha.pdf` volta como
    `C:folha.pdf` com um formfeed no lugar de `\\f`, e `\\a`, `\\b`, `\\n`, `\\t`
    e `\\v` corrompem do mesmo jeito. Um caminho do Windows tem barra invertida
    em todo separador -- ou seja, o dano e a regra, nao a excecao. Os caminhos
    com espaco escapavam por acidente, porque o tkdnd os envolve em chaves e
    dentro das chaves o Tcl nao interpreta nada.

    Aqui as chaves delimitam, e o resto do texto vai literal.
    """
    if not dados:
        return []
    bruto = dados.strip()
    if not bruto:
        return []

    # Alguns tkdnd nao envolvem em chaves nem quando ha espaco. Se a string
    # inteira e um arquivo existente, ela e o caminho -- e nao varios.
    if not bruto.startswith("{") and Path(bruto).exists():
        return [Path(bruto)]

    achados: List[str] = []
    i = 0
    while i < len(bruto):
        if bruto[i].isspace():
            i += 1
            continue
        if bruto[i] == "{":
            fim = bruto.find("}", i + 1)
            if fim < 0:                       # chave sem par: leva o resto
                achados.append(bruto[i + 1:])
                break
            achados.append(bruto[i + 1:fim])
            i = fim + 1
        else:
            fim = i
            while fim < len(bruto) and not bruto[fim].isspace():
                fim += 1
            achados.append(bruto[i:fim])
            i = fim
    return [Path(p) for p in achados if p.strip()]


def registrar(widget, ao_soltar: Callable[[List[Path]], None]) -> bool:
    """Faz `widget` aceitar arquivos arrastados. False se a biblioteca faltar.

    Registra tambem os filhos do widget: numa `Labelframe` com rotulos e
    botoes dentro, soltar sobre o texto nao alcancaria o quadro.
    """
    if not DISPONIVEL:
        return False

    def tratar(evento):
        caminhos = caminhos_do_evento(getattr(evento, "data", ""))
        if caminhos:
            ao_soltar(caminhos)

    alvos = [widget] + _descendentes(widget)
    registrados = 0
    for alvo in alvos:
        try:
            alvo.drop_target_register(DND_FILES)
            alvo.dnd_bind("<<Drop>>", tratar)
            registrados += 1
        except Exception as erro:
            log.debug("Widget nao aceitou alvo de soltura: %s", erro)
    return registrados > 0


def _descendentes(widget) -> List:
    filhos: List = []
    try:
        for filho in widget.winfo_children():
            filhos.append(filho)
            filhos.extend(_descendentes(filho))
    except Exception:
        pass
    return filhos


def separar(caminhos: Sequence[Path], extensoes: Sequence[str]
            ) -> tuple[List[Path], List[Path]]:
    """(aceitos, recusados) conforme a extensao, em minusculas com ponto."""
    aceitos: List[Path] = []
    recusados: List[Path] = []
    permitidas = {e.lower() for e in extensoes}
    for caminho in caminhos:
        (aceitos if caminho.suffix.lower() in permitidas else recusados
         ).append(caminho)
    return (aceitos, recusados)


def dica(texto: str) -> str:
    """Acrescenta 'ou arraste o arquivo aqui' quando a biblioteca existe."""
    return "{} — ou arraste o arquivo aqui".format(texto) if DISPONIVEL else texto
