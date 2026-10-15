# -*- coding: utf-8 -*-
"""Tela principal: anexar as folhas, conferir os numeros e exportar.

O fluxo inteiro em uma tela so, revelado conforme acontece: antes de ler a
folha nao ha o que conferir, e a tela com tudo visivel e vazia pede para ser
ignorada.

Depois da leitura, a ORDEM na tela e o desenho dela, e a ordem e esta:

    1. os documentos anexados -- um ou varios, porque a prefeitura e a camara
       sao PDFs separados e o SISPREVWEB recebe um arquivo por municipio;
    2. o que foi lido do cabecalho (competencia, categoria, municipio), que e
       corrigivel -- adivinhar o municipio errado nao da erro, casa com o
       catalogo da cidade errada;
    3. OS NUMEROS: segurados, remuneracao de contribuicao e contribuicao do
       segurado. Sao a resposta, e e neles que o primeiro olhar tem de cair;
    4. o que FALTA resolver -- fonte sem codigo, que trava a importacao;
    5. o que convem CONFERIR -- fonte que casou sozinha mas pode ter casado
       errado. Separado do anterior de proposito: misturados, como estavam,
       acao e conferencia tinham o mesmo peso e a conferencia era a primeira a
       ser ignorada;
    6. a tabela, para quem quer olhar linha a linha, e o botao de exportar.

Antes, os numeros vinham no meio do caminho e as duas listas de fonte vinham
antes deles, com cinco cartoes de numero lado a lado dando o mesmo peso a
coisas de importancia muito diferente. Quem abria a tela via primeiro o que
nao tinha perguntado.

As fontes pagadoras ficam AQUI, e nao so na tela de cadastro, porque o codigo
de integracao e a unica coluna do layout que a folha nao traz: deixado fora do
caminho, ele vira o passo que alguem esquece e descobre no botao de exportar.

A tabela mostra as colunas do layout mais tres que nao vao no arquivo --
estrutura, verbas somadas e pagina. Sao elas que permitem conferir uma linha
contra o PDF: sem a pagina nao ha como achar o servidor numa folha de 225
paginas, e sem os codigos das verbas nao ha como entender por que o desconto de
alguem e a soma de dois lancamentos.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import arrastar
from .arrastar import registrar as registrar_arrastar
from .base_tela import Tela
from .componentes import (Balao, Botao, Cartao, CaixaCampo, Metrica,
                          Superficie, acompanhar_largura, campo_texto, chip,
                          grade_igual, moldura_de_lista, rotulo_campo,
                          tornar_pesquisavel)
from .identidade import APP_NOME
from .ordenacao import Ordenador
from .preferencias import pasta_gravavel
from .tema import (COR_ACENTO_CLARO, COR_ATENCAO, COR_BORDA, COR_BORDA_CAMPO,
                   COR_CARTAO, COR_CARTAO_FRACO, COR_CHIP, COR_CHIP_TEXTO,
                   COR_DICA, COR_ERRO, COR_FUNDO, COR_MUDO, COR_OK,
                   COR_PRIMARIA, COR_TITULO, GAP, RAIO_LINHA, T_LEGENDA,
                   T_MINI, fonte, fonte_icone, icone)

# As colunas da tabela. As tres ultimas nao vao no arquivo -- ver o modulo.
COLUNAS = (
    ("matricula", "Matrícula", 90, "e"),
    ("nome", "Nome", 230, "w"),
    ("ano", "Ano", 55, "center"),
    ("mes", "Mês", 45, "center"),
    ("base", "Remuneração de contribuição", 165, "e"),
    ("segurado", "Contribuição do segurado", 155, "e"),
    ("patronal", "Patronal normal", 115, "e"),
    ("fonte", "Fonte pagadora", 110, "center"),
    ("categoria", "Categoria", 85, "w"),
    ("fonte_nome", "Fonte na folha", 230, "w"),
    ("verbas", "Verbas", 90, "center"),
    ("pagina", "Pág.", 50, "center"),
)

MESES = tuple("{:02d}".format(m) for m in range(1, 14))

# O nome da fonte e cortado para caber ao lado da lista de codigos: uma linha
# por fonte, e a lista de candidatos e larga. O nome INTEIRO continua no balao
# e no que o clique copia -- o corte e so do que cabe na linha.
LIMITE_NOME_FONTE = 72

# Quanto do nome da unidade cabe na linha de baixo, ao lado da contagem de
# segurados. O nome inteiro fica no balao.
LIMITE_UNIDADE = 44

# Quantos segurados o balao lista antes de resumir. Ha fonte com 149 nesta
# folha, e um balao de 149 linhas nao cabe na tela nem ajuda.
SEGURADOS_NO_BALAO = 12

# Teto da lista de fontes pendentes, em pixels. A tela nao rola, e a area da
# tabela tem 118 na janela padrao: sem teto, uma folha com dez fontes por
# resolver empurrava as metricas e a tabela para fora da janela. Acima do teto
# a lista rola dentro do proprio cartao.
ALTURA_MAX_FONTES = 120


def _moeda(valor: float) -> str:
    """1234.5 -> "1.234,50". A tabela e conferida contra o PDF, que usa isto."""
    return "{:,.2f}".format(float(valor or 0)).replace(",", "\x00") \
        .replace(".", ",").replace("\x00", ".")


def _encurtar(texto: str, limite: int) -> str:
    texto = (texto or "").strip()
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


class TelaFolha(Tela):
    chave = "folha"
    titulo = "1 · Folha de pagamento"
    subtitulo = ("anexe os PDFs, confira os números e exporte o arquivo de "
                 "importação")

    def montar(self) -> None:
        # Varios PDFs, e nao um: a arrecadacao de um mes raramente cabe num
        # arquivo so. A prefeitura exporta a folha dela e a camara a sua, e o
        # SISPREVWEB recebe UM arquivo por municipio -- lidos separados, os
        # dois viram duas exportacoes para conferir e importar em duplicata.
        self.caminhos_pdf: List[str] = []
        self.linhas: List[Any] = []

        self._montar_arquivo()
        self._montar_competencia()
        self._montar_fontes()
        self._montar_conferencia_fontes()
        self._montar_resultado()

    @property
    def caminho_pdf(self) -> Optional[str]:
        """O primeiro documento. So para quem precisa de UM -- a pasta de saida."""
        return self.caminhos_pdf[0] if self.caminhos_pdf else None

    # ------------------------------------------------------------------ #
    # passo 1: o arquivo
    # ------------------------------------------------------------------ #
    def _montar_arquivo(self) -> None:
        cartao = self.cartao_arquivo = Cartao(
            self.corpo, titulo="Folha de pagamento", glifo="pasta",
            legenda=self.LEGENDA_ARQUIVO)
        cartao.pack(fill="x", pady=(0, GAP))

        self.var_arquivo = tk.StringVar(value="nenhum documento escolhido")
        area = self.area_arquivo = Superficie(
            cartao.conteudo, raio=RAIO_LINHA, contorno=COR_BORDA_CAMPO,
            tracejado=True, padding=(14, 12))
        area.pack(fill="x")

        Botao(area.corpo, text="PROCURAR...", command=self._escolher).pack(
            side="right", padx=(12, 0))
        chip(area.corpo, icone("diario"), cor=COR_CHIP,
             cor_glifo=COR_CHIP_TEXTO, cor_fora=COR_CARTAO).pack(
            side="left", padx=(0, 12))

        textos = tk.Frame(area.corpo, bg=COR_CARTAO)
        textos.pack(side="left", fill="x", expand=True)
        rotulo_campo(textos, "Folhas (PDF)").pack(anchor="w")
        tk.Label(textos, textvariable=self.var_arquivo, bg=COR_CARTAO,
                 fg=COR_TITULO, font=fonte(T_LEGENDA, True), anchor="w").pack(
            fill="x")

        # O arrasto vale no cartao INTEIRO, e nao so na area tracejada: depois
        # da leitura a area sai da tela (ver `_encolher_arquivo`) e soltar um
        # PDF continuaria tendo de funcionar.
        registrar_arrastar(area, self._soltar)
        registrar_arrastar(cartao, self._soltar)

        # A lista dos documentos escolhidos, um por linha, com um X para tirar
        # o que entrou por engano. Vazia -- e invisivel -- ate o primeiro.
        self.lista_documentos = tk.Frame(cartao.conteudo, bg=COR_CARTAO)

        self.dica_arquivo = None
        if arrastar.DISPONIVEL:
            self.dica_arquivo = tk.Label(
                cartao.conteudo,
                text="Você também pode arrastar os PDFs para a área acima — "
                     "arraste os dois de uma vez, ou um depois do outro.",
                bg=COR_CARTAO, fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w")
            self.dica_arquivo.pack(fill="x", pady=(10, 0))

        acao = self.acao_arquivo = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        acao.pack(fill="x", pady=(12, 0))
        self.btn_ler = Botao(acao, text="LER AS FOLHAS  ▸", primario=True,
                             command=self._iniciar, state="disabled")
        self.btn_ler.pack(side="right")

        # O botao de trocar mora no CABECALHO do cartao, e nao no corpo. E' o
        # que permite o cartao virar uma linha so depois da leitura: recolhido
        # o corpo inteiro, sobram o chip, o titulo, a legenda com os nomes dos
        # arquivos e este botao -- tudo na mesma altura. Com ele no corpo, o
        # cartao ficava com duas faixas e 60 pixels a mais, em cima da parte
        # da tela que menos importa depois que a folha ja foi lida.
        self.btn_trocar = Botao(cartao.acoes, text="TROCAR OS DOCUMENTOS",
                                command=self._escolher)

    def _encolher_arquivo(self, encolher: bool) -> None:
        """Depois de ler, o cartao do arquivo vira uma linha.

        Ele pede 231 pixels: a area tracejada, a dica do arrasto e o botao.
        Isso e o certo ANTES da leitura, quando escolher o PDF e a unica coisa
        a fazer na tela; depois, e a parte que menos importa, e esses 231
        pixels saem da altura de quem importa.

        E nao e altura sobrando: numa janela maximizada de 1080, com o cartao
        das fontes aberto, o painel de baixo ficava com 201 pixels para 360 de
        conteudo -- a tabela sumia e a caixa do modelo do layout, que o `pack`
        espreme por ultimo, virava um risco de 4 pixels de altura.

        Recolhido, o CORPO INTEIRO sai da tela -- e nao so a area tracejada --
        e o cartao fica com a altura do proprio cabecalho: chip, titulo, os
        nomes dos arquivos na legenda e o botao de trocar, que por isso mora
        no cabecalho. Uma faixa, e nao tres.
        """
        if encolher:
            self.area_arquivo.pack_forget()
            self.lista_documentos.pack_forget()
            if self.dica_arquivo is not None:
                self.dica_arquivo.pack_forget()
            self.btn_ler.pack_forget()
            self.acao_arquivo.pack_forget()
            self.cartao_arquivo.conteudo.pack_forget()
            self.btn_trocar.pack(side="right")
            if self.cartao_arquivo.rotulo_legenda is not None:
                self.cartao_arquivo.rotulo_legenda.configure(
                    text=self._descrever_documentos())
            self.repensar_rolagem()
            return

        self.btn_trocar.pack_forget()
        self.cartao_arquivo.conteudo.pack(fill="both", expand=True,
                                          pady=(12, 0))
        self.acao_arquivo.pack(fill="x", pady=(12, 0))
        self.area_arquivo.pack(fill="x", before=self.acao_arquivo)
        self._montar_lista_documentos()
        if self.dica_arquivo is not None:
            self.dica_arquivo.pack(fill="x", pady=(10, 0),
                                   before=self.acao_arquivo)
        self.btn_ler.pack(side="right")
        if self.cartao_arquivo.rotulo_legenda is not None:
            self.cartao_arquivo.rotulo_legenda.configure(
                text=self.LEGENDA_ARQUIVO)

    LEGENDA_ARQUIVO = ("Os PDFs da folha — a da prefeitura e a da câmara "
                       "entram juntas, e saem num arquivo só.")

    def _descrever_documentos(self) -> str:
        """"2 documentos · geral.pdf, camara.pdf" -- para a linha encolhida."""
        nomes = [Path(c).name for c in self.caminhos_pdf]
        if not nomes:
            return "nenhum documento escolhido"
        if len(nomes) == 1:
            return nomes[0]
        return "{} documentos · {}".format(len(nomes), ", ".join(nomes))

    def _escolher(self) -> None:
        caminhos = filedialog.askopenfilenames(
            title="Folhas de pagamento (PDF)",
            filetypes=[("PDF", "*.pdf"), ("Todos os arquivos", "*.*")])
        if caminhos:
            self._definir(list(caminhos))

    def _soltar(self, caminhos: List[Path]) -> None:
        """Arrastar ACRESCENTA, em vez de substituir.

        Quem arrasta a folha da camara depois da folha da prefeitura quer as
        duas -- trocar uma pela outra em silencio seria perder a primeira sem
        nenhum sinal. Para recomecar ha o X de cada linha e o botao de trocar.
        """
        aceitos, recusados = arrastar.separar(caminhos, (".pdf",))
        if not aceitos:
            messagebox.showwarning(
                APP_NOME,
                "A folha de pagamento é um arquivo .pdf.\n\nRecebido: "
                "{}".format(", ".join(c.name for c in recusados[:4])))
            return
        self._definir([str(c) for c in aceitos], acrescentar=True)

    # O botao e o arrasto passam pelo MESMO metodo: nada de um caminho habilitar
    # o botao de ler e o outro esquecer.
    def _definir(self, caminhos, acrescentar: bool = False) -> None:
        if isinstance(caminhos, str):
            caminhos = [caminhos]
        novos = list(self.caminhos_pdf) if acrescentar else []
        for caminho in caminhos:
            if caminho not in novos:
                novos.append(caminho)
        self.caminhos_pdf = novos

        self.var_arquivo.set(self._descrever_documentos())
        self._encolher_arquivo(False)
        self.btn_ler.configure(
            state="normal" if self.caminhos_pdf else "disabled")
        self.janela.status(
            "Pronto para ler {}.".format(self._descrever_documentos())
            if self.caminhos_pdf else "Anexe o PDF da folha de pagamento.")

    def _montar_lista_documentos(self) -> None:
        """Uma linha por documento escolhido, com o X para tirar."""
        for filho in self.lista_documentos.winfo_children():
            filho.destroy()
        if not self.caminhos_pdf:
            self.lista_documentos.pack_forget()
            return

        for caminho in self.caminhos_pdf:
            linha = tk.Frame(self.lista_documentos, bg=COR_CARTAO)
            linha.pack(fill="x", pady=(6, 0))
            fechar = tk.Label(linha, text="✕", bg=COR_CARTAO, fg=COR_MUDO,
                              font=fonte(T_LEGENDA), cursor="hand2")
            fechar.pack(side="right", padx=(10, 0))
            fechar.bind("<Button-1>",
                        lambda _e, c=caminho: self._tirar_documento(c))
            Balao(fechar, "Tirar este documento da lista.")
            rotulo = tk.Label(linha, text=Path(caminho).name, bg=COR_CARTAO,
                              fg=COR_TITULO, font=fonte(T_LEGENDA),
                              anchor="w")
            rotulo.pack(side="left", fill="x", expand=True)
            Balao(rotulo, caminho)
        self.lista_documentos.pack(fill="x", pady=(10, 0),
                                   after=self.area_arquivo)

    def _tirar_documento(self, caminho: str) -> None:
        self.caminhos_pdf = [c for c in self.caminhos_pdf if c != caminho]
        self.var_arquivo.set(self._descrever_documentos())
        self._montar_lista_documentos()
        self.btn_ler.configure(
            state="normal" if self.caminhos_pdf else "disabled")

    # ------------------------------------------------------------------ #
    # passo 2: competencia e categoria
    # ------------------------------------------------------------------ #
    def _montar_competencia(self) -> None:
        """Cartao da competencia. Escondido ate a folha ser lida.

        Ano e mes sao EDITAVEIS mesmo vindo preenchidos do cabecalho do PDF:
        uma folha complementar, ou um cabecalho que o gerador escreveu de outro
        jeito, nao pode obrigar ninguem a desistir do programa. O que a tela
        deduziu fica dito ao lado, para a correcao ser consciente.
        """
        self.cartao_competencia = Cartao(
            self.corpo, titulo="Competência e categoria", glifo="calendario",
            legenda="Confira o que foi lido do cabeçalho da folha.")

        campos = tk.Frame(self.cartao_competencia.conteudo, bg=COR_CARTAO)
        campos.pack(fill="x")

        ano = tk.Frame(campos, bg=COR_CARTAO)
        ano.grid(row=0, column=0, sticky="we", padx=(0, GAP))
        rotulo_campo(ano, "Ano").pack(anchor="w", pady=(0, 4))
        self.var_ano = tk.StringVar()
        caixa_ano, _entrada = campo_texto(ano, self.var_ano, largura=8)
        caixa_ano.pack(anchor="w")

        mes = tk.Frame(campos, bg=COR_CARTAO)
        mes.grid(row=0, column=1, sticky="we", padx=(0, GAP))
        rotulo_campo(mes, "Mês (13 = 13º salário)").pack(anchor="w", pady=(0, 4))
        self.var_mes = tk.StringVar()
        moldura_mes = moldura_de_lista(mes)
        moldura_mes.pack(anchor="w")
        self.combo_mes = ttk.Combobox(moldura_mes.corpo, state="readonly",
                                      textvariable=self.var_mes, width=6,
                                      values=MESES, style="Plano.TCombobox")
        self.combo_mes.pack()
        moldura_mes.acompanhar(self.combo_mes)
        self.combo_mes.bind("<MouseWheel>", lambda e: "break")

        categoria = tk.Frame(campos, bg=COR_CARTAO)
        categoria.grid(row=0, column=2, sticky="we", padx=(0, GAP))
        rotulo_campo(categoria, "Categoria").pack(anchor="w", pady=(0, 4))
        self.var_categoria = tk.StringVar()
        moldura_cat = moldura_de_lista(categoria)
        moldura_cat.pack(anchor="w")
        from arrecadacao.folha import CATEGORIA_PADRAO, CATEGORIAS_ACEITAS
        self.var_categoria.set(CATEGORIA_PADRAO)
        self.combo_categoria = ttk.Combobox(
            moldura_cat.corpo, state="readonly", textvariable=self.var_categoria,
            width=24, values=list(CATEGORIAS_ACEITAS), style="Plano.TCombobox")
        self.combo_categoria.pack()
        moldura_cat.acompanhar(self.combo_categoria)
        self.combo_categoria.bind("<MouseWheel>", lambda e: "break")

        # O municipio decide contra QUAL catalogo as fontes desta folha vao
        # casar. Vem adivinhado do cabecalho ("DE ARIPUANA-MT") e fica a vista
        # justamente porque adivinhar errado nao da erro: casa com o cadastro
        # da cidade errada e credita a arrecadacao toda na fonte errada.
        municipio = tk.Frame(campos, bg=COR_CARTAO)
        municipio.grid(row=0, column=3, sticky="we")
        rotulo_campo(municipio, "Município").pack(anchor="w", pady=(0, 4))
        # A caixa guarda o ROTULO ("✓  ARIPUANÃ"), e nao o nome puro: a marca
        # do catalogo importado precisa aparecer na lista fechada tambem, que e
        # onde se olha antes de trocar. `_municipio_escolhido` desfaz.
        self.var_municipio = tk.StringVar()
        self._municipio_de_rotulo: Dict[str, str] = {}
        moldura_mun = moldura_de_lista(municipio)
        moldura_mun.pack(anchor="w")
        self.combo_municipio = ttk.Combobox(
            moldura_mun.corpo, textvariable=self.var_municipio,
            width=28, style="Plano.TCombobox")
        self.combo_municipio.pack()
        self._rotulos_municipio = []
        tornar_pesquisavel(self.combo_municipio,
                           lambda: self._rotulos_municipio)
        moldura_mun.acompanhar(self.combo_municipio)
        self.combo_municipio.bind("<MouseWheel>", lambda e: "break")
        grade_igual(campos, 4)

        # O que foi lido do cabecalho ("Mensal - DE ARIPUANA-MT") vai para a
        # LEGENDA do cartao, e nao para uma linha propria: uma linha a mais
        # aqui sai da altura da tabela, que nesta janela tem 118 pixels.
        self.var_origem = tk.StringVar()

        for variavel in (self.var_ano, self.var_mes, self.var_categoria):
            variavel.trace_add("write", lambda *_a: self._remontar())
        self.var_municipio.trace_add("write",
                                     lambda *_a: self._trocar_municipio())

    # ------------------------------------------------------------------ #
    # passo 3: as fontes pagadoras que o catalogo nao resolveu
    # ------------------------------------------------------------------ #
    def _montar_fontes(self) -> None:
        """Cartao do que ficou sem codigo, no meio da leitura.

        A folha agrupa os servidores por fonte pagadora e escreve o grupo no
        cabecalho ("2 - 1 - 2002 -GABINETE EFETIVOS F 1.500"); o catalogo
        importado do SISPREVWEB da o codigo de cada uma. Na folha mensal de
        Aripuana, 51 das 59 casam sozinhas -- o que sobra chega aqui.

        Sobra em dois sabores, e eles pedem campos diferentes:

        * o numero existe no catalogo com MAIS DE UMA fonte -- "351 - 2061 -
          SAUDE - SAUDE BUCAL" esta la duas vezes, codigos 5144 e 5048. Nao ha
          no arquivo o que diga qual e; a tela mostra as duas e quem sabe
          escolhe, numa lista;
        * o numero nao existe no catalogo -- fonte nova, ainda nao exportada.
          Ai e campo de digitar mesmo.

        O cartao so aparece quando ha o que resolver, e sai da tela quando a
        ultima e resolvida: ver `_mostrar_cartao_fontes`.
        """
        self.cartao_fontes = Cartao(
            self.corpo, titulo="Falta resolver: fontes sem código",
            glifo="engrenagem",
            legenda="Sem código, a linha não é aceita na importação.")
        Balao(self.cartao_fontes, self.AJUDA_FONTES)

        self.campos_fonte: Dict[str, tk.StringVar] = {}
        self.marcas_fonte: Dict[str, tk.Label] = {}
        self.opcoes_fonte: Dict[str, Dict[str, str]] = {}
        self._silencio_fontes = False
        self._gravacao_pendente: Optional[str] = None

        self.btn_catalogo = Botao(
            self.cartao_fontes.acoes, text="VER O CATÁLOGO", sutil=True,
            command=lambda: self.janela.ir_para("fontes"))
        self.btn_catalogo.pack(side="right")
        self.var_fontes_resumo = tk.StringVar(value="")
        self.rotulo_fontes_resumo = tk.Label(
            self.cartao_fontes.acoes, textvariable=self.var_fontes_resumo,
            bg=COR_CARTAO, fg=COR_ATENCAO, font=fonte(T_LEGENDA))
        self.rotulo_fontes_resumo.pack(side="right", padx=(0, 12))

        # A lista mora numa area de altura limitada: ver ALTURA_MAX_FONTES.
        self.area_fontes = tk.Frame(self.cartao_fontes.conteudo, bg=COR_CARTAO)
        self.area_fontes.pack(fill="x")
        self.tela_fontes = tk.Canvas(self.area_fontes, bg=COR_CARTAO,
                                     highlightthickness=0, bd=0, takefocus=0,
                                     height=1)
        self.tela_fontes.rola_sozinho_ = True     # ver `Tela.rola_sozinho`
        self.tela_fontes.pack(side="left", fill="both", expand=True)
        self.barra_fontes = ttk.Scrollbar(self.area_fontes, orient="vertical",
                                          command=self.tela_fontes.yview)
        self.tela_fontes.configure(yscrollcommand=self.barra_fontes.set)

        self.grade_fontes = tk.Frame(self.tela_fontes, bg=COR_CARTAO)
        self._janela_fontes = self.tela_fontes.create_window(
            (0, 0), window=self.grade_fontes, anchor="nw")
        self.tela_fontes.bind(
            "<Configure>",
            lambda e: self.tela_fontes.itemconfigure(self._janela_fontes,
                                                     width=e.width))
        # A altura da area acompanha a grade em vez de ser medida uma unica
        # vez. Medida so na montagem, ela dependia de a janela ja ter
        # assentado: quando a leitura termina pela fila de eventos do
        # trabalho -- que e como acontece de verdade, e nao nos testes --, as
        # linhas ainda nao tem tamanho no instante da medida, a area fica com
        # 1 pixel e NUNCA MAIS e refeita. O cartao aparecia dizendo "1 de 1
        # fonte(s) sem codigo" e sem a linha para resolver, que e pior do que
        # nao aparecer: o usuario ve o aviso e nao tem o que fazer com ele.
        self.grade_fontes.bind("<Configure>",
                               lambda _e: self._medir_lista_fontes(), add="+")

    # ------------------------------------------------------------------ #
    # passo 3b: o que casou, mas merece um olhar
    # ------------------------------------------------------------------ #
    def _montar_conferencia_fontes(self) -> None:
        """Cartao do que esta resolvido mas pode estar resolvido errado.

        Separado do cartao de cima de proposito: la fica o que EXIGE acao --
        sem codigo, nao exporta --, e aqui o que exige CONFERENCIA. Misturados,
        como estavam, as duas coisas tinham o mesmo peso e quem abria a tela
        nao sabia por onde comecar; e a conferencia, que nao trava nada, era a
        primeira a ser ignorada.

        Sao tres coisas, e as tres sao silenciosas se ninguem as disser:

        * duas fontes da folha com o MESMO codigo. Soma certa, arrecadacao na
          fonte errada -- o tipo de erro que a conferencia por total nunca
          pega, porque o total continua batendo;
        * fonte que casou so pelo NUMERO, com o nome diferente do catalogo.
          E' o unico casamento que o programa faz sem ter certeza;
        * linhas com pendencia, que a importacao vai recusar.
        """
        self.cartao_conferencia = Cartao(
            self.corpo, titulo="Confira antes de exportar", glifo="aviso",
            legenda="Nada aqui impede a exportação.")
        self.area_conferencia = tk.Frame(self.cartao_conferencia.conteudo,
                                         bg=COR_CARTAO)
        self.area_conferencia.pack(fill="x")

    def _pintar_conferencia_fontes(self) -> None:
        """Refaz as linhas do cartao, e o esconde quando nao ha nenhuma."""
        for filho in self.area_conferencia.winfo_children():
            filho.destroy()

        itens = self._pontos_de_conferencia()
        if not itens:
            self.cartao_conferencia.pack_forget()
            return

        for cor, titulo, detalhe, balao in itens:
            linha = tk.Frame(self.area_conferencia, bg=COR_CARTAO)
            linha.pack(fill="x", pady=3)
            tk.Label(linha, text=icone("aviso"), bg=COR_CARTAO, fg=cor,
                     font=fonte_icone(12), width=2).pack(side="left",
                                                         padx=(0, 8))
            textos = tk.Frame(linha, bg=COR_CARTAO)
            textos.pack(side="left", fill="x", expand=True)
            rotulo = tk.Label(textos, text=titulo, bg=COR_CARTAO, fg=COR_TITULO,
                              font=fonte(T_LEGENDA, True), anchor="w")
            rotulo.pack(anchor="w")
            if detalhe:
                tk.Label(textos, text=detalhe, bg=COR_CARTAO, fg=COR_DICA,
                         font=fonte(T_MINI), anchor="w",
                         justify="left").pack(anchor="w")
            if balao:
                Balao(rotulo, balao)

        self._mostrar_cartao_conferencia(True)

    def _pontos_de_conferencia(self) -> List[tuple]:
        """(cor, título, detalhe, balão) de cada ponto. Vazio = nada a dizer."""
        if not self.estado.tem_folha():
            return []
        from arrecadacao.fontes import POR_NUMERO

        itens: List[tuple] = []
        folha = self.estado.folha

        # 1. mesmo codigo para fontes diferentes
        por_codigo: Dict[str, List[Any]] = {}
        for correspondencia in self.estado.correspondencias.values():
            if correspondencia.codigo:
                por_codigo.setdefault(correspondencia.codigo, []).append(
                    correspondencia.fonte)
        repetidos = {c: fs for c, fs in por_codigo.items() if len(fs) > 1}
        for codigo, fontes_iguais in sorted(repetidos.items()):
            quantos = sum(len(folha.segurados_da_fonte(f.chave))
                          for f in fontes_iguais)
            itens.append((
                COR_ATENCAO,
                "{} fontes da folha com o mesmo código {}".format(
                    len(fontes_iguais), codigo),
                "{} segurado(s) vão todos para essa fonte  ·  {}".format(
                    quantos,
                    _encurtar(" | ".join(str(f) for f in fontes_iguais), 96)),
                "Estas fontes da folha estão apontando para o mesmo código "
                "do SISPREVWEB:\n\n{}\n\nSe forem mesmo a mesma fonte, está "
                "certo. Se não forem, a arrecadação de umas está sendo "
                "creditada na outra — e o total continua fechando, que é o "
                "que torna isso difícil de perceber.".format(
                    "\n".join("    " + str(f) for f in fontes_iguais))))

        # 2. casou so pelo numero
        so_numero = [c for c in self.estado.correspondencias.values()
                     if c.origem == POR_NUMERO]
        if so_numero:
            itens.append((
                COR_ATENCAO,
                "{} fonte(s) casaram só pelo número".format(len(so_numero)),
                _encurtar(" | ".join(str(c.fonte) for c in so_numero), 96),
                "O número bate com o catálogo, mas o nome não. Costuma ser "
                "catálogo do município errado, ou fonte renomeada no "
                "SISPREVWEB depois da última exportação.\n\n{}".format(
                    "\n".join("    {} → código {}".format(c.fonte, c.codigo)
                              for c in so_numero[:8]))))

        # 3. linhas que a importacao recusaria
        pendentes = [l for l in self.linhas if l.tem_pendencia]
        if pendentes:
            motivos: Dict[str, int] = {}
            for linha in pendentes:
                for motivo in linha.pendencias:
                    motivos[motivo] = motivos.get(motivo, 0) + 1
            itens.append((
                COR_ERRO,
                "{} linha(s) com pendência".format(len(pendentes)),
                "  ·  ".join("{} ({})".format(m, q) for m, q
                             in sorted(motivos.items(), key=lambda i: -i[1])),
                "Estas linhas estão em vermelho na tabela. A importação "
                "costuma recusá-las."))
        return itens

    def _mostrar_cartao_conferencia(self, mostrar: bool) -> None:
        """Entra sempre logo acima do painel de resultado."""
        if mostrar == bool(self.cartao_conferencia.winfo_manager()):
            return
        self.repensar_rolagem()
        if not mostrar:
            self.cartao_conferencia.pack_forget()
            return
        # O lugar deste cartao e definido por `before=painel`: ele vem DEPOIS
        # do que falta resolver e ANTES da tabela. Enquanto o painel nao esta
        # na tela nao ha essa ancora, e empacotar assim mesmo jogava o cartao
        # para logo abaixo dos documentos -- que foi exatamente o que aconteceu
        # na primeira versao desta tela. `ao_concluir` repinta no fim.
        if not self.painel.winfo_manager():
            return
        self.cartao_conferencia.pack(fill="x", pady=(0, GAP),
                                     before=self.painel)

    # ------------------------------------------------------------------ #
    # O detalhe de como usar o cartao sai da legenda e vem para ca: na tela,
    # aquilo ocupava quatro linhas acima da lista que importa -- e texto de
    # ajuda, que se le uma vez, empurrando para baixo o trabalho, que se faz
    # toda vez. No balao ele continua a um passo de distancia.
    AJUDA_FONTES = (
        "A folha agrupa os servidores por fonte pagadora, e o catálogo "
        "importado do SISPREVWEB dá o código de cada uma. Chega aqui o que "
        "não casou sozinho:\n\n"
        "    • a fonte não existe no catálogo — campo para digitar o código;\n"
        "    • há mais de uma com o mesmo número — lista para escolher;\n"
        "    • o documento não diz a fonte (a folha da câmara, em geral) — "
        "lista com o catálogo inteiro, as mais prováveis no topo.\n\n"
        "Passe o mouse na linha de baixo para ver quem está na fonte. "
        "Clique no nome para copiá-lo, ou nos segurados para copiar a lista "
        "e colar na busca do SISPREVWEB.\n\n"
        "O que você escolher fica gravado para as próximas folhas.")

    def _montar_lista_fontes(self) -> None:
        """Uma linha por fonte que o catalogo nao resolveu sozinho.

        Sem codigo NO MOMENTO DO CASAMENTO: a linha de quem for resolvido fica
        na lista, marcada de verde, ate a proxima folha. E a conferencia de
        quem acabou de escolher oito codigos -- e refazer a lista a cada tecla
        destruiria o campo que esta com o foco.
        """
        for filho in self.grade_fontes.winfo_children():
            filho.destroy()
        self.campos_fonte.clear()
        self.marcas_fonte.clear()
        self.opcoes_fonte.clear()

        if not self.estado.tem_folha():
            return

        for indice, correspondencia in enumerate(self.janela.fontes_pendentes()):
            celula = tk.Frame(self.grade_fontes, bg=COR_CARTAO)
            celula.grid(row=indice, column=0, sticky="we", pady=3)
            self._linha_fonte(celula, correspondencia)
        self.grade_fontes.columnconfigure(0, weight=1)
        self._medir_lista_fontes()

    def _linha_fonte(self, celula: tk.Frame, correspondencia) -> None:
        # `da_folha`, e nao `fonte`: `fonte` neste modulo e a funcao que devolve
        # a fonte tipografica, e sombrea-la quebra o rotulo desta propria linha.
        da_folha = correspondencia.fonte
        chave = da_folha.chave

        marca = tk.Label(celula, text="", bg=COR_CARTAO, width=2,
                         font=fonte_icone(12))
        marca.pack(side="left", padx=(0, 8))
        self.marcas_fonte[chave] = marca

        variavel = tk.StringVar(value="")
        self.campos_fonte[chave] = variavel

        if correspondencia.candidatos:
            # Mais de um codigo possivel: lista, e nao campo aberto. Digitar um
            # codigo que o catalogo nao tem, tendo o catalogo, e sempre engano.
            opcoes = {}
            for candidato in correspondencia.candidatos:
                opcoes["{} — {}".format(candidato.codigo, candidato.nome)] = \
                    candidato.codigo
            self.opcoes_fonte[chave] = opcoes
            moldura = moldura_de_lista(celula)
            moldura.pack(side="right", padx=(10, 0))
            combo = ttk.Combobox(moldura.corpo, state="readonly", width=52,
                                 values=list(opcoes), style="Plano.TCombobox")
            combo.pack()
            # Quando a folha nao diz a fonte -- a da camara, em regra --, os
            # candidatos sao o catalogo INTEIRO do municipio, e nao os dois ou
            # tres que compartilham um numero. Rolar sessenta linhas para achar
            # "CAMARA MUNICIPAL" e o que a caixa pesquisavel resolve. As
            # provaveis ja vem no topo da lista: ver `_catalogo_ordenado`.
            if da_folha.folha_inteira or len(opcoes) > 8:
                tornar_pesquisavel(combo, lambda o=list(opcoes): o)
            moldura.acompanhar(combo)
            combo.bind("<MouseWheel>", lambda e: "break")
            combo.bind("<<ComboboxSelected>>",
                       lambda _e, c=combo, k=chave: self._escolher_candidato(k, c))
            alvos = (celula, marca, moldura, combo)
        else:
            caixa, entrada = campo_texto(celula, variavel, largura=10,
                                         padding=(9, 5))
            caixa.pack(side="right", padx=(10, 0))
            entrada.bind("<Return>", lambda _e: self._gravar_fontes())
            entrada.bind("<FocusOut>", lambda _e: self._gravar_fontes())
            entrada.bind("<FocusIn>",
                         lambda _e, alvo=celula: self._mostrar_campo_fonte(alvo))
            variavel.trace_add(
                "write", lambda *_a, alvo=chave: self._ao_digitar_fonte(alvo))
            alvos = (celula, marca, caixa, entrada)

        textos = tk.Frame(celula, bg=COR_CARTAO)
        textos.pack(side="left", fill="x", expand=True)
        # O nome inteiro, e nao o encurtado: resolver a fonte e procurar ESTE
        # nome no SISPREVWEB, e quem digita "2062 - SAUDE - APS EFETIVOS
        # F.1.600.0000600" a mao erra um ponto e nao acha. Um clique copia.
        rotulo = tk.Label(textos,
                          text=_encurtar(str(da_folha), LIMITE_NOME_FONTE),
                          bg=COR_CARTAO, fg=COR_TITULO,
                          font=fonte(T_LEGENDA, True), anchor="w",
                          cursor="hand2")
        # Sem `fill`: o rotulo fica da largura do TEXTO, e nao da coluna. Com
        # fill ele media 1.456 pixels para 444 de texto -- e a mao do cursor
        # aparecia sobre espaco vazio, e o balao abria a um palmo do nome.
        rotulo.pack(anchor="w")
        Balao(rotulo, "Clique para copiar:\n{}".format(da_folha))
        rotulo.bind("<Button-1>",
                    lambda _e, texto=str(da_folha): self._copiar(texto))
        # Quem esta nesta fonte. O nome do grupo -- "600 - 2067 - SAMU EFETIVOS
        # 1.600.000.603" -- muitas vezes nao diz nada a quem vai procurar o
        # codigo no SISPREVWEB; o servidor que esta nela diz, e a unidade dele
        # diz mais ainda. Resumo na linha, lista inteira no balao, e o clique
        # copia a lista toda para colar na busca.
        resumo, detalhe, copiavel = self._quem_esta_na_fonte(chave)
        legenda = tk.Label(textos, text="{}  ·  {}".format(
            correspondencia.origem, resumo), bg=COR_CARTAO, fg=COR_DICA,
            font=fonte(T_MINI), anchor="w", cursor="hand2")
        legenda.pack(anchor="w")
        Balao(legenda, detalhe)
        legenda.bind("<Button-1>",
                     lambda _e, texto=copiavel: self._copiar(texto))
        self._marcar_fonte(chave)

        # A roda rola a lista onde quer que o ponteiro esteja dentro dela. Um
        # `bind_all` alcancaria tambem a tabela de 774 linhas, logo abaixo.
        for alvo in alvos + (textos, rotulo, legenda):
            alvo.bind("<MouseWheel>", self._rolar_fontes, add="+")

    def _copiar(self, texto: str) -> None:
        """Poe o nome da fonte na area de transferencia.

        `update()` depois de escrever: sem ele, o que foi copiado some quando
        a janela fecha -- o Tk so entrega o conteudo quando alguem pede, e um
        processo encerrado nao entrega nada.
        """
        try:
            self.corpo.clipboard_clear()
            self.corpo.clipboard_append(texto)
            self.corpo.update()
        except tk.TclError:
            self.janela.status("Não consegui copiar.")
            return
        self.janela.status("Copiado: {}".format(texto))

    def _quem_esta_na_fonte(self, chave: str) -> tuple:
        """(resumo de uma linha, detalhe do balao, texto para copiar).

        O balao mostra ate `SEGURADOS_NO_BALAO` nomes: ha fonte com 149
        servidores, e um balao de 149 linhas nao cabe na tela nem ajuda. O que
        o clique copia e a lista INTEIRA -- esse vai para a busca, nao para o
        olho.
        """
        if not self.estado.tem_folha():
            return ("", "", "")
        folha = self.estado.folha
        segurados = folha.segurados_da_fonte(chave)
        unidades = folha.unidades_da_fonte(chave)
        if not segurados:
            return ("nenhum segurado nesta fonte", "", "")

        quantos = "{} segurado{}".format(len(segurados),
                                         "" if len(segurados) == 1 else "s")
        resumo = quantos
        if len(unidades) == 1:
            resumo += "  ·  " + _encurtar(unidades[0], LIMITE_UNIDADE)
        elif unidades:
            resumo += "  ·  {} unidades".format(len(unidades))

        linhas = ["{} nesta fonte:".format(quantos)]
        for segurado in segurados[:SEGURADOS_NO_BALAO]:
            linhas.append("    {:<8} {:<34} pág. {}".format(
                segurado.matricula or "—", segurado.nome[:34], segurado.pagina))
        if len(segurados) > SEGURADOS_NO_BALAO:
            linhas.append("    ... e mais {}".format(
                len(segurados) - SEGURADOS_NO_BALAO))
        if unidades:
            linhas.append("")
            linhas.append("Unidade{}: {}".format(
                "" if len(unidades) == 1 else "s", "; ".join(unidades[:4])))
        linhas.append("")
        linhas.append("Clique para copiar a lista inteira.")

        copiavel = "\n".join(
            "{}\t{}\tpág. {}".format(s.matricula, s.nome, s.pagina)
            for s in segurados)
        return (resumo, "\n".join(linhas), copiavel)

    def _escolher_candidato(self, chave: str, combo) -> None:
        self.campos_fonte[chave].set(
            self.opcoes_fonte.get(chave, {}).get(combo.get(), ""))
        self._gravar_fontes()

    def _medir_lista_fontes(self) -> None:
        """Da a area a altura da lista, ate o teto -- e so entao a barra.

        Chamada na montagem E a cada vez que a grade muda de tamanho, porque
        a medida da montagem pode pegar as linhas antes de elas terem altura.
        A reentrada e barrada: mudar a altura da area e, com ela, a barra de
        rolagem mexe no proprio widget que dispara esta medida.
        """
        if getattr(self, "_medindo_fontes", False):
            return
        self._medindo_fontes = True
        try:
            self._medir_lista_fontes_agora()
        finally:
            self._medindo_fontes = False

    def _medir_lista_fontes_agora(self) -> None:
        self.grade_fontes.update_idletasks()
        pedida = self.grade_fontes.winfo_reqheight()
        altura = min(pedida, ALTURA_MAX_FONTES)
        self.tela_fontes.configure(height=max(altura, 1),
                                   scrollregion=(0, 0, 0, pedida))
        self.repensar_rolagem()
        if pedida > altura:
            self.barra_fontes.pack(side="right", fill="y")
        else:
            self.barra_fontes.pack_forget()
            self.tela_fontes.yview_moveto(0)

    def _rolar_fontes(self, evento) -> str:
        self.tela_fontes.yview_scroll(-1 * (evento.delta // 120), "units")
        return "break"

    def _mostrar_campo_fonte(self, widget: tk.Misc) -> None:
        """Rola a lista ate o campo que acabou de receber o foco."""
        self.tela_fontes.update_idletasks()
        alto = self.grade_fontes.winfo_reqheight()
        visivel = self.tela_fontes.winfo_height()
        if alto <= visivel:
            return
        topo = widget.winfo_rooty() - self.grade_fontes.winfo_rooty()
        atual = self.tela_fontes.canvasy(0)
        if topo < atual:
            self.tela_fontes.yview_moveto(topo / alto)
        elif topo + widget.winfo_height() > atual + visivel:
            self.tela_fontes.yview_moveto(
                (topo + widget.winfo_height() - visivel) / alto)

    # ------------------------------------------------------------------ #
    def _ao_digitar_fonte(self, chave: str) -> None:
        if self._silencio_fontes:
            return
        self._marcar_fonte(chave)
        # Digitar "5085" dispara o trace quatro vezes, e cada gravacao recasa
        # as fontes, remonta as 774 linhas e reescreve o json. Sem o adiamento
        # a tela engasga a cada tecla; com ele, grava quando a digitacao para.
        if self._gravacao_pendente is not None:
            self.corpo.after_cancel(self._gravacao_pendente)
        self._gravacao_pendente = self.corpo.after(400, self._gravar_fontes)

    def _gravar_fontes(self) -> None:
        """Leva as escolhas para o cadastro, recasa e recalcula a tabela."""
        if self._gravacao_pendente is not None:
            self.corpo.after_cancel(self._gravacao_pendente)
            self._gravacao_pendente = None
        if not self.campos_fonte or not self.estado.tem_folha():
            return

        cadastro = self.janela.cadastro
        municipio = self.estado.municipio
        por_chave = {f.chave: f for f in self.estado.folha.fontes}
        mudou = False
        for chave, variavel in self.campos_fonte.items():
            fonte = por_chave.get(chave)
            if fonte is None:
                continue
            codigo = variavel.get().strip()
            # O layout diz que a fonte pagadora e NUMERICA. O que nao for fica
            # no campo, marcado em vermelho, mas nao entra no cadastro: melhor
            # a linha seguir pendente aqui do que a contribuicao ser creditada
            # na fonte errada la.
            if codigo and not codigo.isdigit():
                continue
            if codigo != cadastro.escolha_de(municipio, fonte):
                cadastro.escolher(municipio, fonte, codigo)
                mudou = True

        if mudou and not cadastro.salvar():
            self.janela.status(
                "As escolhas valem nesta sessão: o cadastro não pôde ser "
                "gravado em {}.".format(cadastro.caminho))
        if mudou:
            self.janela.casar_fontes()
            self._remontar()
        self._atualizar_resumo_fontes()

    def _marcar_fonte(self, chave: str) -> None:
        marca = self.marcas_fonte.get(chave)
        if marca is None:
            return
        codigo = self.campos_fonte[chave].get().strip()
        if not codigo:
            marca.configure(text=icone("aviso"), fg=COR_ATENCAO)
        elif not codigo.isdigit():
            marca.configure(text=icone("aviso"), fg=COR_ERRO)
        else:
            marca.configure(text=icone("certo"), fg=COR_OK)

    def _atualizar_resumo_fontes(self) -> None:
        """O contador do cabecalho -- e o cartao inteiro, quando nada falta."""
        faltam = self.janela.fontes_pendentes()
        if not faltam:
            self._mostrar_cartao_fontes(False)
            return
        for chave in self.campos_fonte:
            self._marcar_fonte(chave)
        total = len(self.estado.folha.fontes) if self.estado.tem_folha() else 0
        self.var_fontes_resumo.set(
            "{} de {} fonte(s) sem código".format(len(faltam), total))

    def _mostrar_cartao_fontes(self, mostrar: bool) -> None:
        """Poe ou tira o cartao da tela, sempre acima do painel de resultado."""
        if mostrar == bool(self.cartao_fontes.winfo_manager()):
            return
        self.repensar_rolagem()
        if not mostrar:
            self.cartao_fontes.pack_forget()
            if self.estado.tem_folha():
                self.janela.status(
                    "As {} fontes desta folha têm código. Confira a tabela e "
                    "exporte.".format(len(self.estado.folha.fontes)))
            return
        # `before` exige um irmao ja empacotado: na primeira leitura o painel
        # ainda nao esta na tela, e ai o cartao so precisa entrar por ultimo.
        if self.painel.winfo_manager():
            self.cartao_fontes.pack(fill="x", pady=(0, GAP), before=self.painel)
        else:
            self.cartao_fontes.pack(fill="x", pady=(0, GAP))

    def _municipio_escolhido(self) -> str:
        return self._municipio_de_rotulo.get(self.var_municipio.get(), "")

    def _recarregar_municipios(self) -> None:
        """Refaz a lista com a marca de quem tem catalogo, sem perder a escolha."""
        rotulos, self._municipio_de_rotulo = self.janela.rotulos_de_municipio()
        self._rotulos_municipio = rotulos
        self.combo_municipio.configure(values=rotulos)
        escolhido = self.estado.municipio
        alvo = next((r for r, m in self._municipio_de_rotulo.items()
                     if m == escolhido), "")
        self._silencio_fontes = True
        try:
            self.var_municipio.set(alvo)
        finally:
            self._silencio_fontes = False

    def _trocar_municipio(self) -> None:
        """Outro municipio, outro catalogo: recasa tudo e refaz a lista."""
        if self._silencio_fontes or not self.estado.tem_folha():
            return
        escolhido = self._municipio_escolhido()
        # Rotulo que nao esta na lista nao apaga o municipio escolhido: a caixa
        # e `readonly`, entao isso so acontece por engano de codigo -- e o
        # estrago seria mudo, com as 59 fontes voltando a ficar sem codigo.
        if not escolhido or escolhido == self.estado.municipio:
            return
        self.estado.municipio = escolhido
        self.janela.casar_fontes()
        self._montar_lista_fontes()
        self._mostrar_cartao_fontes(bool(self.janela.fontes_pendentes()))
        self._remontar()

    def _sincronizar_fontes(self) -> None:
        """Recasa ao voltar para esta tela: o catalogo pode ter sido importado.

        A lista e refeita quando o conjunto de pendencias mudou -- importar o
        arquivo do municipio certo costuma resolver todas de uma vez, e a
        lista antiga ficaria na tela dizendo que falta o que ja nao falta.
        """
        if not self.estado.tem_folha():
            return
        self._recarregar_municipios()
        self.janela.casar_fontes()
        pendentes = {c.fonte.chave for c in self.janela.fontes_pendentes()}
        if pendentes != set(self.campos_fonte):
            self._montar_lista_fontes()
        self._mostrar_cartao_fontes(bool(pendentes))
        self._atualizar_resumo_fontes()

    # ------------------------------------------------------------------ #
    # passo 4 e 5: numeros, avisos, tabela e exportacao
    # ------------------------------------------------------------------ #
    def _montar_resultado(self) -> None:
        self.painel = tk.Frame(self.corpo, bg=COR_FUNDO)

        # Os numeros ficam FORA do painel, e nao dentro como antes. O painel e
        # empacotado por ultimo, com `expand`, porque e ele que contem a tabela
        # e e a tabela que deve ceder altura; os numeros dentro dele sairiam
        # depois do que falta resolver, e e o contrario disso que se quer ver
        # primeiro. Soltos no corpo, eles entram logo abaixo dos documentos.
        numeros = self.quadro_numeros = tk.Frame(self.corpo, bg=COR_FUNDO)
        # TRES numeros, e nao cinco. Os cinco de antes punham lado a lado, com
        # o mesmo peso visual, coisas de importancia muito diferente: dois sao
        # as colunas 05 e 06 do arquivo, um e conferencia da leitura e outro
        # era contagem de pendencia -- que agora mora no cartao do que falta
        # resolver, junto com o que fazer a respeito. Com cinco, quem abria a
        # tela nao sabia em qual olhar; com tres, o primeiro olhar cai onde
        # deve.
        #
        # O PESO de cada coluna importa: com cartoes de mesma largura,
        # "4.767.480,36" nao cabe na fonte de 20 e sai cortado no ",36" -- o
        # pior corte possivel num numero de dinheiro. "774" nao precisa da
        # mesma largura, entao os de dinheiro recebem o dobro.
        cartoes = (("registros", "segurados", COR_PRIMARIA, 1),
                   ("base", "remuneração de contribuição", COR_PRIMARIA, 2),
                   ("segurado", "contribuição do segurado", COR_OK, 2))
        self.metricas: Dict[str, Metrica] = {}
        for indice, (chave, rotulo, cor, peso) in enumerate(cartoes):
            numeros.columnconfigure(indice, weight=peso)
            metrica = Metrica(numeros, "0", rotulo, cor_acento=cor)
            metrica.grid(row=0, column=indice, sticky="nsew",
                         padx=(0, 0 if indice == len(cartoes) - 1 else GAP))
            self.metricas[chave] = metrica

        # O balao responde no cartao e na linha da conta: quem estranha o
        # numero pousa o mouse onde estranhou, e nao onde a explicacao mora.
        self.balao_base = Balao(self.metricas["base"], self.EXPLICACAO_BASE)
        self._montar_conferencia()

        self._montar_avisos()
        self._montar_exportacao()
        self._montar_tabela()

    # A conta, escrita: proventos - o que nao entra na base = a base. E a
    # resposta a pergunta que aparece toda vez que alguem compara a tela com o
    # rodape da folha -- "4.126.327,68 nao bate com os 4.767.480,36 de
    # proventos". Nao bate mesmo, e nao pode bater: sao numeros de coisas
    # diferentes. Dito em uma linha, ao lado dos dois numeros, a duvida nao
    # chega a virar desconfianca da leitura do PDF.
    EXPLICACAO_BASE = (
        "Proventos é tudo o que a folha pagou; remuneração de contribuição é "
        "só a base do desconto previdenciário — e é ela que o layout pede na "
        "coluna 05.\n\n"
        "A diferença são as verbas que não compõem a base (aulas excedentes, "
        "horas extras, 1/3 de férias, insalubridade, periculosidade, "
        "gratificações, abono de permanência) e quem tem cargo efetivo "
        "exercendo cargo comissionado, que contribui sobre o vencimento do "
        "efetivo — a folha marca isso no bloco do servidor.\n\n"
        "E são, também, os servidores que não contribuem para o regime "
        "próprio: comissionado sem vínculo, contratado temporário e "
        "celetista descontam para o INSS, e a folha traz as duas "
        "previdências lado a lado. Eles aparecem com proventos e com base "
        "zero — é assim que tem de ser, porque essa contribuição não é do "
        "fundo municipal.\n\n"
        "Cada base está na coluna “Base” da própria verba de previdência, no "
        "PDF, e a verba de nota 10004 repete a mesma soma.")

    def _montar_conferencia(self) -> None:
        """A linha da conta, logo abaixo dos cartoes de numero."""
        self.faixa_conferencia = tk.Frame(self.corpo, bg=COR_FUNDO)
        self.var_conferencia = tk.StringVar(value="")
        self.rotulo_conferencia = tk.Label(
            self.faixa_conferencia, textvariable=self.var_conferencia,
            bg=COR_FUNDO, fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w",
            justify="left")
        self.rotulo_conferencia.pack(side="left", fill="x", expand=True,
                                     padx=(2, 0))
        # A frase cresceu quando passou a nomear quem esta fora do regime
        # proprio, e saia pela direita da tela. Quebra na largura disponivel.
        acompanhar_largura(self.rotulo_conferencia, folga=24)
        self.balao_conferencia = Balao(self.rotulo_conferencia,
                                       self.EXPLICACAO_BASE)

    def _pintar_conferencia(self, numeros: Dict[str, float]) -> None:
        fora = round(numeros["proventos"] - numeros["base"], 2)
        if not numeros["proventos"] or abs(fora) < 0.005:
            self.faixa_conferencia.pack_forget()
            return
        # Quem nao contribui para o regime proprio -- o servidor do INSS, o
        # contratado temporario -- aparece na folha com proventos e sem base. A
        # frase "verbas que nao compoem a base" sozinha fica enganosa onde eles
        # sao a maioria: em Barra do Garcas sao 2.339 de 3.327, e a diferenca
        # de dez milhoes parece erro de leitura quando e so gente de outro
        # regime. Entao, quando eles existem, eles sao nomeados.
        fora_do_regime = (len(self.estado.folha.sem_previdencia)
                          if self.estado.tem_folha() else 0)
        explicacao = "em verbas que não compõem a base"
        if fora_do_regime:
            explicacao = ("em verbas fora da base e em {} servidor(es) sem "
                          "contribuição ao regime próprio".format(
                              fora_do_regime))
        self.var_conferencia.set(
            "{} de proventos − {} {} = {} de remuneração de contribuição.  "
            "Passe o mouse para ver por quê."
            .format(_moeda(numeros["proventos"]), _moeda(fora), explicacao,
                    _moeda(numeros["base"])))
        # `after`: a faixa fica colada nos cartoes de numero, e nao no fim do
        # painel -- os avisos e a tabela sao empacotados depois dela.
        # A faixa mora colada EMBAIXO dos numeros, e `after` exige um irmao ja
        # empacotado. Preencher ano e mes dispara o `trace`, e portanto esta
        # pintura, antes de os numeros entrarem na tela: ai nao ha onde
        # ancorar, e empacotar assim mesmo poria a conta ACIMA dos numeros que
        # ela explica. Nao faz nada -- `ao_concluir` repinta depois de montar.
        if not self.quadro_numeros.winfo_manager():
            return
        self.faixa_conferencia.pack(fill="x", pady=(0, GAP),
                                    after=self.quadro_numeros)

    def _montar_avisos(self) -> None:
        """Faixa amarela com o que a leitura encontrou de estranho.

        Fica ENTRE os numeros e a tabela, e nao numa caixa de dialogo: aviso em
        dialogo e fechado sem ler, e o que ele dizia -- tres servidores sem
        contribuicao, duas paginas ilegiveis -- e exatamente o que precisa
        continuar a vista enquanto a tabela e conferida.
        """
        self.cartao_avisos = Superficie(self.painel, cor="#fdf8ec",
                                        contorno="#efe0bf", padding=(16, 12))
        linha = tk.Frame(self.cartao_avisos.corpo, bg="#fdf8ec")
        linha.pack(fill="x")
        chip(linha, icone("aviso"), cor="#f3e3c3", cor_glifo="#8a6d00",
             cor_fora="#fdf8ec", lado=30, tamanho=14).pack(
            side="left", padx=(0, 10))
        self.var_avisos = tk.StringVar()
        self.rotulo_avisos = tk.Label(
            linha, textvariable=self.var_avisos, bg="#fdf8ec", fg="#7a5c00",
            font=fonte(T_LEGENDA), anchor="w", justify="left", wraplength=820)
        self.rotulo_avisos.pack(side="left", fill="x", expand=True)
        acompanhar_largura(self.rotulo_avisos, folga=60)

    def _montar_tabela(self) -> None:
        cartao = Cartao(self.painel, titulo="Linhas do layout", glifo="planilha",
                        legenda="Clique num título para ordenar; botão direito "
                                "para filtrar. As três últimas colunas são de "
                                "conferência e não vão no arquivo.")
        cartao.pack(fill="both", expand=True, pady=(GAP, 0))
        self.cartao_tabela = cartao

        self.var_contagem = tk.StringVar(value="")
        tk.Label(cartao.acoes, textvariable=self.var_contagem, bg=COR_CARTAO,
                 fg=COR_MUDO, font=fonte(T_LEGENDA)).pack(side="right")

        moldura = CaixaCampo(cartao.conteudo, padding=(1, 1))
        moldura.pack(fill="both", expand=True)

        quadro = tk.Frame(moldura.corpo, bg=COR_CARTAO)
        quadro.pack(fill="both", expand=True)

        chaves = [c[0] for c in COLUNAS]
        # `height` e so o minimo: a tabela cresce com a janela (`expand`). Um
        # minimo alto demais empurra a barra de exportacao para fora da tela em
        # monitor de notebook.
        self.tabela = ttk.Treeview(quadro, columns=chaves, show="headings",
                                   height=8, selectmode="browse")
        for chave, titulo, largura, alinhamento in COLUNAS:
            self.tabela.column(chave, width=largura, minwidth=40,
                               anchor=alinhamento, stretch=(chave == "nome"))
        self.tabela.grid(row=0, column=0, sticky="nsew")

        vertical = ttk.Scrollbar(quadro, orient="vertical",
                                 command=self.tabela.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(quadro, orient="horizontal",
                                   command=self.tabela.xview)
        horizontal.grid(row=1, column=0, sticky="we")
        self.tabela.configure(yscrollcommand=vertical.set,
                              xscrollcommand=horizontal.set)
        quadro.rowconfigure(0, weight=1)
        quadro.columnconfigure(0, weight=1)

        # A linha com pendencia fica vermelha na tabela inteira: e o unico jeito
        # de achar tres linhas problematicas no meio de setecentas rolando.
        self.tabela.tag_configure("pendente", foreground=COR_ERRO)
        self.tabela.tag_configure("zebra", background=COR_CARTAO_FRACO)

        self.ordenador = Ordenador(
            self.tabela, {c[0]: c[1] for c in COLUNAS}, filtravel=True,
            ao_mudar=self._atualizar_contagem)
        self.tabela.bind("<Button-3>", self.ordenador.menu)

    def _montar_exportacao(self) -> None:
        """A barra de exportacao, ancorada no pe da TELA -- nao do painel.

        Fora do painel, e empacotada antes de todo o resto (ver
        `_mostrar_exportacao`), porque o `pack` serve os widgets na ordem em
        que os recebe e corta o ultimo quando falta espaco. Dentro do painel
        ela era servida depois das metricas e sobrava com 43 dos 82 pixels que
        pede: a caixa do modelo do layout virava um risco preto de 4 pixels, e
        e nela que se escolhe entre 10 e 8 colunas.

        Quem cede espaco agora e a tabela, que e quem pode: ela rola.
        """
        cartao = Cartao(self.corpo, padding=(18, 14))
        self.cartao_exportacao = cartao

        from arrecadacao.layout import (MODELO_COMPLETO, MODELO_REDUZIDO,
                                        NOMES_DOS_MODELOS)
        self._modelos = {NOMES_DOS_MODELOS[m]: m
                         for m in (MODELO_COMPLETO, MODELO_REDUZIDO)}

        escolha = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        escolha.pack(side="left", fill="x", expand=True)
        rotulo_campo(escolha, "Modelo do layout").pack(anchor="w", pady=(0, 4))
        self.var_modelo = tk.StringVar(value=NOMES_DOS_MODELOS[MODELO_COMPLETO])
        moldura = moldura_de_lista(escolha)
        moldura.pack(anchor="w")
        self.combo_modelo = ttk.Combobox(
            moldura.corpo, state="readonly", textvariable=self.var_modelo,
            width=38, values=list(self._modelos), style="Plano.TCombobox")
        self.combo_modelo.pack()
        moldura.acompanhar(self.combo_modelo)
        self.combo_modelo.bind("<MouseWheel>", lambda e: "break")

        Botao(cartao.conteudo, text="EXPORTAR XLSX", primario=True,
              command=lambda: self._exportar("xlsx")).pack(
            side="right", padx=(8, 0))
        Botao(cartao.conteudo, text="EXPORTAR CSV",
              command=lambda: self._exportar("csv")).pack(side="right")

    def _mostrar_exportacao(self, mostrar: bool) -> None:
        """`before`: entra na FRENTE da fila do pack, ancorada embaixo."""
        if mostrar == bool(self.cartao_exportacao.winfo_manager()):
            return
        if mostrar:
            self.cartao_exportacao.pack(side="bottom", fill="x", pady=(GAP, 0),
                                        before=self.cartao_arquivo)
        else:
            self.cartao_exportacao.pack_forget()

    # ------------------------------------------------------------------ #
    # leitura
    # ------------------------------------------------------------------ #
    def _iniciar(self) -> None:
        try:
            from arrecadacao import extracao
        except ImportError as exc:
            messagebox.showerror(
                APP_NOME,
                "Falta uma biblioteca para ler o PDF:\n\n{}\n\nInstale com:\n"
                "    python -m pip install -r requirements.txt".format(exc))
            return

        caminhos = list(self.caminhos_pdf)
        if not caminhos:
            return

        def tarefa(progresso):
            return extracao.ler_varios(caminhos, progresso)

        self.painel.pack_forget()
        self.quadro_numeros.pack_forget()
        self.faixa_conferencia.pack_forget()
        self._mostrar_exportacao(False)
        self.cartao_fontes.pack_forget()
        self.cartao_conferencia.pack_forget()
        self.cartao_competencia.pack_forget()
        self.janela.iniciar_trabalho(
            self.chave,
            "Lendo {}...".format(
                Path(caminhos[0]).name if len(caminhos) == 1
                else "{} documentos".format(len(caminhos))),
            tarefa)

    def ao_progresso(self, feitos: int, total: int, texto: str) -> None:
        self.btn_ler.configure(state="disabled")

    def ao_concluir(self, resultado: Any) -> None:
        folha = resultado
        self.btn_ler.configure(state="normal")

        if not folha.segurados:
            self.estado.limpar()
            self.janela.atualizar_barra()
            messagebox.showwarning(
                APP_NOME,
                "Nenhum segurado foi encontrado {}.\n\n".format(
                    "neste PDF" if len(self.caminhos_pdf) == 1
                    else "em nenhum dos documentos")
                + "\n".join(folha.avisos[:3]))
            self.janela.status("Nada encontrado no PDF.")
            return

        self.estado.folha = folha
        self.estado.caminho_pdf = folha.arquivo

        # O municipio sai do cabecalho da folha ("1 - DE ARIPUANA-MT") e e o
        # que decide contra qual catalogo as fontes vao casar. So e adivinhado
        # quando ainda nao ha um escolhido: trocar o municipio embaixo de quem
        # acabou de corrigi-lo a mao seria desfazer a correcao.
        from arrecadacao.municipios import reconhecer
        if not self.estado.municipio:
            self.estado.municipio = reconhecer(folha.entidade) or ""
        self._recarregar_municipios()
        self.janela.casar_fontes()

        competencia = folha.competencia_de_saida()
        # Preencher os campos dispara `_remontar` pelo trace -- e por isso a
        # montagem das linhas vem DEPOIS, e nao antes.
        if competencia is not None:
            self.var_ano.set(str(competencia.ano))
            self.var_mes.set("{:02d}".format(competencia.mes))
        else:
            self.var_ano.set("")
            self.var_mes.set("")
        # Com mais de um documento a origem e dita por documento: "o que foi
        # lido do cabecalho" de dois PDFs juntos nao e uma frase so, e e
        # justamente aqui que se percebe ter anexado a folha do mes errado.
        if len(folha.origens) > 1:
            self.var_origem.set("  ·  ".join(
                "{}: {} {}".format(o.nome, o.tipo or "tipo?",
                                   o.competencia or "sem competência")
                for o in folha.origens))
        else:
            self.var_origem.set("{} · {}".format(
                folha.tipo or "tipo não identificado",
                folha.entidade or "entidade não identificada"))
        if self.cartao_competencia.rotulo_legenda is not None:
            self.cartao_competencia.rotulo_legenda.configure(
                text="Confira o que foi lido do cabeçalho:  {}".format(
                    self.var_origem.get()))

        # A ordem aqui e a ordem na tela: o `pack` serve os widgets na sequencia
        # em que os recebe, e os tres foram recolhidos no inicio da leitura.
        # Nada de `before=self.painel` -- na primeira leitura o painel ainda nao
        # esta empacotado, e `before` exige um widget que ja esteja.
        # A ORDEM AQUI E A ORDEM NA TELA, porque o `pack` serve os widgets na
        # sequencia em que os recebe. E a ordem e o desenho da tela: primeiro
        # o que foi anexado, depois o que foi lido do cabecalho, depois os
        # numeros -- que sao a resposta --, depois o que FALTA fazer, depois o
        # que convem conferir, e so entao a tabela, que e para quem quer olhar
        # linha a linha. Antes os numeros vinham no meio da tabela e as duas
        # listas de fonte vinham antes deles; quem abria a tela via primeiro o
        # que nao tinha pedido.
        self._encolher_arquivo(True)
        self.cartao_competencia.pack(fill="x", pady=(0, GAP))
        self.quadro_numeros.pack(fill="x", pady=(0, GAP))
        # So entra na tela se esta folha trouxe estrutura sem codigo: na
        # segunda folha do mesmo municipio ja nao ha o que preencher, e o
        # cartao vazio tomaria a altura da tabela.
        self._montar_lista_fontes()
        self._mostrar_cartao_fontes(bool(self.janela.fontes_pendentes()))
        self._remontar()
        self._mostrar_exportacao(True)
        self.painel.pack(fill="both", expand=True)
        # Agora que o painel esta na tela ha onde ancorar o cartao de
        # conferencia -- ver `_mostrar_cartao_conferencia`.
        self._pintar_conferencia_fontes()
        self.janela.atualizar_barra()
        # A pagina acabou de ganhar todos os cartoes: sem isto ela nao
        # descobre que ja nao cabe. Ver `Tela.repensar_rolagem`.
        self.repensar_rolagem()
        self.janela.status(
            "{} segurado(s) lidos de {}.".format(
                folha.total_segurados,
                Path(folha.arquivo).name if len(folha.origens) == 1
                else "{} documentos".format(len(folha.origens))))

    def ao_falhar(self, detalhe: str) -> None:
        self.btn_ler.configure(state="normal")
        super().ao_falhar(detalhe)

    # ------------------------------------------------------------------ #
    # montagem da tabela
    # ------------------------------------------------------------------ #
    def _remontar(self) -> None:
        """Refaz as linhas a partir da folha lida. Nao rele o PDF.

        Chamado sempre que ano, mes, categoria ou o cadastro de fontes muda --
        cadastrar um codigo na outra tela tem de refletir aqui na volta, e
        reler 225 paginas para trocar um numero seria absurdo.
        """
        if not self.estado.tem_folha():
            return

        from arrecadacao.folha import Competencia
        from arrecadacao.layout import montar, resumo

        competencia = self._competencia_escolhida()
        self.linhas = montar(self.estado.folha, self.janela.codigo_da_fonte,
                             competencia=competencia,
                             categoria=self.var_categoria.get())
        self.estado.linhas = self.linhas

        numeros = resumo(self.linhas)
        self._pintar_tabela()
        self._pintar_metricas(numeros)
        self._pintar_conferencia(numeros)
        self._pintar_avisos()
        self._atualizar_resumo_fontes()
        self._pintar_conferencia_fontes()
        self.janela.atualizar_barra()

    def _competencia_escolhida(self):
        """A competencia dos campos, ou None se estiverem ilegiveis."""
        from arrecadacao.folha import Competencia
        try:
            return Competencia(ano=int(self.var_ano.get().strip()),
                               mes=int(self.var_mes.get().strip()))
        except (TypeError, ValueError):
            return None

    def _pintar_tabela(self) -> None:
        self.ordenador.esvaziar()
        for indice, linha in enumerate(self.linhas):
            etiquetas = []
            if linha.tem_pendencia:
                etiquetas.append("pendente")
            elif indice % 2:
                etiquetas.append("zebra")
            self.tabela.insert(
                "", "end", iid=str(indice), tags=tuple(etiquetas),
                values=(linha.matricula, linha.nome, linha.ano, linha.mes,
                        _moeda(linha.base), _moeda(linha.segurado),
                        _moeda(linha.patronal), linha.fonte or "—",
                        linha.categoria, linha.fonte_nome or "—",
                        linha.verbas or "—",
                        linha.pagina))
        self.ordenador.reaplicar()
        self._atualizar_contagem()

    def _atualizar_contagem(self) -> None:
        visiveis = self.ordenador.visiveis()
        total = self.ordenador.total()
        self.var_contagem.set(
            "{} de {} linhas".format(visiveis, total) if visiveis != total
            else "{} linhas".format(total))

    def _pintar_metricas(self, numeros: Dict[str, float]) -> None:
        self.metricas["registros"].definir(str(int(numeros["registros"])))
        self.metricas["base"].definir(_moeda(numeros["base"]))
        self.metricas["segurado"].definir(_moeda(numeros["segurado"]))

    def _pintar_avisos(self) -> None:
        # As fontes sem codigo NAO entram aqui: o cartao logo acima ja as
        # nomeia uma a uma e deixa preencher. Repetir o recado nesta faixa era
        # dizer duas vezes a mesma coisa, e cada linha dela sai da altura da
        # tabela.
        recados = list(getattr(self.estado.folha, "avisos", []))

        # O casamento so pelo numero NAO entra aqui: ele agora e uma linha do
        # cartao "Confira antes de exportar", junto com os outros pontos que
        # pedem olho e nao acao. Esta faixa fica so com o que a LEITURA do PDF
        # encontrou de estranho.
        self.repensar_rolagem()
        if not recados:
            self.cartao_avisos.pack_forget()
            return
        self.var_avisos.set("\n".join("• " + r for r in recados))
        self.cartao_avisos.pack(fill="x", pady=(GAP, 0),
                                before=self.cartao_tabela)

    # ------------------------------------------------------------------ #
    # exportacao
    # ------------------------------------------------------------------ #
    def _exportar(self, extensao: str) -> None:
        if not self.linhas:
            return

        from arrecadacao import exportacao
        modelo = self._modelos.get(self.var_modelo.get())

        if not self._confirmar_pendencias():
            return

        pasta, mudou = pasta_gravavel(self.janela.prefs.destino(
            Path(self.caminho_pdf).parent if self.caminho_pdf else None))
        if mudou:
            messagebox.showinfo(
                APP_NOME,
                "A pasta escolhida para as exportações não aceitou gravação."
                "\n\nO arquivo será salvo em:\n{}".format(pasta))

        sugerido = exportacao.nome_sugerido(self.estado.folha, modelo,
                                            extensao, self.estado.municipio)
        destino = filedialog.asksaveasfilename(
            title="Exportar {}".format(extensao.upper()),
            initialdir=str(pasta), initialfile=sugerido,
            defaultextension="." + extensao,
            filetypes=[(extensao.upper(), "*." + extensao),
                       ("Todos os arquivos", "*.*")])
        if not destino:
            return

        try:
            if extensao == "xlsx":
                exportacao.gravar_xlsx(self.linhas, Path(destino), modelo,
                                       self.estado.folha,
                                       self.estado.municipio)
            else:
                exportacao.gravar_csv(self.linhas, Path(destino), modelo)
        except PermissionError:
            messagebox.showerror(
                APP_NOME,
                "O arquivo está aberto em outro programa:\n\n{}\n\nFeche-o e "
                "exporte de novo.".format(destino))
            return
        except OSError as erro:
            messagebox.showerror(
                APP_NOME, "Não foi possível gravar:\n\n{}".format(erro))
            return

        self.estado.ultima_exportacao = destino
        competencia = self._competencia_escolhida()
        self.janela.indice.registrar(
            destino, extensao,
            "{} · {} · {} linha(s) · modelo {}".format(
                self.estado.municipio or "sem município",
                competencia or "sem competência", len(self.linhas), modelo))
        self.janela.status("Exportado: {}".format(destino))

        if messagebox.askyesno(
                APP_NOME,
                "Arquivo gerado:\n\n{}\n\nAbrir agora?".format(destino)):
            try:
                os.startfile(destino)      # type: ignore[attr-defined]
            except OSError:
                pass

    def _confirmar_pendencias(self) -> bool:
        """Pede confirmacao antes de exportar linha que o importador recusaria.

        Nao BLOQUEIA: ha caso legitimo -- exportar so para conferir, ou mandar
        o arquivo mesmo sabendo que tres linhas vao ser corrigidas a mao. Mas
        exportar 774 linhas com tres furos sem ninguem perceber e o modo mais
        facil de recolher a menos, e por isso a pergunta tem de ser feita antes
        de o arquivo existir, e nao depois.
        """
        pendentes = [l for l in self.linhas if l.tem_pendencia]
        if not pendentes:
            return True

        motivos: Dict[str, int] = {}
        for linha in pendentes:
            for motivo in linha.pendencias:
                motivos[motivo] = motivos.get(motivo, 0) + 1
        detalhe = "\n".join("   • {} — {} linha(s)".format(motivo, quantas)
                            for motivo, quantas in sorted(
                                motivos.items(), key=lambda i: -i[1]))
        return messagebox.askyesno(
            APP_NOME,
            "{} de {} linha(s) têm pendência e provavelmente serão recusadas "
            "na importação:\n\n{}\n\nExportar mesmo assim?".format(
                len(pendentes), len(self.linhas), detalhe))

    # ------------------------------------------------------------------ #
    def ao_entrar(self) -> None:
        # O codigo de uma fonte pode ter sido cadastrado na outra tela desde a
        # ultima vez que esta apareceu.
        if self.estado.tem_folha():
            self._sincronizar_fontes()
            self._remontar()
            self.janela.status("Confira a tabela e exporte.")
        else:
            self.janela.status("Anexe o PDF da folha de pagamento.")
