# -*- coding: utf-8 -*-
"""Tela principal: escolher o municipio, anexar as folhas, conferir e exportar.

O fluxo inteiro em uma tela so, revelado conforme acontece: antes de ler a
folha nao ha o que conferir, e a tela com tudo visivel e vazia pede para ser
ignorada. No alto, a trilha das quatro etapas -- as mesmas do Inicio -- diz
onde o trabalho esta e o que falta.

O MUNICIPIO vem primeiro, antes do PDF: e ele que traz as regras (o formato da
folha, o 13o da rescisao, o CSV que Nova Olimpia manda junto) -- ver
`arrecadacao.regras`. Trocar de municipio depois da leitura reaplica as regras
sem reler o PDF.

Depois da leitura, a ORDEM na tela e o desenho dela, e a ordem e esta:

    1. os documentos anexados -- um ou varios, porque a prefeitura e a camara
       sao PDFs separados e o SISPREVWEB recebe um arquivo por municipio;
    2. competencia e categoria, numa linha so -- corrigiveis, e quase nunca
       corrigidas;
    3. o CSV de segurados do SISPREVWEB. No alto, e nao no fim: ele traz a
       matricula do SISPREVWEB e confere a fonte de cada servidor, e o que nao
       bate tem de aparecer na tabela ANTES de exportar;
    4. OS NUMEROS: segurados, remuneracao de contribuicao e contribuicao do
       segurado. Sao a resposta, e e neles que o primeiro olhar tem de cair;
    5. a tabela, com o que cada linha precisa na coluna "Ajuste" e o ajuste
       feito nela mesma -- ver `arrecadacao.ajustes`;
    6. os tres arquivos: o final para importar, o sem alteracoes e a
       planilha.

Ja houve tres cartoes entre os numeros e a tabela -- fontes sem codigo, o que
conferir, as matriculas --, cada um com o seu jeito de resolver, e o que
sobrava so aparecia no fim, abrindo o arquivo de importacao para corrigir a
mao. Agora e uma tabela: a linha diz o que falta, a cor diz o quanto e grave,
e o duplo clique resolve ali.

A tabela mostra as colunas do layout mais as de conferencia, que nao vao no
arquivo -- a matricula da folha, a fonte da folha, as verbas somadas e a
pagina. Sao elas que permitem conferir uma linha contra o PDF: sem a pagina
nao ha como achar o servidor numa folha de 225 paginas.
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
from .componentes import (Balao, Botao, Cartao, CaixaCampo, Metrica, Passos,
                          caixa_de_marcar,
                          Superficie, acompanhar_largura, campo_texto, chip,
                          moldura_de_lista, rotulo_campo,
                          tornar_pesquisavel)
from .identidade import APP_NOME
from .ordenacao import Ordenador
from .preferencias import pasta_gravavel
from .tema import (COR_ACENTO_CLARO, COR_ATENCAO, COR_BORDA_CAMPO,
                   COR_CARTAO, COR_CHIP, COR_CHIP_TEXTO,
                   COR_DICA, COR_FUNDO, COR_MUDO, COR_OK,
                   COR_PRIMARIA, COR_TITULO, GAP, RAIO_LINHA, T_LEGENDA,
                   T_MINI, fonte, icone)

# As colunas da tabela. As tres ultimas nao vao no arquivo -- ver o modulo.
COLUNAS = (
    ("ajuste", "Ajuste", 260, "w"),
    ("matricula", "Mat. no arquivo", 110, "e"),
    ("matricula_folha", "Mat. na folha", 100, "e"),
    ("nome", "Nome", 230, "w"),
    # A fonte logo depois do nome, e nao na ordem do layout: e a coluna que
    # mais se ajusta, e la no fim ela so aparecia rolando a tabela de lado.
    ("fonte", "Fonte pagadora", 110, "center"),
    ("fonte_nome", "Nome fonte", 230, "w"),
    ("ano", "Ano", 55, "center"),
    ("mes", "Mês", 45, "center"),
    ("base", "Remun. Contrib.", 120, "e"),
    ("segurado", "Contrib. Segur.", 120, "e"),
    ("patronal", "Patronal normal", 115, "e"),
    ("categoria", "Categoria", 85, "w"),
    ("verbas", "Verbas", 90, "center"),
    ("pagina", "Pág.", 50, "center"),
)

# A cor de fundo de cada tipo de ajuste -- ver `arrecadacao.ajustes`. Vermelho
# trava a importacao; amarelo pede confirmacao; azul e sugestao de matricula;
# cinza e quem por padrao nao vai para o arquivo.
CORES_DO_AJUSTE = {
    "fonte": "#f8dada", "erro": "#f8dada", "fonte_sugerida": "#fcefd2",
    "fonte_repetida": "#fcefd2", "matricula_sugerida": "#e4ecf7",
    "matricula": "#fde3cf", "diverge": "#fff6d5", "zerada": "#eeeeee",
    "corrigido": "#e3f1e6", "alterado": "#ece4f7",
}

# A linha que nao precisava de nada e foi mexida -- as vezes sem querer.
ALTERADA_SEM_AJUSTE = ("o segurado não tinha ajustes a serem feitos e você "
                       "alterou algo na linha")

MESES = tuple("{:02d}".format(m) for m in range(1, 14))

def _moeda(valor: float) -> str:
    """1234.5 -> "1.234,50". A tabela e conferida contra o PDF, que usa isto."""
    return "{:,.2f}".format(float(valor or 0)).replace(",", "\x00") \
        .replace(".", ",").replace("\x00", ".")


class TelaFolha(Tela):
    chave = "folha"
    titulo = "Arrecadação"
    subtitulo = ("escolha o município, anexe as folhas, confira os números e "
                 "exporte o arquivo de importação")

    def montar(self) -> None:
        # Varios PDFs, e nao um: a arrecadacao de um mes raramente cabe num
        # arquivo so. A prefeitura exporta a folha dela e a camara a sua, e o
        # SISPREVWEB recebe UM arquivo por municipio -- lidos separados, os
        # dois viram duas exportacoes para conferir e importar em duplicata.
        self.caminhos_pdf: List[str] = []
        # O CSV que alguns municipios mandam junto (Nova Olimpia). Um so: e um
        # arquivo por competencia, e dois seriam duas versoes da mesma coisa.
        self.caminho_complementar: str = ""
        self.linhas: List[Any] = []
        # A comparacao com o cadastro do SISPREVWEB, refeita a cada
        # `_remontar` -- as linhas mudam com a competencia e as fontes.
        self.comparacao_sisprev: Any = None
        # O que foi ajustado na tabela, linha a linha -- ver
        # `arrecadacao.ajustes`. Da sessao: some ao ler outra folha.
        self.ajustes: Dict[str, dict] = {}
        # O que a linha tinha antes de ser corrigida na tabela: a linha fica
        # verde e o ajuste diz o que era, com "(corrigido)" -- sumir sem
        # rastro nao deixava saber se tinha corrigido mesmo.
        self.corrigidos: Dict[str, str] = {}
        self._editor: Optional[tk.Widget] = None
        # Com a tabela em tela cheia: (dono, [(widget, como estava no pack)])
        # de tudo o que saiu, na ordem, para voltar exatamente como era.
        self._escondidos: List[tuple] = []
        self._exportou = False
        self._silencio_fontes = False

        self._montar_trilha()
        self._montar_municipio()
        self._montar_arquivo()
        self._montar_competencia()
        self._montar_resultado()
        # Depois do resultado so porque pinta o botao da planilha, que mora
        # no cartao de exportar; na tela ele aparece logo abaixo da
        # competencia -- ver `ao_concluir`.
        self._montar_sisprev()

    @property
    def caminho_pdf(self) -> Optional[str]:
        """O primeiro documento. So para quem precisa de UM -- a pasta de saida."""
        return self.caminhos_pdf[0] if self.caminhos_pdf else None

    # ------------------------------------------------------------------ #
    # a trilha das etapas
    # ------------------------------------------------------------------ #
    def _montar_trilha(self) -> None:
        """As quatro etapas do Inicio, aqui pintadas com o estado de cada uma."""
        from .tela_inicio import ETAPAS

        self.cartao_trilha = Cartao(self.corpo, padding=(18, 10))
        self.cartao_trilha.pack(fill="x", pady=(0, GAP))
        self.trilha = Passos(self.cartao_trilha.conteudo, ETAPAS,
                             ao_clicar=self._clique_na_trilha)
        self.trilha.pack(fill="x")

    def _clique_na_trilha(self, etapa: int) -> None:
        if etapa == 0:
            self.combo_municipio.focus_set()
        elif etapa == 1:
            self._escolher()

    def _atualizar_trilha(self) -> None:
        """Onde o trabalho esta: feito em verde, a vez em navy, o resto apagado."""
        feita, atual, pendente = Passos.FEITA, Passos.ATUAL, Passos.PENDENTE
        regras = self.janela.regras_atuais()
        municipio = self.estado.municipio
        lida = self.estado.tem_folha()

        estados = [feita if municipio else atual]
        detalhes = [municipio or "escolha o município"]

        falta_csv = bool(regras.complementar) and not self.caminho_complementar
        if lida:
            estados.append(atual if falta_csv else feita)
            detalhes.append("{} segurado(s){}".format(
                self.estado.folha.total_segurados,
                " · falta o CSV" if falta_csv else ""))
        else:
            estados.append(atual if municipio else pendente)
            quantos = len(self.caminhos_pdf)
            detalhes.append(
                "{} documento(s) anexado(s)".format(quantos) if quantos
                else "anexe os PDFs" + (" e o CSV" if regras.complementar
                                        else ""))

        if lida:
            sem_codigo = len(self.janela.fontes_pendentes())
            com_pendencia = sum(1 for l in self.linhas if l.tem_pendencia)
            if sem_codigo:
                estados.append(atual)
                detalhes.append("{} fonte(s) sem código".format(sem_codigo))
            elif com_pendencia:
                estados.append(atual)
                detalhes.append("{} linha(s) com pendência".format(com_pendencia))
            else:
                estados.append(feita)
                detalhes.append("sem pendências")
        else:
            estados.append(pendente)
            detalhes.append("números, avisos e fontes")

        if self._exportou:
            estados.append(feita)
            detalhes.append("arquivo gerado")
        else:
            estados.append(atual if lida and estados[2] == feita else pendente)
            detalhes.append("o arquivo do SISPREVWEB")
        self.trilha.marcar(estados, detalhes)

    # ------------------------------------------------------------------ #
    # passo 0: o municipio, que traz as regras
    # ------------------------------------------------------------------ #
    def _montar_municipio(self) -> None:
        """O municipio decide as regras E o catalogo -- por isso vem primeiro.

        Vem adivinhado do cabecalho da folha quando ninguem escolheu antes, e
        fica a vista justamente porque adivinhar errado nao da erro: casa com o
        cadastro da cidade errada e credita a arrecadacao na fonte errada.
        """
        cartao = self.cartao_municipio = Cartao(
            self.corpo, titulo="Município", glifo="pessoas",
            legenda="Escolha antes de ler: o município traz as regras dele.")
        cartao.pack(fill="x", pady=(0, GAP))
        Botao(cartao.acoes, text="AJUSTAR AS REGRAS",
              command=lambda: self.janela.ir_para("municipios")).pack(
            side="right")

        linha = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        linha.pack(fill="x")

        # A caixa guarda o ROTULO ("✓  ARIPUANÃ"), e nao o nome puro: a marca
        # do catalogo importado precisa aparecer na lista fechada tambem, que e
        # onde se olha antes de trocar. `_municipio_escolhido` desfaz.
        self.var_municipio = tk.StringVar()
        self._municipio_de_rotulo: Dict[str, str] = {}
        moldura_mun = moldura_de_lista(linha)
        moldura_mun.pack(side="left", anchor="n")
        self.combo_municipio = ttk.Combobox(
            moldura_mun.corpo, textvariable=self.var_municipio,
            width=30, style="Plano.TCombobox")
        self.combo_municipio.pack()
        self._rotulos_municipio = []
        tornar_pesquisavel(self.combo_municipio,
                           lambda: self._rotulos_municipio)
        moldura_mun.acompanhar(self.combo_municipio)
        self.combo_municipio.bind("<MouseWheel>", lambda e: "break")

        self.var_regras = tk.StringVar(value="")
        self.rotulo_regras = tk.Label(
            linha, textvariable=self.var_regras, bg=COR_CARTAO, fg=COR_MUDO,
            font=fonte(T_LEGENDA), anchor="w", justify="left")
        self.rotulo_regras.pack(side="left", fill="x", expand=True,
                                padx=(GAP, 0))
        acompanhar_largura(self.rotulo_regras, folga=20)

        self.var_municipio.trace_add("write",
                                     lambda *_a: self._trocar_municipio())

    def _pintar_regras(self) -> None:
        """O que as regras do municipio escolhido vao fazer com a folha."""
        if not self.estado.municipio:
            self.var_regras.set("Nenhum município escolhido — valem as regras "
                                "gerais, e o catálogo de fontes fica sem "
                                "cidade para casar.")
            return
        regras = self.janela.regras_atuais()
        proprias = self.janela.config.configurado(self.estado.municipio)
        texto = "{}:  {}".format(
            "Regras próprias" if proprias else "Segue as regras gerais",
            "  ·  ".join(regras.resumo()))
        if regras.observacoes:
            texto += "\n" + regras.observacoes
        self.var_regras.set(texto)

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
            self.campos_competencia.pack(side="right", padx=(0, GAP),
                                         after=self.cartao_arquivo.acoes)
            if self.cartao_arquivo.rotulo_legenda is not None:
                self.cartao_arquivo.rotulo_legenda.configure(
                    text="  ·  ".join(p for p in (
                        self._descrever_documentos(), self.var_origem.get())
                        if p))
            self.repensar_rolagem()
            return

        self.btn_trocar.pack_forget()
        self.campos_competencia.pack_forget()
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
                       "entram juntas, e saem num arquivo só. O CSV "
                       "complementar, quando o município manda, vem junto.")

    def _descrever_documentos(self) -> str:
        """"2 documentos · geral.pdf, camara.pdf" -- para a linha encolhida."""
        nomes = [Path(c).name for c in self.caminhos_pdf]
        extra = (" + complementar {}".format(Path(self.caminho_complementar).name)
                 if self.caminho_complementar else "")
        if not nomes:
            return ("só o complementar " + Path(self.caminho_complementar).name
                    if self.caminho_complementar else "nenhum documento escolhido")
        if len(nomes) == 1:
            return nomes[0] + extra
        return "{} documentos · {}{}".format(len(nomes), ", ".join(nomes), extra)

    def _escolher(self) -> None:
        caminhos = filedialog.askopenfilenames(
            title="Folhas de pagamento (PDF) e arquivo complementar (CSV)",
            filetypes=[("PDF ou CSV", "*.pdf *.csv"), ("PDF", "*.pdf"),
                       ("CSV complementar", "*.csv"),
                       ("Todos os arquivos", "*.*")])
        if caminhos:
            self._definir(list(caminhos))

    def _soltar(self, caminhos: List[Path]) -> None:
        """Arrastar ACRESCENTA, em vez de substituir.

        Quem arrasta a folha da camara depois da folha da prefeitura quer as
        duas -- trocar uma pela outra em silencio seria perder a primeira sem
        nenhum sinal. Para recomecar ha o X de cada linha e o botao de trocar.
        """
        aceitos, recusados = arrastar.separar(caminhos, (".pdf", ".csv"))
        if not aceitos:
            messagebox.showwarning(
                APP_NOME,
                "A folha de pagamento é um arquivo .pdf (e o complementar, "
                ".csv).\n\nRecebido: "
                "{}".format(", ".join(c.name for c in recusados[:4])))
            return
        self._definir([str(c) for c in aceitos], acrescentar=True)

    # O botao e o arrasto passam pelo MESMO metodo: nada de um caminho habilitar
    # o botao de ler e o outro esquecer.
    def _definir(self, caminhos, acrescentar: bool = False) -> None:
        if isinstance(caminhos, str):
            caminhos = [caminhos]
        # O CSV vai para o lugar do complementar, e nao para a fila de PDFs: e
        # um arquivo de outro tipo, lido de outro jeito (ver
        # `arrecadacao.complementar`). Um novo substitui o anterior.
        csvs = [c for c in caminhos if c.lower().endswith(".csv")]
        caminhos = [c for c in caminhos if not c.lower().endswith(".csv")]
        if csvs:
            self.caminho_complementar = csvs[-1]
        elif not acrescentar:
            self.caminho_complementar = ""
        novos = list(self.caminhos_pdf) if acrescentar or not caminhos else []
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
        self._atualizar_trilha()

    def _montar_lista_documentos(self) -> None:
        """Uma linha por documento escolhido, com o X para tirar."""
        for filho in self.lista_documentos.winfo_children():
            filho.destroy()
        todos = list(self.caminhos_pdf)
        if self.caminho_complementar:
            todos.append(self.caminho_complementar)
        if not todos:
            self.lista_documentos.pack_forget()
            return

        for caminho in todos:
            linha = tk.Frame(self.lista_documentos, bg=COR_CARTAO)
            linha.pack(fill="x", pady=(6, 0))
            fechar = tk.Label(linha, text="✕", bg=COR_CARTAO, fg=COR_MUDO,
                              font=fonte(T_LEGENDA), cursor="hand2")
            fechar.pack(side="right", padx=(10, 0))
            fechar.bind("<Button-1>",
                        lambda _e, c=caminho: self._tirar_documento(c))
            Balao(fechar, "Tirar este documento da lista.")
            nome = Path(caminho).name
            if caminho == self.caminho_complementar:
                nome = "{}   (arquivo complementar)".format(nome)
            rotulo = tk.Label(linha, text=nome, bg=COR_CARTAO,
                              fg=COR_TITULO, font=fonte(T_LEGENDA),
                              anchor="w")
            rotulo.pack(side="left", fill="x", expand=True)
            Balao(rotulo, caminho)
        self.lista_documentos.pack(fill="x", pady=(10, 0),
                                   after=self.area_arquivo)

    def _tirar_documento(self, caminho: str) -> None:
        self.caminhos_pdf = [c for c in self.caminhos_pdf if c != caminho]
        if caminho == self.caminho_complementar:
            self.caminho_complementar = ""
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
        # No cabecalho do cartao da folha, ao lado do botao de trocar: sao tres
        # campos que quase nunca mudam, e um cartao proprio tomava a altura que
        # a tabela precisa. Aparecem so depois da leitura -- ver
        # `_encolher_arquivo`.
        campos = self.campos_competencia = tk.Frame(
            self.cartao_arquivo.cabeca, bg=COR_CARTAO)

        def rotulo(texto: str) -> None:
            tk.Label(campos, text=texto, bg=COR_CARTAO, fg=COR_MUDO,
                     font=fonte(T_LEGENDA)).pack(side="left", padx=(0, 6))

        rotulo("Ano")
        self.var_ano = tk.StringVar()
        caixa_ano, _entrada = campo_texto(campos, self.var_ano, largura=6,
                                          padding=(8, 4))
        caixa_ano.pack(side="left", padx=(0, GAP))

        rotulo("Mês (13 = 13º)")
        self.var_mes = tk.StringVar()
        moldura_mes = moldura_de_lista(campos)
        moldura_mes.pack(side="left", padx=(0, GAP))
        self.combo_mes = ttk.Combobox(moldura_mes.corpo, state="readonly",
                                      textvariable=self.var_mes, width=4,
                                      values=MESES, style="Plano.TCombobox")
        self.combo_mes.pack()
        moldura_mes.acompanhar(self.combo_mes)
        self.combo_mes.bind("<MouseWheel>", lambda e: "break")

        rotulo("Categoria")
        self.var_categoria = tk.StringVar()
        moldura_cat = moldura_de_lista(campos)
        moldura_cat.pack(side="left", padx=(0, GAP))
        from arrecadacao.folha import CATEGORIA_PADRAO, CATEGORIAS_ACEITAS
        self.var_categoria.set(CATEGORIA_PADRAO)
        self.combo_categoria = ttk.Combobox(
            moldura_cat.corpo, state="readonly", textvariable=self.var_categoria,
            width=18, values=list(CATEGORIAS_ACEITAS), style="Plano.TCombobox")
        self.combo_categoria.pack()
        moldura_cat.acompanhar(self.combo_categoria)
        self.combo_categoria.bind("<MouseWheel>", lambda e: "break")

        # O que foi lido do cabecalho vai na legenda do cartao, junto com os
        # nomes dos documentos.
        self.var_origem = tk.StringVar()

        for variavel in (self.var_ano, self.var_mes, self.var_categoria):
            variavel.trace_add("write", lambda *_a: self._remontar())

    def _copiar(self, texto: str) -> None:
        """Poe o texto na area de transferencia.

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
        """Outro municipio: outras regras e outro catalogo.

        Antes da leitura, so guarda a escolha -- as regras valem quando o PDF
        for lido. Depois, reaplica as regras sobre a folha ja lida e recasa as
        fontes, sem reler o PDF.
        """
        if self._silencio_fontes:
            return
        escolhido = self._municipio_escolhido()
        # Rotulo que nao esta na lista nao apaga o municipio escolhido: meio
        # nome digitado nao e escolha, e o estrago seria mudo, com as 59
        # fontes voltando a ficar sem codigo.
        if not escolhido or escolhido == self.estado.municipio:
            return
        self.estado.municipio = escolhido
        # Os ajustes da tabela eram contra o catalogo e o cadastro do outro
        # municipio.
        self.ajustes = {}
        self.corrigidos = {}
        # O cadastro de segurados era o do municipio anterior: casar a folha
        # de um com o cadastro de outro trocaria matriculas sem erro nenhum.
        if self.estado.cadastro_sisprev is not None:
            self.estado.cadastro_sisprev = None
            self.comparacao_sisprev = None
            self._pintar_sisprev()
        self._pintar_regras()
        if self.estado.folha_lida is not None:
            self.janela.aplicar_regras()
            self._aplicar_categoria()
            self._remontar()
        self.janela.atualizar_barra()
        self._atualizar_trilha()

    def _aplicar_categoria(self) -> None:
        """A categoria da regra do municipio, que a tela deixa corrigir."""
        categoria = self.janela.regras_atuais().categoria
        if categoria and categoria != self.var_categoria.get():
            self.var_categoria.set(categoria)

    def _sincronizar_fontes(self) -> None:
        """Recasa ao voltar para esta tela: o catalogo pode ter sido importado."""
        if not self.estado.tem_folha():
            return
        self._recarregar_municipios()
        self.janela.casar_fontes()

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
                        legenda="Duplo clique na fonte ou na matrícula para "
                                "ajustar; no nome, copia. Clique em Importar "
                                "para tirar ou pôr a linha no arquivo. Botão "
                                "direito no título filtra.")
        cartao.pack(fill="both", expand=True, pady=(GAP, 0))
        self.cartao_tabela = cartao

        self.var_contagem = tk.StringVar(value="")
        # No canto: o primeiro a entrar com side="right" e o mais a direita.
        self.btn_expandir = Botao(cartao.acoes, text="TELA CHEIA", sutil=True,
                                  command=self._alternar_expandida)
        self.btn_expandir.pack(side="right", padx=(12, 0))
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
        # A coluna da arvore (#0) e a unica que aceita imagem: e nela que mora
        # o check de importar, desenhado do tamanho do da janela de revisao.
        self.tabela = ttk.Treeview(quadro, columns=chaves,
                                   show="tree headings", height=14,
                                   selectmode="browse")
        self.tabela.column("#0", width=70, minwidth=70, stretch=False,
                           anchor="center")
        self.tabela.heading("#0", text="Importar")
        self._img_marcado = caixa_de_marcar(self.tabela, True)
        self._img_desmarcado = caixa_de_marcar(self.tabela, False)
        for chave, titulo, largura, alinhamento in COLUNAS:
            # Nome e ajuste nao encolhem: com quinze colunas, a que estica
            # virava a que cede, e o nome sumia. Sobrando pouco, a tabela rola
            # para o lado.
            self.tabela.column(chave, width=largura,
                               minwidth=largura if chave in ("nome", "ajuste")
                               else 40,
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

        # A cor da linha e a do ajuste mais grave dela; a linha que nao vai
        # para o arquivo fica com o texto apagado.
        for tipo, cor in CORES_DO_AJUSTE.items():
            self.tabela.tag_configure(tipo, background=cor)
        self.tabela.tag_configure("fora", foreground=COR_DICA)

        self.ordenador = Ordenador(
            self.tabela, {c[0]: c[1] for c in COLUNAS}, filtravel=True,
            ao_mudar=self._atualizar_contagem)
        self.tabela.bind("<Button-3>", self.ordenador.menu)
        self.tabela.bind("<Button-1>", self._clicar_tabela, add="+")
        self.tabela.bind("<Double-1>", self._editar_celula)
        self.tabela.bind("<Control-c>", lambda _e: self._copiar_nome())
        # O editor flutua sobre a celula: rolar a tabela o deixaria sobre a
        # linha errada.
        self.tabela.bind("<MouseWheel>", lambda _e: self._fechar_editor(),
                         add="+")

        self.btn_so_ajustes = Botao(cartao.acoes, text="SÓ O QUE PRECISA DE AJUSTE",
                                    sutil=True, command=self._alternar_so_ajustes)
        self.btn_so_ajustes.pack(side="right", padx=(0, 12))
        # Busca em todas as colunas: um nome, uma matricula, um codigo.
        self.var_busca = tk.StringVar()
        caixa_busca, _entrada = campo_texto(cartao.acoes, self.var_busca,
                                            largura=22, padding=(8, 4))
        caixa_busca.pack(side="right", padx=(0, 12))
        tk.Label(cartao.acoes, text="Buscar", bg=COR_CARTAO, fg=COR_MUDO,
                 font=fonte(T_LEGENDA)).pack(side="right", padx=(0, 6))
        self.var_busca.trace_add(
            "write", lambda *_a: self.ordenador.definir_busca(
                self.var_busca.get()))

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

        principal = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        principal.pack(fill="x")

        escolha = tk.Frame(principal, bg=COR_CARTAO)
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

        # Tres arquivos, com o nome do que cada um e: "EXPORTAR CSV" e
        # "EXPORTAR XLSX" nao diziam qual se importa.
        Botao(principal, text="ARQUIVO FINAL PARA IMPORTAÇÃO", primario=True,
              command=lambda: self._exportar("final")).pack(
            side="right", padx=(8, 0))
        Botao(principal, text="ARQUIVO SEM ALTERAÇÕES",
              command=lambda: self._exportar("original")).pack(
            side="right", padx=(8, 0))
        self.btn_planilha = Botao(principal, text="PLANILHA DE CONFERÊNCIA",
                                  command=lambda: self._exportar("planilha"))
        self.btn_planilha.pack(side="right")

    def _montar_sisprev(self) -> None:
        """O cadastro de segurados do SISPREVWEB, logo abaixo da competencia.

        No alto, e nao no fim: ele traz a matricula do SISPREVWEB e confere a
        fonte de cada servidor, e o que nao bate aparece na tabela para ajuste
        ANTES de exportar -- no fim, o que sobrava so era visto abrindo o
        arquivo de importacao para corrigir a mao.
        """
        self.cartao_sisprev = Cartao(self.corpo, padding=(18, 10))
        linha = tk.Frame(self.cartao_sisprev.conteudo, bg=COR_CARTAO)
        linha.pack(fill="x")

        texto = tk.Frame(linha, bg=COR_CARTAO)
        texto.pack(side="left", fill="x", expand=True)
        rotulo_campo(texto, "Cadastro de segurados do SISPREVWEB").pack(anchor="w")
        self.var_sisprev = tk.StringVar()
        self.rotulo_sisprev = tk.Label(
            texto, textvariable=self.var_sisprev, bg=COR_CARTAO, fg=COR_MUDO,
            font=fonte(T_LEGENDA), anchor="w", justify="left", wraplength=620)
        self.rotulo_sisprev.pack(anchor="w", fill="x", pady=(2, 0))
        acompanhar_largura(self.rotulo_sisprev, folga=16)

        self.btn_revisar_sisprev = Botao(
            linha, text="REVISAR SUGESTÕES", command=self._revisar_sugestoes,
            state="disabled")
        self.btn_revisar_sisprev.pack(side="right", padx=(8, 0))
        self.btn_anexar_sisprev = Botao(
            linha, text="ANEXAR CSV DO SISPREV", primario=True,
            command=self._anexar_sisprev)
        self.btn_anexar_sisprev.pack(side="right")
        self._pintar_sisprev()

    def _mostrar_exportacao(self, mostrar: bool) -> None:
        """`before`: entra na FRENTE da fila do pack, ancorada embaixo."""
        if mostrar == bool(self.cartao_exportacao.winfo_manager()):
            return
        if mostrar:
            self.cartao_exportacao.pack(side="bottom", fill="x", pady=(GAP, 0),
                                        before=self.cartao_trilha)
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

        regras = self.janela.regras_atuais()
        complementar = self.caminho_complementar
        if regras.complementar and not complementar:
            if not messagebox.askyesno(
                    APP_NOME,
                    "{} manda um arquivo complementar (CSV) junto com a folha, "
                    "e ele não foi anexado.\n\nSem ele a base de cada "
                    "servidor é deduzida da contribuição e pode ficar alguns "
                    "centavos longe da real.\n\nLer só o PDF mesmo "
                    "assim?".format(self.estado.municipio)):
                return

        def tarefa(progresso):
            from arrecadacao.complementar import (ArquivoComplementarInvalido,
                                                  ler_csv_sisprevweb)
            folha = extracao.ler_varios(caminhos, progresso, regras.formato)
            lido = None
            if complementar:
                nome = Path(complementar).name
                try:
                    lido = (nome, ler_csv_sisprevweb(complementar))
                except (OSError, ArquivoComplementarInvalido) as erro:
                    folha.avisos_de_leitura.append(
                        "O arquivo complementar não foi usado: {}".format(erro))
            return {"folha": folha, "complementar": lido}

        if self._escondidos:
            self._alternar_expandida()
        self.painel.pack_forget()
        self.quadro_numeros.pack_forget()
        self.faixa_conferencia.pack_forget()
        self._mostrar_exportacao(False)
        self.cartao_sisprev.pack_forget()
        self.janela.iniciar_trabalho(
            self.chave,
            "Lendo {}...".format(
                Path(caminhos[0]).name if len(caminhos) == 1
                else "{} documentos".format(len(caminhos))),
            tarefa)

    def ao_progresso(self, feitos: int, total: int, texto: str) -> None:
        self.btn_ler.configure(state="disabled")

    def ao_concluir(self, resultado: Any) -> None:
        folha = resultado["folha"]
        self.btn_ler.configure(state="normal")
        self._exportou = False
        self.ajustes = {}
        self.corrigidos = {}

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

        self.estado.folha_lida = folha
        self.estado.complementar = resultado["complementar"]
        self.estado.caminho_pdf = folha.arquivo

        # O municipio sai do cabecalho da folha ("1 - DE ARIPUANA-MT") quando
        # ninguem o escolheu antes. Escolhido, ele manda -- mas se a folha diz
        # outra cidade, a tela avisa: e o jeito de perceber que se anexou o PDF
        # do municipio errado antes de creditar nas fontes erradas.
        from arrecadacao.municipios import reconhecer
        lista = self.janela.config.lista_de_municipios()
        lidos = {m for m in (reconhecer(o.entidade, lista)
                             for o in folha.origens if o.entidade) if m}
        if not self.estado.municipio:
            self.estado.municipio = next(iter(lidos), "") if len(lidos) == 1 \
                else (reconhecer(folha.entidade, lista) or "")
        estranhos = sorted(lidos - {self.estado.municipio})
        if estranhos:
            folha.avisos_de_leitura.append(
                "O município escolhido é {}, mas o cabeçalho da folha fala em "
                "{}. Confira se os documentos são deste município.".format(
                    self.estado.municipio, ", ".join(estranhos)))
        self._recarregar_municipios()
        self._pintar_regras()
        self.janela.aplicar_regras()
        folha = self.estado.folha
        self._aplicar_categoria()

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
            # So o tipo: a entidade repete o municipio, que esta escolhido no
            # cartao de cima, e o texto longo encostava nos campos da
            # competencia, na mesma linha.
            self.var_origem.set(folha.tipo or "tipo não identificado")

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
        self.cartao_sisprev.pack(fill="x", pady=(0, GAP))
        self.quadro_numeros.pack(fill="x", pady=(0, GAP))
        self._remontar()
        self._mostrar_exportacao(True)
        self.painel.pack(fill="both", expand=True)
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
        # A fonte escolhida para uma linha entra ANTES da comparacao: e ela
        # que a conferencia contra o cadastro tem de ver.
        from arrecadacao.ajustes import aplicar_fontes
        aplicar_fontes(self.linhas, self.ajustes)

        self._comparar_sisprev()
        numeros = resumo(self.linhas)
        self._pintar_tabela()
        self._pintar_metricas(numeros)
        self._pintar_conferencia(numeros)
        self._pintar_avisos()
        self.janela.atualizar_barra()
        self._atualizar_trilha()

    def _competencia_escolhida(self):
        """A competencia dos campos, ou None se estiverem ilegiveis."""
        from arrecadacao.folha import Competencia
        try:
            return Competencia(ano=int(self.var_ano.get().strip()),
                               mes=int(self.var_mes.get().strip()))
        except (TypeError, ValueError):
            return None

    def _pintar_tabela(self) -> None:
        self._fechar_editor()
        comparacoes = self._comparacoes_por_linha()
        por_fonte = {str(c.fonte): c for c in
                     self.estado.correspondencias.values()}
        repetidos = self._codigos_repetidos()
        self.ordenador.esvaziar()
        for indice, linha in enumerate(self.linhas):
            imagem, etiquetas, valores = self._conteudo_da_linha(
                linha, comparacoes.get(id(linha)), por_fonte, repetidos)
            self.tabela.insert("", "end", iid=str(indice), image=imagem,
                               tags=etiquetas, values=valores)
        self.ordenador.reaplicar()
        self._atualizar_contagem()

    def _conteudo_da_linha(self, linha, comparacao, por_fonte, repetidos):
        """(imagem do check, etiquetas, valores) de uma linha da tabela."""
        from arrecadacao.ajustes import chave, diagnosticar, importa, \
            matricula_final
        ajuste = self.ajustes.get(chave(linha))
        achados = diagnosticar(linha, por_fonte.get(linha.fonte_nome),
                               comparacao, ajuste, repetidos)
        texto = "; ".join(texto for _tipo, texto in achados)
        etiquetas = [achados[0][0]] if achados else []
        antes = self.corrigidos.get(chave(linha))
        marcada = importa(linha, ajuste)
        if antes and not achados:
            etiquetas, texto = ["corrigido"], "{} (corrigido)".format(antes)
        elif not antes and not achados and ajuste and (
                ajuste.get("fonte") or ajuste.get("matricula")
                or marcada != (linha.segurado > 0)):
            # Nao precisava de nada, e alguem mexeu: pode ter sido sem querer.
            etiquetas, texto = ["alterado"], ALTERADA_SEM_AJUSTE
        if not marcada:
            etiquetas.append("fora")
        return (self._img_marcado if marcada else self._img_desmarcado,
                tuple(etiquetas),
                # A setinha diz que a celula abre uma lista no duplo clique.
                (texto or "—", "{}  ▾".format(
                    matricula_final(linha, comparacao, ajuste)),
                 linha.matricula, linha.nome,
                 "{}  ▾".format(linha.fonte or "—"),
                 linha.fonte_nome or "—", linha.ano, linha.mes,
                 _moeda(linha.base), _moeda(linha.segurado),
                 _moeda(linha.patronal), linha.categoria,
                 linha.verbas or "—", linha.pagina))

    def _comparacoes_por_linha(self) -> Dict[int, Any]:
        if self.comparacao_sisprev is None:
            return {}
        return {id(c.linha): c for c in self.comparacao_sisprev.comparacoes}

    def _codigos_repetidos(self) -> set:
        """Codigos dados a mais de uma fonte da folha: soma certa, fonte errada."""
        por_codigo: Dict[str, int] = {}
        for correspondencia in self.estado.correspondencias.values():
            if correspondencia.codigo:
                por_codigo[correspondencia.codigo] = \
                    por_codigo.get(correspondencia.codigo, 0) + 1
        return {c for c, n in por_codigo.items() if n > 1}

    def linhas_finais(self) -> List[Any]:
        """O arquivo de importacao: as marcadas, com a matricula final."""
        from arrecadacao.ajustes import linhas_finais
        return linhas_finais(self.linhas, self._comparacoes_por_linha(),
                             self.ajustes)

    # ------------------------------------------------------------------ #
    # ajustes na tabela
    # ------------------------------------------------------------------ #
    def _linha_em(self, evento):
        """(iid, coluna, linha) sob o mouse, ou (None, '', None)."""
        if self.tabela.identify_region(evento.x, evento.y) not in ("cell",
                                                                    "tree"):
            return None, "", None
        iid = self.tabela.identify_row(evento.y)
        if not iid:
            return None, "", None
        coluna = "importar" if self.tabela.identify_column(evento.x) == "#0" \
            else self.ordenador.coluna_em(evento.x)
        return iid, coluna, self.linhas[int(iid)]

    def _clicar_tabela(self, evento) -> None:
        self._fechar_editor()
        iid, coluna, linha = self._linha_em(evento)
        if linha is None or coluna != "importar":
            return
        from arrecadacao.ajustes import chave, importa
        ajuste = self.ajustes.setdefault(chave(linha), {})
        ajuste["importar"] = not importa(linha, ajuste)
        # So esta linha: refazer a tabela inteira a cada clique perderia a
        # rolagem de quem esta desmarcando uma por uma.
        imagem, etiquetas, valores = self._conteudo_da_linha(
            linha, self._comparacoes_por_linha().get(id(linha)),
            {str(c.fonte): c for c in self.estado.correspondencias.values()},
            self._codigos_repetidos())
        self.tabela.item(iid, image=imagem, tags=etiquetas, values=valores)
        self._atualizar_contagem()

    def _copiar_nome(self) -> None:
        escolha = self.tabela.selection()
        if escolha:
            self._copiar(self.linhas[int(escolha[0])].nome)

    def _fechar_editor(self) -> None:
        if self._editor is not None:
            self._editor.destroy()
            self._editor = None

    def _lembrar(self, linhas) -> None:
        """Guarda o ajuste que estas linhas mostram, antes de corrigi-las."""
        from arrecadacao.ajustes import chave
        indice = {id(l): i for i, l in enumerate(self.linhas)}
        for linha in linhas:
            i = indice.get(id(linha))
            if i is None or not self.tabela.exists(str(i)):
                continue
            texto = self.tabela.set(str(i), "ajuste")
            if texto and texto != "—" and not texto.endswith("(corrigido)"):
                self.corrigidos[chave(linha)] = texto

    def _editar_celula(self, evento) -> str:
        """Duplo clique: copia o nome, ou abre a lista da fonte ou da matricula.

        Campo com a lista embaixo, e nao um Combobox: a lista do Combobox
        abre roubando o foco, e o que se digitava nao filtrava nada. Aqui se
        digita e a lista encolhe; setas escolhem, Enter confirma. Na matricula
        vale tambem o que for digitado e nao estiver na lista.
        """
        self._fechar_editor()
        iid, coluna, linha = self._linha_em(evento)
        if linha is None:
            return "break"
        if coluna == "nome":
            self._copiar(linha.nome)
            return "break"
        if coluna not in ("fonte", "matricula"):
            return "break"
        caixa = self.tabela.bbox(iid, coluna)
        if not caixa:
            return "break"
        if coluna == "fonte":
            opcoes = self._opcoes_fonte(linha)
            aplicar = self._aplicar_fonte
        else:
            opcoes = self._opcoes_matricula(linha)
            aplicar = self._aplicar_matricula
        livre = coluna == "matricula"
        rotulos = list(opcoes)

        from arrecadacao.fontes import normalizar
        x, y, largura, _altura = caixa
        quadro = tk.Frame(self.tabela, bg=COR_BORDA_CAMPO)
        quadro.place(x=x, y=y, width=max(largura, 420))
        texto = tk.StringVar()
        entrada = tk.Entry(quadro, textvariable=texto, relief="flat", bd=0,
                           font=fonte(T_LEGENDA), bg=COR_CARTAO)
        entrada.pack(fill="x", padx=1, pady=1, ipady=4)
        lista = tk.Listbox(quadro, relief="flat", bd=0, font=fonte(T_LEGENDA),
                           activestyle="none", exportselection=False,
                           selectbackground=COR_PRIMARIA)
        lista.pack(fill="x", padx=1, pady=(0, 1))
        self._editor = quadro

        def filtrar(*_a) -> None:
            procurado = normalizar(texto.get())
            visiveis = [r for r in rotulos if procurado in normalizar(r)]
            lista.delete(0, "end")
            for rotulo in visiveis:
                lista.insert("end", rotulo)
            lista.configure(height=max(1, min(10, len(visiveis))))
            if visiveis:
                lista.selection_set(0)

        def mover(passo: int) -> str:
            if lista.size():
                atual = lista.curselection()
                i = max(0, min(lista.size() - 1,
                               (atual[0] if atual else -1) + passo))
                lista.selection_clear(0, "end")
                lista.selection_set(i)
                lista.see(i)
            return "break"

        def confirmar(_evento=None) -> str:
            atual = lista.curselection()
            escolhido = lista.get(atual[0]) if atual else (
                texto.get().strip() if livre else "")
            self._fechar_editor()
            if escolhido:
                aplicar(linha, opcoes.get(escolhido, escolhido))
            return "break"

        texto.trace_add("write", filtrar)
        entrada.bind("<Down>", lambda _e: mover(1))
        entrada.bind("<Up>", lambda _e: mover(-1))
        entrada.bind("<Return>", confirmar)
        entrada.bind("<Escape>", lambda _e: self._fechar_editor())
        lista.bind("<ButtonRelease-1>", confirmar)
        filtrar()
        entrada.focus_set()
        return "break"

    def _opcoes_fonte(self, linha) -> Dict[str, str]:
        """{rotulo: codigo}: a sugestao primeiro, depois o catalogo inteiro."""
        catalogo = self.janela.cadastro.fontes_de(self.estado.municipio)
        correspondencia = next(
            (c for c in self.estado.correspondencias.values()
             if str(c.fonte) == linha.fonte_nome), None)
        sugerido = getattr(correspondencia, "sugerido", None)
        primeiras = [sugerido] if sugerido is not None else []
        opcoes: Dict[str, str] = {}
        for item in primeiras + [f for f in catalogo if f is not sugerido]:
            opcoes["{} — {}".format(item.codigo, item.nome)] = item.codigo
        return opcoes

    def _aplicar_fonte(self, linha, codigo: str) -> None:
        """Grupo sem codigo: a escolha e do grupo, gravada para os proximos
        meses. Grupo ja resolvido: a escolha e so desta linha."""
        from arrecadacao.ajustes import chave
        codigo = codigo.split(" ")[0]
        if not codigo.isdigit():
            self.janela.status("O código da fonte pagadora é só número: {}"
                               .format(codigo))
            return
        correspondencia = next(
            (c for c in self.estado.correspondencias.values()
             if str(c.fonte) == linha.fonte_nome), None)
        if correspondencia is not None and not correspondencia.codigo:
            self._lembrar([l for l in self.linhas
                           if l.fonte_nome == linha.fonte_nome])
            cadastro = self.janela.cadastro
            cadastro.escolher(self.estado.municipio, correspondencia.fonte, codigo)
            gravou = cadastro.salvar()
            self.janela.casar_fontes()
            self.janela.status(
                "Fonte {} gravada para {}{}.".format(
                    codigo, correspondencia.fonte,
                    "" if gravou else " (só nesta sessão: o cadastro não pôde "
                    "ser gravado)"))
        else:
            self._lembrar([linha])
            ajuste = self.ajustes.setdefault(chave(linha), {})
            if codigo == (correspondencia.codigo if correspondencia else ""):
                ajuste.pop("fonte", None)
            else:
                ajuste["fonte"] = codigo
            self.janela.status("Fonte {} só para {}.".format(codigo, linha.nome))
        self._remontar()

    def _opcoes_matricula(self, linha) -> Dict[str, str]:
        """A sugestao do SISPREVWEB, a da folha, ou o que for digitado."""
        comparacao = self._comparacoes_por_linha().get(id(linha))
        opcoes: Dict[str, str] = {}
        if comparacao is not None and comparacao.sugerido is not None \
                and not comparacao.aceita:
            opcoes["{} — {} (sugestão)".format(
                comparacao.sugerido.codigo,
                comparacao.sugerido.nome)] = "sugestao"
        if comparacao is not None and comparacao.codigo_sisprev:
            opcoes["{} (SISPREVWEB)".format(comparacao.codigo_sisprev)] = \
                comparacao.codigo_sisprev
        opcoes["{} (matrícula da folha)".format(linha.matricula)] = \
            linha.matricula
        return opcoes

    def _aplicar_matricula(self, linha, escolha: str) -> None:
        """A sugestao aceita fica gravada (`Aceites`); a digitada, na sessao."""
        from arrecadacao.ajustes import chave
        self._lembrar([linha])
        ajuste = self.ajustes.setdefault(chave(linha), {})
        comparacao = self._comparacoes_por_linha().get(id(linha))
        if escolha == "sugestao" and comparacao is not None:
            self.janela.aceites.aceitar(self.estado.municipio, comparacao.linha,
                                        comparacao.sugerido)
            self.janela.aceites.salvar()
            ajuste.pop("matricula", None)
        else:
            codigo = escolha.split(" ")[0]
            automatica = comparacao.matricula_ajustada if comparacao \
                else linha.matricula
            if codigo == automatica:
                ajuste.pop("matricula", None)
            else:
                ajuste["matricula"] = codigo
        self._remontar()

    def _alternar_expandida(self) -> None:
        """A tabela na tela toda, para editar; de novo, volta ao que era.

        Tira do `pack` tudo o que nao e a tabela -- trilha, municipio, folha,
        cadastro, numeros, avisos e o cartao de exportar -- e guarda a ordem e
        as opcoes de cada um. Voltar refaz o pack de TODOS na ordem guardada:
        recolocar so os escondidos os poria depois da tabela.
        """
        self._fechar_editor()
        if self._escondidos:
            for dono, fila in self._escondidos:
                for widget, _opcoes in fila:
                    widget.pack_forget()
                for widget, opcoes in fila:
                    widget.pack_configure(opcoes)
            self._escondidos = []
            self.btn_expandir.configure(text="TELA CHEIA")
        else:
            for dono in (self.corpo, self.painel):
                fila = [(w, w.pack_info()) for w in dono.pack_slaves()]
                self._escondidos.append((dono, fila))
                for widget, _opcoes in fila:
                    if widget not in (self.painel, self.cartao_tabela):
                        widget.pack_forget()
            self.btn_expandir.configure(text="VOLTAR AO NORMAL")
        self.repensar_rolagem()

    def _alternar_so_ajustes(self) -> None:
        if self.ordenador.filtros.get("ajuste"):
            self.ordenador.definir_filtro("ajuste", set())
            self.btn_so_ajustes.configure(text="SÓ O QUE PRECISA DE AJUSTE")
            return
        valores = {v for v, _n in self.ordenador.valores_de("ajuste")
                   if v != "—"}
        if not valores:
            self.janela.status("Nenhuma linha precisa de ajuste.")
            return
        self.ordenador.definir_filtro("ajuste", valores)
        self.btn_so_ajustes.configure(text="MOSTRAR TODAS")

    def _atualizar_contagem(self) -> None:
        visiveis = self.ordenador.visiveis()
        total = self.ordenador.total()
        marcadas = len(self.linhas_finais())
        self.var_contagem.set("{}  ·  {} vão para o arquivo".format(
            "{} de {} linhas".format(visiveis, total) if visiveis != total
            else "{} linhas".format(total), marcadas))

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
    def _exportar(self, tipo: str) -> None:
        """`final`: o arquivo para importar, com os ajustes e so as linhas
        marcadas. `original`: a folha como foi lida, sem nada do SISPREVWEB.
        `planilha`: a comparacao SISPREVWEB x folha, ou a planilha de
        conferencia quando o cadastro nao foi anexado."""
        if not self.linhas:
            return
        from arrecadacao import exportacao
        modelo = self._modelos.get(self.var_modelo.get())
        linhas = self.linhas_finais() if tipo == "final" else self.linhas
        if tipo == "final" and not linhas:
            messagebox.showinfo(APP_NOME, "Nenhuma linha está marcada para "
                                "importar.")
            return
        if tipo == "final" and not self._confirmar_pendencias(linhas):
            return

        pasta, mudou = pasta_gravavel(self.janela.prefs.destino(
            Path(self.caminho_pdf).parent if self.caminho_pdf else None))
        if mudou:
            messagebox.showinfo(
                APP_NOME,
                "A pasta escolhida para as exportações não aceitou gravação."
                "\n\nO arquivo será salvo em:\n{}".format(pasta))

        comparacao = self.comparacao_sisprev
        extensao = "xlsx" if tipo == "planilha" else "csv"
        base = exportacao.nome_sugerido(self.estado.folha, modelo, extensao,
                                        self.estado.municipio)[:-len(extensao) - 1]
        sufixo = {"final": "", "original": "_SemAlteracoes",
                  "planilha": "_ComparacaoSisprev" if comparacao is not None
                  else ""}[tipo]
        titulo = {"final": "Arquivo final para importação",
                  "original": "Arquivo sem alterações",
                  "planilha": "Comparação SISPREVWEB × folha"
                  if comparacao is not None else "Planilha de conferência"}[tipo]
        destino = filedialog.asksaveasfilename(
            title=titulo, initialdir=str(pasta),
            initialfile="{}{}.{}".format(base, sufixo, extensao),
            defaultextension="." + extensao,
            filetypes=[(extensao.upper(), "*." + extensao),
                       ("Todos os arquivos", "*.*")])
        if not destino:
            return

        try:
            if tipo == "planilha" and comparacao is not None:
                exportacao.gravar_comparacao_xlsx(
                    comparacao, Path(destino), self.estado.folha,
                    self.estado.municipio)
            elif tipo == "planilha":
                exportacao.gravar_xlsx(self.linhas, Path(destino), modelo,
                                       self.estado.folha,
                                       self.estado.municipio)
            else:
                exportacao.gravar_csv(linhas, Path(destino), modelo)
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
        if tipo == "final":
            self._exportou = True
            self._atualizar_trilha()
        competencia = self._competencia_escolhida()
        self.janela.indice.registrar(
            destino, extensao,
            "{} · {} · {} linha(s) · {}".format(
                self.estado.municipio or "sem município",
                competencia or "sem competência", len(linhas), titulo.lower()))
        self.janela.status("Exportado: {}".format(destino))

        if messagebox.askyesno(
                APP_NOME,
                "{}:\n\n{}\n\nAbrir agora?".format(titulo, destino)):
            try:
                os.startfile(destino)      # type: ignore[attr-defined]
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # matriculas do SISPREVWEB
    # ------------------------------------------------------------------ #
    def _anexar_sisprev(self) -> None:
        from arrecadacao.segurados_sisprev import CadastroInvalido, ler_cadastro
        inicial = Path(self.caminho_pdf).parent if self.caminho_pdf else None
        caminho = filedialog.askopenfilename(
            title="Cadastro de segurados exportado pelo SISPREVWEB (CSV)",
            initialdir=str(inicial) if inicial else None,
            filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")])
        if not caminho:
            return
        try:
            segurados = ler_cadastro(caminho)
        except (OSError, CadastroInvalido) as erro:
            messagebox.showerror(APP_NOME, str(erro))
            return
        self.estado.cadastro_sisprev = (caminho, segurados)
        self._remontar()
        self.repensar_rolagem()
        if self.comparacao_sisprev is not None:
            self.janela.status("Cadastro do SISPREVWEB comparado: {}.".format(
                ", ".join("{} {}".format(quantos, situacao.lower())
                          for situacao, quantos
                          in self.comparacao_sisprev.contagem().items())))

    def _comparar_sisprev(self) -> None:
        cadastro = self.estado.cadastro_sisprev
        if cadastro is None or not self.linhas:
            self.comparacao_sisprev = None
        else:
            from arrecadacao.segurados_sisprev import (comparar,
                                                       conferir_fontes)
            caminho, segurados = cadastro
            self.comparacao_sisprev = comparar(
                self.linhas, segurados, caminho,
                aceitas=self.janela.aceites.codigos(self.estado.municipio))
            conferir_fontes(self.comparacao_sisprev, segurados, {
                f.codigo: f.nome for f in
                self.janela.cadastro.fontes_de(self.estado.municipio)})
        self._pintar_sisprev()

    def _pintar_sisprev(self) -> None:
        resultado = self.comparacao_sisprev
        if resultado is None:
            self.var_sisprev.set(
                "A matrícula da folha quase nunca é o código do segurado no "
                "SISPREVWEB. Anexe o CSV de segurados exportado por ele para "
                "trocar pelo código certo (casa por nome + data de admissão).")
            self.rotulo_sisprev.configure(fg=COR_MUDO)
            self.btn_planilha.configure(text="PLANILHA DE CONFERÊNCIA")
            self.btn_revisar_sisprev.configure(
                text="REVISAR SUGESTÕES", state="disabled")
            return
        from arrecadacao.segurados_sisprev import (DIFERENTE, ENCONTRADA,
                                                   NAO_ENCONTRADO)
        quantos = resultado.contagem()
        pendentes = sum(1 for c in resultado.comparacoes
                        if c.situacao == NAO_ENCONTRADO and c.sugerido)
        aceitas = sum(1 for c in resultado.comparacoes if c.aceita)
        detalhes = []
        if pendentes:
            detalhes.append("{} com sugestão para revisar".format(pendentes))
        if aceitas:
            detalhes.append("{} sugestão(ões) aceita(s)".format(aceitas))
        if resultado.repetidos:
            detalhes.append("{} código(s) repetido(s) no SISPREVWEB: {}".format(
                len(resultado.repetidos), ", ".join(sorted(resultado.repetidos))))
        self.var_sisprev.set(
            "{}:  {} com a mesma matrícula · {} com matrícula trocada · {} não "
            "encontrado(s){}".format(
                Path(resultado.arquivo).name, quantos[ENCONTRADA],
                quantos[DIFERENTE], quantos[NAO_ENCONTRADO],
                " ({})".format(", ".join(detalhes)) if detalhes else ""))
        self.rotulo_sisprev.configure(
            fg=COR_ATENCAO if quantos[NAO_ENCONTRADO] else COR_OK)
        self.btn_planilha.configure(text="COMPARAÇÃO SISPREV × FOLHA")
        self.btn_revisar_sisprev.configure(
            text="REVISAR SUGESTÕES ({})".format(pendentes) if pendentes
            else "REVISAR SUGESTÕES",
            state="normal" if pendentes or aceitas else "disabled")

    def _revisar_sugestoes(self) -> None:
        """Abre a revisao com as pendentes e as ja aceitas, lado a lado.

        As aceitas vao junto, marcadas, para poderem ser desfeitas: o aceite
        de um mes atras pode ter sido engano, e sem isto ele seria eterno.
        """
        resultado = self.comparacao_sisprev
        if resultado is None:
            return
        from .revisar_sugestoes import RevisarSugestoes
        itens = [c for c in resultado.comparacoes if c.sugerido is not None]
        if not itens:
            return

        def salvar(escolhas: Dict[int, bool]) -> None:
            aceites = self.janela.aceites
            municipio = self.estado.municipio
            novas = desfeitas = 0
            for indice, marcada in escolhas.items():
                comparacao = itens[indice]
                if marcada and not comparacao.aceita:
                    self._lembrar([comparacao.linha])
                    aceites.aceitar(municipio, comparacao.linha,
                                    comparacao.sugerido)
                    novas += 1
                elif not marcada and comparacao.aceita:
                    aceites.desfazer(municipio, comparacao.linha)
                    desfeitas += 1
            if not novas and not desfeitas:
                return
            gravou = aceites.salvar()
            self._remontar()
            partes = []
            if novas:
                partes.append("{} sugestão(ões) aceita(s)".format(novas))
            if desfeitas:
                partes.append("{} desfeita(s)".format(desfeitas))
            self.janela.status("{}.{}".format(
                ", ".join(partes).capitalize(),
                "" if gravou else " Não foi possível gravar para os "
                "próximos meses: {}".format(aceites.caminho)))

        RevisarSugestoes(self.corpo, itens, salvar)

    def _confirmar_pendencias(self, linhas) -> bool:
        """Pede confirmacao antes de exportar linha que o importador recusaria.

        Nao BLOQUEIA: ha caso legitimo -- exportar so para conferir, ou mandar
        o arquivo mesmo sabendo que tres linhas vao ser corrigidas a mao. Mas
        exportar 774 linhas com tres furos sem ninguem perceber e o modo mais
        facil de recolher a menos, e por isso a pergunta tem de ser feita antes
        de o arquivo existir, e nao depois.
        """
        pendentes = [l for l in linhas if l.tem_pendencia]
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
                len(pendentes), len(linhas), detalhe))

    # ------------------------------------------------------------------ #
    def ao_entrar(self) -> None:
        # O codigo de uma fonte pode ter sido cadastrado na outra tela desde a
        # ultima vez que esta apareceu -- e as regras do municipio podem ter
        # mudado na tela Municipios, ou o municipio ter sido escolhido la.
        self._recarregar_municipios()
        self._pintar_regras()
        if self.estado.folha_lida is not None:
            self.janela.aplicar_regras()
        if self.estado.tem_folha():
            self._sincronizar_fontes()
            self._remontar()
            self.janela.status("Confira a tabela e exporte.")
        elif not self.estado.municipio:
            self.janela.status("Escolha o município e anexe o PDF da folha.")
        else:
            self.janela.status("Anexe o PDF da folha de pagamento.")
        self._atualizar_trilha()
