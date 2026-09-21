# -*- coding: utf-8 -*-
"""Tela de abertura: o que o programa faz, em que ordem, e por onde comecar.

Nao e enfeite. Quem abre este programa uma vez por mes nao lembra se cadastra a
fonte pagadora antes ou depois de ler o PDF, e descobrir isso por tentativa
custa uma leitura de 225 paginas. Os tres passos e o que eles produzem ficam
escritos, e cada um leva a sua tela.
"""

from __future__ import annotations

import tkinter as tk

from .base_tela import Tela
from .componentes import Botao, Cartao, Linha, acompanhar_largura
from .tema import (COR_CARTAO, COR_FUNDO, COR_MUDO, GAP, T_LEGENDA, fonte)

PASSOS = (
    ("1", "diario", "Leia a folha de pagamento",
     "Anexe o PDF da folha — mensal, de rescisão ou de 13º. O programa "
     "encontra cada segurado, soma o desconto previdenciário do mês e monta a "
     "tabela do layout.", "folha"),
    ("2", "engrenagem", "Importe o catálogo de fontes pagadoras",
     "Uma vez por município: o arquivo que o SISPREVWEB exporta, com as "
     "colunas FONTE_PAG_ID e NOME. A folha diz a fonte pelo nome; o catálogo "
     "dá o código. O que não casar sozinho a tela da folha pergunta.",
     "fontes"),
    ("3", "baixar", "Exporte o arquivo",
     "XLSX para conferir — com totais e uma aba de resumo — ou CSV para "
     "importar no SISPREVWEB.", "folha"),
)


class TelaInicio(Tela):
    chave = "inicio"
    titulo = "Atualiza Arrecadação"
    subtitulo = "da folha de pagamento em PDF para o layout de importação do SISPREVWEB"

    def montar(self) -> None:
        cartao = Cartao(
            self.corpo, titulo="Como funciona", glifo="informacao",
            legenda="Três passos. O segundo só é necessário na primeira folha "
                    "de cada município.")
        cartao.pack(fill="x")

        for numero, glifo, titulo, texto, destino in PASSOS:
            linha = Linha(cartao.conteudo, titulo="{} · {}".format(numero, titulo),
                          texto=texto, glifo=glifo)
            linha.pack(fill="x", pady=(0, 8))
            Botao(linha.acoes, text="ABRIR",
                  command=lambda alvo=destino: self.janela.ir_para(alvo)).pack()

        self.espacar()

        rodape = Cartao(self.corpo, padding=(18, 14))
        rodape.pack(fill="x")
        aviso = tk.Label(
            rodape.conteudo,
            text="O programa lê apenas o texto embutido no PDF — ele não "
                 "interpreta folha digitalizada. Se a folha vier como imagem, "
                 "a tela avisa quais páginas ficaram de fora, em vez de "
                 "exportar valores incompletos.",
            bg=COR_CARTAO, fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w",
            justify="left", wraplength=760)
        aviso.pack(side="left", fill="x", expand=True)
        acompanhar_largura(aviso)

        Botao(rodape.conteudo, text="COMEÇAR  ▸", primario=True,
              command=lambda: self.janela.ir_para("folha")).pack(
            side="right", padx=(12, 0))

    def ao_entrar(self) -> None:
        self.janela.status("Pronto.")
