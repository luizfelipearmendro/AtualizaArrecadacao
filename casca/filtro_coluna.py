# -*- coding: utf-8 -*-
"""Painel de filtro de uma coluna: os valores que existem, com caixa de marcar.

Mostrar os valores EXISTENTES, e nao um campo de texto, e a diferenca que
importa numa auditoria: quem confere quer saber quais situacoes funcionais o
diario devolveu, nao adivinhar como elas foram escritas. A contagem ao lado de
cada valor responde "quantas linhas isso esconde" antes de esconder.

Duas coisas faceis de errar e que este modulo resolve:

* **A busca nao pode perder marca.** Digitar no campo de busca destroi
  Checkbuttons; se as marcas morressem com os widgets, filtrar as
  aposentadorias e depois buscar outra coisa apagaria a escolha. As variaveis
  vivem em `self._marcas`, por valor, e sobrevivem a reconstrucao da lista.
* **Marcar nada nao e um filtro, e uma tabela vazia.** Aplicar com tudo
  desmarcado esvaziaria a tela sem dizer por que; o painel recusa e explica.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from .componentes import (Botao, Cartao, Superficie, campo_texto, divisor,
                          moldura_de_lista, rotulo_campo)
from .ordenacao import COM_DOIS, OPERADORES, OPERADORES_DATA, SEM_TEXTO
from .tema import (COR_BORDA_CAMPO, COR_CARTAO, COR_DICA, COR_FUNDO,
                   COR_TEXTO, GAP, T_LEGENDA, T_MINI, fonte)

# Coluna como "Numero do Ato" tem um valor por linha: criar um Checkbutton para
# cada trava a janela por segundos. Acima disto a lista e cortada e a busca
# passa a ser o caminho -- com o aviso na tela, para nao parecer perda de dado.
MAX_RENDERIZADOS = 300

ALTURA_LINHA = 24        # uma linha da lista de valores
ALTURA_LISTA = 264       # teto da caixa: 11 linhas antes de rolar


class PainelFiltro(tk.Toplevel):
    """Modal com os valores distintos de uma coluna.

    `marcados` vazio significa "todos" -- e como a ausencia de filtro chega
    aqui, e tambem como ela volta em `ao_aplicar`.
    """

    def __init__(self, pai, titulo_coluna: str,
                 valores: Sequence[Tuple[str, int]],
                 marcados: Set[str],
                 ao_aplicar: Callable[[Set[str], Tuple[str, str, str]], None],
                 x: Optional[int] = None, y: Optional[int] = None,
                 condicao: Tuple[str, str, str] = ("", "", ""),
                 tipo: str = "texto") -> None:
        super().__init__(pai)
        self.ao_aplicar = ao_aplicar
        self.valores = list(valores)
        self.tipo = tipo
        self._todos = [v for v, _ in self.valores]

        ativos = set(marcados) if marcados else set(self._todos)
        self._marcas: Dict[str, tk.BooleanVar] = {
            valor: tk.BooleanVar(value=valor in ativos) for valor in self._todos
        }
        self._mostrados: List[str] = list(self._todos)
        self._condicao_inicial = tuple(condicao) + ("", "", "")[len(condicao):]

        self.title("Filtrar: {}".format(titulo_coluna))
        self.transient(pai)
        self.resizable(False, True)
        self._montar(titulo_coluna)
        self._reconstruir()
        self._posicionar(pai, x, y)

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._aplicar())
        self.grab_set()
        self.entrada.focus_set()

    # ------------------------------------------------------------------ #
    def _montar(self, titulo_coluna: str) -> None:
        """O painel na mesma linguagem das telas: um cartao sobre o cinza.

        Era um `ttk.Frame` com widgets soltos na moldura da janela, e ficava
        sendo a unica parte do programa com cara de caixa de dialogo antiga.
        """
        self.configure(bg=COR_FUNDO)
        cartao = Cartao(self, titulo="Filtrar", glifo="filtro",
                        legenda=titulo_coluna)
        cartao.pack(fill="both", expand=True, padx=GAP, pady=GAP)
        corpo = cartao.conteudo

        rotulo_campo(corpo, "Buscar valor").pack(anchor="w", pady=(0, 4))
        self.var_busca = tk.StringVar()
        caixa_busca, self.entrada = campo_texto(corpo, self.var_busca,
                                                largura=34, padding=(10, 5))
        caixa_busca.pack(fill="x")
        self.var_busca.trace_add("write", lambda *_a: self._reconstruir())

        # Quantos estao marcados: sem isto, uma lista longa esconde o proprio
        # estado -- da rolagem nao se ve se sobrou alguma marca la embaixo.
        self.var_contagem = tk.StringVar()
        ttk.Label(corpo, textvariable=self.var_contagem,
                  style="Dica.TLabel").pack(anchor="w", pady=(10, 4))

        # Canvas porque a lista precisa rolar: um Frame com dezenas de
        # Checkbuttons nao rola sozinho.
        caixa = Superficie(corpo, cor_fora=COR_CARTAO,
                           contorno=COR_BORDA_CAMPO, raio=10, padding=(4, 4))
        caixa.pack(fill="both", expand=True)
        self.tela = tk.Canvas(caixa.corpo, height=ALTURA_LISTA, width=360,
                              highlightthickness=0, bd=0, bg=COR_CARTAO)
        rolagem = ttk.Scrollbar(caixa.corpo, orient="vertical",
                                command=self.tela.yview)
        self.tela.configure(yscrollcommand=rolagem.set)
        self.tela.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")
        self.lista = tk.Frame(self.tela, bg=COR_CARTAO)
        self._janela_lista = self.tela.create_window((0, 0), window=self.lista,
                                                     anchor="nw")
        self.lista.bind("<Configure>", lambda _e: self.tela.configure(
            scrollregion=self.tela.bbox("all")))
        # A lista acompanha a largura do canvas: sem isto a contagem alinhada
        # a direita ficaria colada no valor, e nao na borda.
        self.tela.bind("<Configure>", lambda e: self.tela.itemconfigure(
            self._janela_lista, width=e.width), add="+")
        self.tela.bind("<MouseWheel>", self._rolar, add="+")
        self.lista.bind("<MouseWheel>", self._rolar, add="+")

        self.var_aviso = tk.StringVar()
        ttk.Label(corpo, textvariable=self.var_aviso, style="Aviso.TLabel",
                  wraplength=360).pack(anchor="w", pady=(8, 0))

        marcar = tk.Frame(corpo, bg=COR_CARTAO)
        marcar.pack(fill="x", pady=(10, 0))
        Botao(marcar, text="MARCAR", altura=28,
              command=lambda: self._marcar_mostrados(True)).pack(side="left")
        Botao(marcar, text="DESMARCAR", altura=28,
              command=lambda: self._marcar_mostrados(False)).pack(side="left",
                                                                  padx=8)
        Botao(marcar, text="INVERTER", altura=28,
              command=self._inverter).pack(side="left")

        self._montar_condicao(corpo)

        divisor(corpo, pady=(14, 0))
        acoes = tk.Frame(corpo, bg=COR_CARTAO)
        acoes.pack(fill="x", pady=(12, 0))
        Botao(acoes, text="APLICAR", primario=True,
              command=self._aplicar).pack(side="right")
        Botao(acoes, text="CANCELAR", command=self.destroy).pack(side="right",
                                                                 padx=8)
        Botao(acoes, text="MOSTRAR TUDO", sutil=True,
              command=self._mostrar_tudo).pack(side="left")

    def _posicionar(self, pai, x: Optional[int], y: Optional[int]) -> None:
        """Abre junto do cabecalho clicado, sem sair da tela."""
        self.update_idletasks()
        largura, altura = self.winfo_reqwidth(), self.winfo_reqheight()
        if x is None or y is None:
            x = pai.winfo_rootx() + 60
            y = pai.winfo_rooty() + 60
        x = max(0, min(int(x), self.winfo_screenwidth() - largura - 10))
        y = max(0, min(int(y), self.winfo_screenheight() - altura - 40))
        self.geometry("+{}+{}".format(x, y))

    def _rolar(self, evento) -> None:
        try:
            self.tela.yview_scroll(int(-1 * (evento.delta / 120)), "units")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ #
    def _reconstruir(self) -> None:
        """Refaz a lista conforme a busca. As marcas ficam em `_marcas`."""
        procurado = self.var_busca.get().strip().casefold()
        casam = [(v, n) for v, n in self.valores
                 if not procurado or procurado in v.casefold()]

        for filho in self.lista.winfo_children():
            filho.destroy()

        cortados = max(0, len(casam) - MAX_RENDERIZADOS)
        self._mostrados = [v for v, _ in casam[:MAX_RENDERIZADOS]]
        for valor, quantas in casam[:MAX_RENDERIZADOS]:
            self._linha_de_valor(valor, quantas)

        # A caixa acompanha o tanto de valor que existe: com tres situacoes
        # funcionais, a lista de 260 px era um retangulo vazio.
        alturas = min(ALTURA_LISTA,
                      max(ALTURA_LINHA * 3, ALTURA_LINHA * len(self._mostrados)))
        self.tela.configure(height=alturas)

        if not casam:
            self.var_aviso.set("Nenhum valor casa com o que foi buscado.")
        elif cortados:
            self.var_aviso.set(
                "Mostrando {} de {} valores. Use a busca para achar os demais "
                "-- as marcas dos nao mostrados sao preservadas.".format(
                    MAX_RENDERIZADOS, len(casam)))
        else:
            self.var_aviso.set("")
        self._contar()
        self.tela.yview_moveto(0)

    def _linha_de_valor(self, valor: str, quantas: int) -> None:
        """Uma linha da lista: marca, valor, e a contagem alinhada a direita.

        Linha montada a mao em vez de um Checkbutton com tudo no texto: assim a
        contagem sai em cinza, na borda direita, e o valor pode ocupar o resto
        -- que e o que deixa a coluna de numeros legivel.
        """
        linha = tk.Frame(self.lista, bg=COR_CARTAO)
        linha.pack(fill="x")

        marca = tk.Checkbutton(
            linha, variable=self._marcas[valor], bg=COR_CARTAO,
            activebackground=COR_CARTAO, selectcolor=COR_CARTAO,
            highlightthickness=0, bd=0, padx=0, pady=0,
            command=self._contar)
        marca.pack(side="left", padx=(4, 4))

        tk.Label(linha, text=str(quantas), bg=COR_CARTAO, fg=COR_DICA,
                 font=fonte(T_MINI)).pack(side="right", padx=(6, 8))
        rotulo = tk.Label(linha, text=valor if valor.strip() else "(vazio)",
                          bg=COR_CARTAO, fg=COR_TEXTO, font=fonte(T_LEGENDA),
                          anchor="w", cursor="hand2")
        rotulo.pack(side="left", fill="x", expand=True)

        # clicar no texto tambem marca: o alvo de 12 px da caixinha e pequeno
        def alternar(_evento=None, alvo=valor):
            self._marcas[alvo].set(not self._marcas[alvo].get())
            self._contar()

        rotulo.bind("<Button-1>", alternar)
        for widget in (linha, marca, rotulo):
            widget.bind("<MouseWheel>", self._rolar, add="+")

    def _contar(self) -> None:
        """Atualiza o "N de M marcados" acima da lista."""
        marcados = sum(1 for marca in self._marcas.values() if marca.get())
        total = len(self._todos)
        if marcados == total:
            self.var_contagem.set(
                "{} valor(es) na coluna — todos marcados".format(total))
        else:
            self.var_contagem.set(
                "{} de {} valor(es) marcados".format(marcados, total))

    def _montar_condicao(self, dono: tk.Misc) -> None:
        """A condicao de texto (ou de data), somada a lista de valores.

        Marcar valor por valor nao serve a coluna cujo texto e quase unico por
        linha -- situacao funcional, numero do ato: ali a lista tem uma entrada
        por linha, e o que o usuario quer dizer e "contem aposentadoria". Em
        coluna de data, os operadores comparam como DATA, senao 01/2026
        apareceria antes de 31/2025.
        """
        divisor(dono, pady=(14, 0))
        rotulo_campo(dono, "E também, por condição").pack(anchor="w",
                                                          pady=(12, 6))

        self._operadores = dict(OPERADORES_DATA) if self.tipo == "data" else {}
        self._operadores.update(OPERADORES)
        self._rotulos = {rotulo: chave
                         for chave, rotulo in self._operadores.items()}

        linha = ttk.Frame(dono)
        linha.pack(fill="x")
        operador, valor, valor2 = self._condicao_inicial
        self.var_operador = tk.StringVar(
            value=self._operadores.get(operador, "(sem condição)"))
        moldura = moldura_de_lista(linha)
        moldura.pack(side="left")
        combo = ttk.Combobox(
            moldura.corpo, state="readonly", width=16,
            style="Plano.TCombobox", textvariable=self.var_operador,
            values=["(sem condição)"] + list(self._operadores.values()))
        combo.pack()
        moldura.acompanhar(combo)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._pintar_condicao())
        combo.bind("<MouseWheel>", lambda e: "break")

        self.var_condicao = tk.StringVar(value=valor)
        self.caixa_condicao, entrada = campo_texto(linha, self.var_condicao,
                                                   largura=14)
        self.caixa_condicao.pack(side="left", padx=(8, 0))
        entrada.bind("<Return>", lambda _e: self._aplicar())

        self.var_condicao2 = tk.StringVar(value=valor2)
        self.rotulo_e = ttk.Label(linha, text="e")
        self.caixa_condicao2, entrada2 = campo_texto(linha, self.var_condicao2,
                                                     largura=10)
        entrada2.bind("<Return>", lambda _e: self._aplicar())

        if self.tipo == "data":
            ttk.Label(dono, text="Datas no formato dd/mm/aaaa.",
                      style="Dica.TLabel").pack(anchor="w", pady=(6, 0))
        self._pintar_condicao()

    def _pintar_condicao(self) -> None:
        """Mostra os campos que o operador escolhido realmente usa."""
        chave = self._rotulos.get(self.var_operador.get(), "")
        precisa_valor = bool(chave) and chave not in SEM_TEXTO
        precisa_dois = chave in COM_DOIS

        if precisa_valor:
            self.caixa_condicao.pack(side="left", padx=(8, 0))
        else:
            self.caixa_condicao.pack_forget()
        if precisa_dois:
            self.rotulo_e.pack(side="left", padx=(8, 0))
            self.caixa_condicao2.pack(side="left", padx=(8, 0))
        else:
            self.rotulo_e.pack_forget()
            self.caixa_condicao2.pack_forget()

    def _condicao_escolhida(self) -> Tuple[str, str, str]:
        chave = self._rotulos.get(self.var_operador.get(), "")
        if not chave:
            return ("", "", "")
        if chave in SEM_TEXTO:
            return (chave, "", "")
        return (chave, self.var_condicao.get().strip(),
                self.var_condicao2.get().strip() if chave in COM_DOIS else "")

    def _inverter(self) -> None:
        """Troca marcado por desmarcado no que a busca esta mostrando.

        E o atalho para "tudo menos estes": marcar duas situacoes e inverter
        custa dois cliques, contra marcar as outras trinta.
        """
        for valor in self._mostrados:
            marca = self._marcas[valor]
            marca.set(not marca.get())
        self._contar()

    def _marcar_mostrados(self, ligado: bool) -> None:
        """Age sobre o que a busca mostra, e nao sobre a coluna inteira.

        E o que se espera de "Marcar todos" depois de buscar por aposentadoria:
        marcar as aposentadorias, sem mexer no resto.
        """
        for valor in self._mostrados:
            self._marcas[valor].set(ligado)
        self._contar()

    def _mostrar_tudo(self) -> None:
        self.ao_aplicar(set(), ("", "", ""))
        self.destroy()

    def _aplicar(self) -> None:
        escolhidos = {v for v, marca in self._marcas.items() if marca.get()}
        condicao = self._condicao_escolhida()
        if not escolhidos:
            self.var_aviso.set(
                "Nenhum valor marcado: a tabela ficaria vazia. Marque ao menos "
                "um, ou use Mostrar tudo.")
            return
        if condicao[0] in COM_DOIS and not (condicao[1] and condicao[2]):
            self.var_aviso.set(
                "A condição \"entre\" precisa das duas datas.")
            return
        if condicao[0] and condicao[0] not in SEM_TEXTO and not condicao[1]:
            self.var_aviso.set(
                "A condição \"{}\" precisa de um valor.".format(
                    self._operadores.get(condicao[0], condicao[0])))
            return
        # Tudo marcado nao e filtro: o conjunto vazio diz "sem filtro" e deixa o
        # cabecalho limpo, em vez de anunciar filtro que nao esconde nada.
        self.ao_aplicar(
            set() if escolhidos == set(self._todos) else escolhidos, condicao)
        self.destroy()
