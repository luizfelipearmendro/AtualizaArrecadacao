# -*- coding: utf-8 -*-
"""Tela de abertura: o que o programa faz, em que ordem, e por onde comecar.

Nao e enfeite. Quem abre este programa uma vez por mes nao lembra se escolhe o
municipio antes ou depois de ler o PDF, nem que Nova Olimpia pede um CSV junto
-- e descobrir isso por tentativa custa uma leitura de 225 paginas. O caminho
fica desenhado ("Como o trabalho anda", o mesmo desenho do AutoArial), e cada
ponto de partida leva a sua tela.

As quatro etapas sao as da tela da arrecadacao, na mesma ordem e com os mesmos
nomes: la elas viram a trilha que mostra onde o trabalho esta.
"""

from __future__ import annotations

import tkinter as tk

from .base_tela import Tela
from .componentes import (Botao, Cartao, Metrica, Passos, acompanhar_largura,
                          grade_igual)
from .tema import (COR_CARTAO, COR_MUDO, COR_OK, COR_PRIMARIA, GAP,
                   T_LEGENDA, fonte)

# (titulo, detalhe, glifo) -- as mesmas da trilha da tela da arrecadacao.
ETAPAS = (
    ("Município", "traz as regras dele", "pessoas"),
    ("Folhas", "PDFs e arquivo complementar", "pasta"),
    ("Conferência", "números, avisos e fontes", "conferir"),
    ("Exportar", "o arquivo do SISPREVWEB", "baixar"),
)

# (glifo, titulo, texto, botao, destino, primario)
PONTOS_DE_PARTIDA = (
    ("diario", "Fazer a arrecadação",
     "Escolha o município, anexe as folhas do mês — prefeitura e câmara "
     "juntas — e o programa aplica as regras dele, confere e monta o arquivo.",
     "COMEÇAR", "folha", True),
    ("conferir", "Regras dos municípios",
     "Formato da folha, 13º da rescisão, arquivo complementar e verbas que a "
     "regra geral erra. Configure uma vez; vale para todo mês.",
     "CONFIGURAR", "municipios", False),
    ("engrenagem", "Fontes pagadoras",
     "O catálogo do SISPREVWEB de cada município, para a folha casar o nome "
     "da fonte com o código de integração.",
     "ABRIR", "fontes", False),
)


class TelaInicio(Tela):
    chave = "inicio"
    titulo = "Início"
    subtitulo = "o fluxo do trabalho e os três pontos de partida"

    def montar(self) -> None:
        self._montar_numeros()
        self.espacar()
        self._montar_fluxo()
        self.espacar()
        self._montar_partidas()
        self.espacar()

        aviso = tk.Label(
            self.corpo,
            text="O programa lê apenas o texto embutido no PDF — ele não "
                 "interpreta folha digitalizada. Se a folha vier como imagem, "
                 "a tela avisa quais páginas ficaram de fora, em vez de "
                 "exportar valores incompletos.",
            bg=self.corpo["bg"], fg=COR_MUDO, font=fonte(T_LEGENDA),
            anchor="w", justify="left", wraplength=760)
        aviso.pack(fill="x", padx=4)
        acompanhar_largura(aviso, folga=8)

    def _montar_numeros(self) -> None:
        linha = tk.Frame(self.corpo, bg=self.corpo["bg"])
        linha.pack(fill="x")
        grade_igual(linha, 3)
        self.metricas = {}
        for indice, (chave, rotulo, cor) in enumerate((
                ("exportacoes", "arquivos exportados por este aplicativo",
                 COR_PRIMARIA),
                ("municipios", "municípios com regra própria", COR_OK),
                ("formatos", "formatos de folha que o programa lê",
                 COR_PRIMARIA))):
            metrica = Metrica(linha, "0", rotulo, cor_acento=cor)
            metrica.grid(row=0, column=indice, sticky="nsew",
                         padx=(0, 0 if indice == 2 else GAP))
            self.metricas[chave] = metrica

    def _montar_fluxo(self) -> None:
        cartao = Cartao(
            self.corpo, titulo="Como o trabalho anda", glifo="grafico",
            legenda="Quatro etapas encadeadas: o município escolhido traz as "
                    "regras dele, e elas valem da leitura da folha até o "
                    "arquivo exportado.")
        cartao.pack(fill="x")
        Passos(cartao.conteudo, ETAPAS).pack(fill="x", pady=(4, 0))

    def _montar_partidas(self) -> None:
        linha = tk.Frame(self.corpo, bg=self.corpo["bg"])
        linha.pack(fill="x")
        grade_igual(linha, len(PONTOS_DE_PARTIDA))
        ultimo = len(PONTOS_DE_PARTIDA) - 1
        for indice, (glifo, titulo, texto, botao, destino, primario) in \
                enumerate(PONTOS_DE_PARTIDA):
            cartao = Cartao(linha, titulo=titulo, glifo=glifo)
            cartao.grid(row=0, column=indice, sticky="nsew",
                        padx=(0, 0 if indice == ultimo else GAP))
            rotulo = tk.Label(cartao.conteudo, text=texto, bg=COR_CARTAO,
                              fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="nw",
                              justify="left", wraplength=260)
            rotulo.pack(fill="both", expand=True)
            acompanhar_largura(rotulo, folga=4)
            Botao(cartao.conteudo, text=botao, primario=primario,
                  command=lambda alvo=destino: self.janela.ir_para(alvo)).pack(
                anchor="w", pady=(14, 0))

    def ao_entrar(self) -> None:
        from arrecadacao import formatos

        config = self.janela.config
        try:
            exportados = len(self.janela.indice.carregar())
        except Exception:                 # indice estragado nao derruba o inicio
            exportados = 0
        self.metricas["exportacoes"].definir(str(exportados))
        self.metricas["municipios"].definir(str(sum(
            1 for m in config.lista_de_municipios() if config.configurado(m))))
        self.metricas["formatos"].definir(str(len(formatos.LEITORES)))
        self.janela.status("Pronto.")
