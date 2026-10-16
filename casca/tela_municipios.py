# -*- coding: utf-8 -*-
"""Tela Municipios: a regra geral e o que cada municipio tem de diferente.

A esquerda, a lista dos municipios atendidos -- com "Regras gerais" no topo e
uma marca em quem tem regra propria. A direita, a ficha do escolhido.

Na ficha de um municipio cada campo comeca em "Seguir a regra geral (...)",
dizendo qual e a geral: o municipio guarda SO o que muda, e uma mudanca na
regra geral chega a todos os que a seguem. Copiar a geral para dentro de cada
ficha faria trinta copias que divergem na primeira correcao.

As listas de verbas sao a excecao: as de um municipio SOMAM-SE as da regra
geral. Excluir a CAPEMISA em Leverger nao pode desfazer a exclusao do INSS.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Dict, List, Optional

from .base_tela import Tela
from .componentes import (Botao, CaixaCampo, Cartao, acompanhar_largura,
                          campo_texto, moldura_de_lista, rotulo_campo)
from .identidade import APP_NOME
from .tema import (COR_CARTAO, COR_DICA, COR_FUNDO, COR_MUDO, COR_OK,
                   COR_PRIMARIA, COR_SOBRE_PRIMARIA, COR_TEXTO, COR_TITULO,
                   GAP, T_BASE, T_LEGENDA, T_MINI, fonte)

GERAL = "★  Regras gerais"
LARGURA_LISTA = 300

# Os rotulos das opcoes de cada campo. O VALOR gravado e a chave.
def _opcoes_formato() -> Dict[str, str]:
    from arrecadacao import formatos
    opcoes = {"": "Reconhecer sozinho (recomendado)"}
    for nome in formatos.nomes():
        opcoes[nome] = nome
    return opcoes


def _opcoes_decimo() -> Dict[str, str]:
    from arrecadacao.regras import NOMES_DECIMO
    return dict(NOMES_DECIMO)


def _opcoes_complementar() -> Dict[str, str]:
    from arrecadacao.regras import NOMES_COMPLEMENTAR
    return dict(NOMES_COMPLEMENTAR)


def _opcoes_categoria() -> Dict[str, str]:
    from arrecadacao.folha import CATEGORIAS_ACEITAS
    return {c: c for c in CATEGORIAS_ACEITAS}


# (chave, rotulo, opcoes, explicacao)
CAMPOS = (
    ("formato", "Formato da folha", _opcoes_formato,
     "Qual sistema gera o PDF. Deixe o programa reconhecer — fixe só se um "
     "PDF for confundido com outro formato."),
    ("decimo_na_rescisao", "13º dentro da rescisão", _opcoes_decimo,
     "A rescisão que paga o 13º proporcional traz a previdência dele no mesmo "
     "bloco. Somar faz como a folha (a base patronal já soma); separar manda "
     "o 13º para a competência 13."),
    ("complementar", "Arquivo complementar", _opcoes_complementar,
     "O município manda, além do PDF, um CSV no layout do SISPREVWEB. A base "
     "de cada servidor sai dele, conferida contra a contribuição da folha."),
    ("categoria", "Categoria (coluna 10)", _opcoes_categoria,
     "O que vai na coluna Categoria do arquivo."),
)

LISTAS = (
    ("excluir", "Descontos que NÃO são do RPPS",
     "Um por linha: o código da verba (só dígitos) ou um pedaço da descrição. "
     "Ex.: 809, CAPEMISA. Somam-se aos da regra geral."),
    ("incluir", "Descontos que SÃO do RPPS",
     "Para o fundo batizado sem \"PREV\" no nome. Mesmo jeito: código ou "
     "pedaço da descrição."),
)


class TelaMunicipios(Tela):
    chave = "municipios"
    titulo = "Municípios"
    subtitulo = ("a regra geral e o que cada município tem de diferente — "
                 "escolhido na arrecadação, ele traz as regras dele")

    def montar(self) -> None:
        self.selecionado: Optional[str] = None      # None = regras gerais
        self._sujo = False
        self._carregando = False
        self._rotulos: List[str] = []
        self._de_rotulo: Dict[str, Optional[str]] = {}

        linha = tk.Frame(self.corpo, bg=COR_FUNDO)
        linha.pack(fill="both", expand=True)
        self._montar_lista(linha)
        self._montar_ficha(linha)

    # ------------------------------------------------------------------ #
    # a lista
    # ------------------------------------------------------------------ #
    def _montar_lista(self, dono: tk.Misc) -> None:
        cartao = Cartao(dono, titulo="Municípios atendidos", glifo="pessoas",
                        legenda="● regra própria   ✓ catálogo")
        cartao.pack(side="left", fill="y", padx=(0, GAP))
        cartao.configure(width=LARGURA_LISTA)
        cartao.pack_propagate(False)

        rotulo_campo(cartao.conteudo, "Procurar").pack(anchor="w", pady=(0, 4))
        self.var_busca = tk.StringVar()
        caixa, _entrada = campo_texto(cartao.conteudo, self.var_busca)
        caixa.pack(fill="x")
        self.var_busca.trace_add("write", lambda *_a: self._pintar_lista())

        moldura = CaixaCampo(cartao.conteudo, padding=(2, 2))
        moldura.pack(fill="both", expand=True, pady=(8, 0))
        self.lista = tk.Listbox(
            moldura.corpo, activestyle="none", exportselection=False,
            relief="flat", bd=0, highlightthickness=0, bg=COR_CARTAO,
            fg=COR_TEXTO, font=fonte(T_BASE), selectbackground=COR_PRIMARIA,
            selectforeground=COR_SOBRE_PRIMARIA, height=18)
        self.lista.pack(side="left", fill="both", expand=True)
        self.lista.rola_sozinho_ = True
        barra = ttk.Scrollbar(moldura.corpo, orient="vertical",
                              command=self.lista.yview)
        barra.pack(side="right", fill="y")
        self.lista.configure(yscrollcommand=barra.set)
        self.lista.bind("<<ListboxSelect>>", lambda _e: self._ao_escolher())

        Botao(cartao.conteudo, text="ACRESCENTAR MUNICÍPIO", sutil=True,
              command=self._acrescentar).pack(anchor="w", pady=(8, 0))

    def _rotulo(self, municipio: str) -> str:
        config = self.janela.config
        regra = "●" if config.configurado(municipio) else "  "
        catalogo = "✓" if self.janela.cadastro.fontes_de(municipio) else "  "
        return "{} {}  {}".format(regra, catalogo, municipio)

    def _pintar_lista(self) -> None:
        from arrecadacao.municipios import sem_acento

        procurado = sem_acento(self.var_busca.get()).strip()
        self._de_rotulo = {GERAL: None}
        self._rotulos = [GERAL]
        for municipio in self.janela.config.lista_de_municipios():
            if procurado and procurado not in sem_acento(municipio):
                continue
            rotulo = self._rotulo(municipio)
            self._rotulos.append(rotulo)
            self._de_rotulo[rotulo] = municipio

        self.lista.delete(0, "end")
        for indice, rotulo in enumerate(self._rotulos):
            self.lista.insert("end", rotulo)
            if indice == 0:
                self.lista.itemconfigure(0, fg=COR_TITULO)
        alvo = next((i for i, r in enumerate(self._rotulos)
                     if self._de_rotulo[r] == self.selecionado), None)
        if alvo is not None:
            self.lista.selection_set(alvo)
            self.lista.see(alvo)

    def _ao_escolher(self) -> None:
        escolha = self.lista.curselection()
        if not escolha:
            return
        municipio = self._de_rotulo.get(self._rotulos[escolha[0]])
        if municipio == self.selecionado:
            return
        if not self._perguntar_se_salva():
            self._pintar_lista()           # volta a selecao para quem estava
            return
        self.selecionado = municipio
        self._carregar_ficha()

    def _acrescentar(self) -> None:
        nome = simpledialog.askstring(
            APP_NOME, "Nome do município, como ele deve aparecer nas listas:",
            parent=self.quadro)
        if not nome or not nome.strip():
            return
        if not self._perguntar_se_salva():
            return
        gravado = self.janela.config.acrescentar(nome)
        if not self._gravar_config():
            return
        self.selecionado = gravado
        self.var_busca.set("")
        self._pintar_lista()
        self._carregar_ficha()

    # ------------------------------------------------------------------ #
    # a ficha
    # ------------------------------------------------------------------ #
    def _montar_ficha(self, dono: tk.Misc) -> None:
        cartao = self.cartao_ficha = Cartao(dono, titulo="Regras gerais",
                                            glifo="conferir", legenda="")
        cartao.pack(side="left", fill="both", expand=True)

        self.var_info = tk.StringVar()
        tk.Label(cartao.conteudo, textvariable=self.var_info, bg=COR_CARTAO,
                 fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w",
                 justify="left").pack(fill="x", pady=(0, 6))

        grade = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        grade.pack(fill="x")
        grade.columnconfigure(1, weight=1)

        self.vars: Dict[str, tk.StringVar] = {}
        self.combos: Dict[str, ttk.Combobox] = {}
        self.dicas: Dict[str, tk.StringVar] = {}
        for linha, (chave, rotulo, _opcoes, explicacao) in enumerate(CAMPOS):
            rotulo_campo(grade, rotulo).grid(row=linha * 2, column=0,
                                             sticky="w", pady=(10, 2))
            var = self.vars[chave] = tk.StringVar()
            moldura = moldura_de_lista(grade)
            moldura.grid(row=linha * 2, column=1, sticky="w", pady=(10, 2),
                         padx=(GAP, 0))
            combo = self.combos[chave] = ttk.Combobox(
                moldura.corpo, state="readonly", textvariable=var, width=52,
                style="Plano.TCombobox")
            combo.pack()
            moldura.acompanhar(combo)
            combo.bind("<MouseWheel>", lambda e: "break")
            var.trace_add("write", lambda *_a: self._marcar_sujo())
            dica = self.dicas[chave] = tk.StringVar(value=explicacao)
            rotulo_dica = tk.Label(grade, textvariable=dica, bg=COR_CARTAO,
                                   fg=COR_DICA, font=fonte(T_MINI), anchor="w",
                                   justify="left", wraplength=480)
            rotulo_dica.grid(row=linha * 2 + 1, column=1, sticky="w",
                             padx=(GAP, 0))
            # a coluna dos rotulos come uns 190 pixels da largura da grade
            acompanhar_largura(rotulo_dica, folga=210)

        self.textos: Dict[str, tk.Text] = {}
        listas = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        listas.pack(fill="x", pady=(16, 0))
        for indice, (chave, rotulo, explicacao) in enumerate(LISTAS):
            coluna = tk.Frame(listas, bg=COR_CARTAO)
            coluna.grid(row=0, column=indice, sticky="nsew",
                        padx=(0, GAP if indice == 0 else 0))
            listas.columnconfigure(indice, weight=1, uniform="listas")
            rotulo_campo(coluna, rotulo).pack(anchor="w", pady=(0, 4))
            self.textos[chave] = self._caixa_de_texto(coluna, altura=4)
            rotulo_dica = tk.Label(coluna, text=explicacao, bg=COR_CARTAO,
                                   fg=COR_DICA, font=fonte(T_MINI), anchor="w",
                                   justify="left", wraplength=330)
            rotulo_dica.pack(fill="x", pady=(4, 0))
            acompanhar_largura(rotulo_dica, folga=8)

        rotulo_campo(cartao.conteudo, "Observações").pack(anchor="w",
                                                          pady=(14, 4))
        self.textos["observacoes"] = self._caixa_de_texto(cartao.conteudo,
                                                          altura=2)

        acoes = tk.Frame(cartao.conteudo, bg=COR_CARTAO)
        acoes.pack(fill="x", pady=(16, 0))
        self.btn_salvar = Botao(acoes, text="SALVAR", primario=True,
                                command=self._salvar)
        self.btn_salvar.pack(side="right")
        self.btn_descartar = Botao(acoes, text="DESCARTAR", sutil=True,
                                   command=self._carregar_ficha)
        self.btn_descartar.pack(side="right", padx=(0, 8))
        self.btn_limpar = Botao(acoes, text="VOLTAR TUDO À REGRA GERAL",
                                command=self._limpar)
        self.btn_limpar.pack(side="left")
        self.btn_usar = Botao(acoes, text="FAZER A ARRECADAÇÃO DESTE",
                              command=self._usar)
        self.btn_usar.pack(side="left", padx=(8, 0))
        self.var_sujo = tk.StringVar(value="")
        tk.Label(acoes, textvariable=self.var_sujo, bg=COR_CARTAO,
                 fg=COR_OK, font=fonte(T_LEGENDA)).pack(side="right",
                                                        padx=(0, 12))

    def _caixa_de_texto(self, dono: tk.Misc, altura: int) -> tk.Text:
        moldura = CaixaCampo(dono, padding=(8, 6))
        moldura.pack(fill="x")
        texto = tk.Text(moldura.corpo, height=altura, relief="flat", bd=0,
                        highlightthickness=0, bg=COR_CARTAO, fg=COR_TEXTO,
                        font=fonte(T_LEGENDA), insertbackground=COR_TEXTO,
                        wrap="word", undo=True)
        texto.pack(fill="x")
        texto.rola_sozinho_ = True
        moldura.acompanhar(texto)
        texto.bind("<<Modified>>", lambda _e, t=texto: self._texto_mudou(t))
        return texto

    def _texto_mudou(self, texto: tk.Text) -> None:
        if texto.edit_modified():
            texto.edit_modified(False)
            self._marcar_sujo()

    # ------------------------------------------------------------------ #
    def _carregar_ficha(self) -> None:
        """Preenche a ficha com o que esta gravado para o selecionado."""
        config = self.janela.config
        geral = config.geral
        self._carregando = True
        try:
            if self.selecionado is None:
                self._titulo_da_ficha(
                    "Regras gerais",
                    "Valem para todo município que não diga outra coisa.")
                self.var_info.set("")
                for chave, _rotulo, opcoes, _explicacao in CAMPOS:
                    valores = opcoes()
                    self.combos[chave].configure(values=list(valores.values()))
                    self.vars[chave].set(valores.get(getattr(geral, chave),
                                                     getattr(geral, chave)))
                for chave, *_resto in LISTAS:
                    self._preencher(self.textos[chave], getattr(geral, chave))
                self._preencher(self.textos["observacoes"], [geral.observacoes])
            else:
                municipio = self.selecionado
                proprias = config.proprias(municipio)
                quantas = len(proprias)
                self._titulo_da_ficha(
                    municipio,
                    "{} regra(s) própria(s); o resto vem das regras gerais."
                    .format(quantas) if quantas
                    else "Segue a regra geral em tudo.")
                fontes = len(self.janela.cadastro.fontes_de(municipio))
                self.var_info.set(
                    "Catálogo de fontes pagadoras: {}.".format(
                        "{} fontes".format(fontes) if fontes
                        else "não importado (tela Fontes pagadoras)"))
                for chave, _rotulo, opcoes, _explicacao in CAMPOS:
                    valores = opcoes()
                    herdado = "Seguir a regra geral ({})".format(
                        valores.get(getattr(geral, chave),
                                    getattr(geral, chave) or "—"))
                    self.combos[chave].configure(
                        values=[herdado] + list(valores.values()))
                    if chave in proprias:
                        self.vars[chave].set(valores.get(proprias[chave],
                                                         proprias[chave]))
                    else:
                        self.vars[chave].set(herdado)
                for chave, *_resto in LISTAS:
                    self._preencher(self.textos[chave], proprias.get(chave, []))
                self._preencher(self.textos["observacoes"],
                                [proprias.get("observacoes", "")])
        finally:
            self._carregando = False
        self._sujo = False
        self.var_sujo.set("")
        eh_municipio = self.selecionado is not None
        self.btn_limpar.configure(state="normal" if eh_municipio else "disabled")
        self.btn_usar.configure(state="normal" if eh_municipio else "disabled")
        # A ficha muda de altura com o que mostra (a legenda, as dicas): sem
        # isto a pagina nao descobre que ja nao cabe -- ver
        # `Tela.repensar_rolagem` -- e o pe da ficha, com o SALVAR, some.
        self.repensar_rolagem()

    def _titulo_da_ficha(self, titulo: str, legenda: str) -> None:
        self.cartao_ficha.rotulo_titulo.configure(text=titulo)
        legenda_rotulo = self.cartao_ficha.rotulo_legenda
        legenda_rotulo.configure(text=legenda)
        if legenda and not legenda_rotulo.winfo_manager():
            legenda_rotulo.pack(fill="x")

    @staticmethod
    def _preencher(texto: tk.Text, itens) -> None:
        texto.delete("1.0", "end")
        texto.insert("1.0", "\n".join(i for i in itens if i))
        texto.edit_modified(False)
        texto.edit_reset()

    @staticmethod
    def _linhas(texto: tk.Text) -> List[str]:
        return [l.strip() for l in texto.get("1.0", "end").splitlines()
                if l.strip()]

    def _marcar_sujo(self) -> None:
        if self._carregando:
            return
        self._sujo = True
        self.var_sujo.set("alterações não salvas")

    def _ficha_como_dados(self) -> dict:
        """O que esta na ficha, nas chaves gravadas. Herdado nao entra."""
        dados: dict = {}
        for chave, _rotulo, opcoes, _explicacao in CAMPOS:
            rotulo = self.vars[chave].get()
            de_rotulo = {v: k for k, v in opcoes().items()}
            if rotulo in de_rotulo:
                dados[chave] = de_rotulo[rotulo]
        for chave, *_resto in LISTAS:
            dados[chave] = self._linhas(self.textos[chave])
        dados["observacoes"] = self.textos["observacoes"].get(
            "1.0", "end").strip()
        return dados

    def _salvar(self) -> bool:
        from arrecadacao.regras import _regras_de_dicionario

        config = self.janela.config
        dados = self._ficha_como_dados()
        if self.selecionado is None:
            config.geral = _regras_de_dicionario(dados)
        else:
            config.definir_proprias(self.selecionado, dados)
        if not self._gravar_config():
            return False
        self._sujo = False
        self._pintar_lista()
        self._carregar_ficha()
        self.var_sujo.set("salvo")
        self._regras_mudaram()
        return True

    def _gravar_config(self) -> bool:
        try:
            self.janela.config.salvar()
        except OSError as erro:
            messagebox.showerror(
                APP_NOME, "Não foi possível gravar as regras:\n\n{}".format(erro))
            return False
        return True

    def _regras_mudaram(self) -> None:
        """A folha ja lida passa a seguir as regras novas, sem reler o PDF."""
        afeta = (self.selecionado is None
                 or self.selecionado == self.estado.municipio)
        if afeta and self.estado.folha_lida is not None:
            self.janela.aplicar_regras()
        self.janela.atualizar_barra()

    def _limpar(self) -> None:
        if self.selecionado is None:
            return
        if not messagebox.askyesno(
                APP_NOME, "Apagar as regras próprias de {}? Ele passa a seguir "
                "a regra geral em tudo.".format(self.selecionado)):
            return
        self.janela.config.definir_proprias(self.selecionado, {})
        if self._gravar_config():
            self._pintar_lista()
            self._carregar_ficha()
            self._regras_mudaram()

    def _usar(self) -> None:
        if self.selecionado is None or not self._perguntar_se_salva():
            return
        if self.estado.folha_lida is not None and \
                self.estado.municipio != self.selecionado:
            if not messagebox.askyesno(
                    APP_NOME, "Há uma folha lida de {}. Trocar a arrecadação "
                    "para {}? A folha continua lida; as regras e o catálogo "
                    "passam a ser os de {}.".format(
                        self.estado.municipio or "outro município",
                        self.selecionado, self.selecionado)):
                return
        self.estado.municipio = self.selecionado
        self.janela.aplicar_regras()
        self.janela.ir_para("folha")

    def _perguntar_se_salva(self) -> bool:
        """True se pode seguir: nada pendente, salvo, ou descartado."""
        if not self._sujo:
            return True
        resposta = messagebox.askyesnocancel(
            APP_NOME, "Salvar as alterações de {}?".format(
                self.selecionado or "Regras gerais"))
        if resposta is None:
            return False
        if resposta:
            return self._salvar()
        self._sujo = False
        return True

    # ------------------------------------------------------------------ #
    def ao_entrar(self) -> None:
        if not self._sujo:
            # Abre no municipio da arrecadacao em andamento: e quase sempre ele
            # que se veio ajustar.
            if self.estado.municipio and self.selecionado is None:
                self.selecionado = self.estado.municipio
            self._carregar_ficha()
        self._pintar_lista()
        self.janela.status("Escolha um município para ver ou mudar as regras dele.")
