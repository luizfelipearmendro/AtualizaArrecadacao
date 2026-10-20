# -*- coding: utf-8 -*-
"""Motor do AtualizaArrecadacao: le a folha em PDF e monta o arquivo do layout.

Sem nenhuma dependencia de interface, de proposito -- o mesmo motor serve a
janela e a um script. A casca chama `extracao.ler`, `layout.montar` e
`exportacao.gravar_*`, nessa ordem.
"""

__version__ = "1.4.4"
