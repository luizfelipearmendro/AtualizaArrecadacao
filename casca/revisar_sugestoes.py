# -*- coding: utf-8 -*-
"""Revisar as sugestoes de matricula do SISPREVWEB, uma a uma.

Quem nao casou por nome + admissao pode ter uma SUGESTAO -- ver
`arrecadacao.segurados_sisprev`. A sugestao nunca e aplicada sozinha: trocar a
matricula pela de outra pessoa nao da erro na importacao, credita a
contribuicao no segurado errado. Aqui quem confere ve a folha e o SISPREVWEB
lado a lado e marca o que e a mesma pessoa.

As marcadas ficam gravadas por municipio. No mes seguinte a mesma servidora
com sobrenome de casada ja entra trocada, e aparece aqui MARCADA -- para poder
ser desmarcada, se o aceite de antes estava errado.

Tudo comeca DESMARCADO. Um botao "aceitar todas" com tudo marcado por padrao
seria o caminho de menor esforco, e o de menor esforco aqui e o que credita
contribuicao em quem nao devia.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Sequence

from .componentes import Botao, Cartao, Superficie, caixa_de_marcar
from .tema import (COR_ATENCAO, COR_BORDA, COR_BORDA_CAMPO, COR_CARTAO,
                   COR_CARTAO_FRACO, COR_DICA, COR_FUNDO, COR_MUDO, COR_OK,
                   COR_TEXTO, COR_TITULO, GAP, T_LEGENDA, T_MINI, fonte)

MESMA_ADMISSAO = "mesma admissão, nome diferente"
MESMO_NOME = "mesmo nome, admissão diferente"


def _data(valor) -> str:
    if not valor:
        return "sem data"
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def motivo_da_sugestao(comparacao) -> str:
    from arrecadacao.segurados_sisprev import nome_comparavel
    if nome_comparavel(comparacao.linha.nome) == \
            nome_comparavel(comparacao.sugerido.nome):
        return MESMO_NOME
    return MESMA_ADMISSAO


class RevisarSugestoes(tk.Toplevel):
    """Modal com as sugestoes. `ao_salvar` recebe {indice: marcada}."""

    def __init__(self, pai, comparacoes: Sequence,
                 ao_salvar: Callable[[Dict[int, bool]], None]) -> None:
        super().__init__(pai)
        self.ao_salvar = ao_salvar
        # Agrupadas pelo motivo -- sao conferencias diferentes: num grupo se
        # olha o sobrenome, no outro a data --, e por nome dentro do grupo.
        self.itens = sorted(
            enumerate(comparacoes),
            key=lambda par: (motivo_da_sugestao(par[1]) != MESMA_ADMISSAO,
                             par[1].linha.nome))
        self.marcas: Dict[int, tk.BooleanVar] = {
            indice: tk.BooleanVar(value=bool(c.aceita))
            for indice, c in self.itens}
        # Para esconder linha e grupo sem refazer a lista: os widgets de cada
        # sugestao, o grupo dela e quais grupos estao abertos.
        self._widgets: Dict[int, List[tk.Widget]] = {}
        self._img_marcado = caixa_de_marcar(self, True)
        self._img_desmarcado = caixa_de_marcar(self, False)
        self._grupo: Dict[int, str] = {}
        self._aberto: Dict[str, bool] = {}
        self._setas: Dict[str, tk.Label] = {}

        self.title("Sugestões do SISPREVWEB")
        self.configure(bg=COR_FUNDO)
        self.transient(pai)
        self.minsize(760, 420)
        self._montar()
        self._contar()
        self._posicionar(pai)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()
        self.focus_set()

    # ------------------------------------------------------------------ #
    def _montar(self) -> None:
        cartao = Cartao(
            self, titulo="Sugestões do SISPREVWEB", glifo="pessoas",
            legenda="Marque só quem é a mesma pessoa. As marcadas vão com o "
                    "código do SISPREVWEB e ficam gravadas para os próximos "
                    "meses deste município.")
        cartao.pack(fill="both", expand=True, padx=GAP, pady=GAP)
        corpo = cartao.conteudo

        topo = tk.Frame(corpo, bg=COR_CARTAO)
        topo.pack(fill="x", pady=(0, 6))
        self.var_contagem = tk.StringVar()
        tk.Label(topo, textvariable=self.var_contagem, bg=COR_CARTAO,
                 fg=COR_MUDO, font=fonte(T_LEGENDA), anchor="w").pack(
            side="left")
        self.var_filtro = tk.StringVar(value="todas")
        for valor, rotulo in (("nao", "Não marcadas"), ("sim", "Marcadas"),
                              ("todas", "Todas")):
            ttk.Radiobutton(topo, text=rotulo, value=valor,
                            variable=self.var_filtro,
                            command=self._reaplicar).pack(side="right",
                                                          padx=(8, 0))
        tk.Label(topo, text="Mostrar:", bg=COR_CARTAO, fg=COR_MUDO,
                 font=fonte(T_LEGENDA)).pack(side="right")

        caixa = Superficie(corpo, cor_fora=COR_CARTAO,
                           contorno=COR_BORDA_CAMPO, raio=10, padding=(4, 4))
        caixa.pack(fill="both", expand=True)
        self.tela = tk.Canvas(caixa.corpo, height=380, width=820,
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
        # Depois do evento, e nao dentro: ver `TelaFolha._alinhar_lista_fontes`.
        self.tela.bind("<Configure>", lambda _e: self.after_idle(
            self._alinhar), add="+")
        self.bind("<MouseWheel>", self._rolar)

        self.lista.columnconfigure(1, weight=1, uniform="lado")
        self.lista.columnconfigure(3, weight=1, uniform="lado")
        linha = 0
        grupo = None
        for indice, comparacao in self.itens:
            motivo = motivo_da_sugestao(comparacao)
            if motivo != grupo:
                grupo = motivo
                linha = self._titulo_do_grupo(linha, motivo)
            linha = self._linha(linha, indice, comparacao, motivo)

        botoes = tk.Frame(corpo, bg=COR_CARTAO)
        botoes.pack(fill="x", pady=(12, 0))
        Botao(botoes, text="MARCAR TODAS", altura=30,
              command=lambda: self._marcar_todas(True)).pack(side="left")
        Botao(botoes, text="DESMARCAR TODAS", altura=30,
              command=lambda: self._marcar_todas(False)).pack(side="left",
                                                              padx=8)
        Botao(botoes, text="SALVAR", primario=True,
              command=self._salvar).pack(side="right")
        Botao(botoes, text="CANCELAR",
              command=self.destroy).pack(side="right", padx=8)

    def _titulo_do_grupo(self, linha: int, motivo: str) -> int:
        explicacao = {
            MESMA_ADMISSAO: "confira o sobrenome — costuma ser o de casada",
            MESMO_NOME: "confira a data — costuma ser posse × nomeação",
        }[motivo]
        quantos = sum(1 for _i, c in self.itens
                      if motivo_da_sugestao(c) == motivo)
        quadro = tk.Frame(self.lista, bg=COR_CARTAO_FRACO, cursor="hand2")
        quadro.grid(row=linha, column=0, columnspan=4, sticky="we",
                    pady=(0 if linha == 0 else 8, 2))
        # Clicar no titulo abre e fecha o grupo: sao dois tipos de conferencia
        # diferentes, e quem esta num nao precisa rolar o outro.
        self._aberto[motivo] = True
        seta = tk.Label(quadro, text="▾", bg=COR_CARTAO_FRACO, fg=COR_TITULO,
                        font=fonte(T_LEGENDA, True))
        seta.pack(side="left", padx=(8, 4), pady=4)
        self._setas[motivo] = seta
        tk.Label(quadro, text="{} ({})".format(motivo.capitalize(), quantos),
                 bg=COR_CARTAO_FRACO, fg=COR_TITULO,
                 font=fonte(T_LEGENDA, True)).pack(side="left", padx=(0, 6),
                                                   pady=4)
        tk.Label(quadro, text=explicacao, bg=COR_CARTAO_FRACO, fg=COR_DICA,
                 font=fonte(T_MINI)).pack(side="left", pady=4)
        for alvo in (quadro,) + tuple(quadro.winfo_children()):
            alvo.bind("<Button-1>", lambda _e, m=motivo: self._abrir_fechar(m))
        return linha + 1

    def _linha(self, linha: int, indice: int, comparacao, motivo: str) -> int:
        folha = comparacao.linha
        sisprev = comparacao.sugerido
        # O mesmo check da tabela da folha -- ver `caixa_de_marcar`.
        variavel = self.marcas[indice]
        marca = tk.Label(self.lista, bg=COR_CARTAO, cursor="hand2",
                         image=self._img_marcado if variavel.get()
                         else self._img_desmarcado)
        marca.bind("<Button-1>", lambda _e, i=indice: self._alternar(i))
        variavel.trace_add("write", lambda *_a, m=marca, v=variavel:
                           m.configure(image=self._img_marcado if v.get()
                                       else self._img_desmarcado))
        marca.grid(row=linha, column=0, sticky="n", padx=(6, 8), pady=(8, 0))
        widgets: List[tk.Widget] = [marca]
        self._grupo[indice] = motivo

        # O que difere vai em amarelo: e para onde o olho tem de ir.
        destaque_nome = motivo == MESMA_ADMISSAO
        lados = (
            (1, "FOLHA", folha.matricula, folha.nome, folha.admissao),
            (3, "SISPREVWEB", sisprev.codigo, sisprev.nome,
             _data(sisprev.admissao)),
        )
        for coluna, rotulo, codigo, nome, admissao in lados:
            bloco = tk.Frame(self.lista, bg=COR_CARTAO)
            bloco.grid(row=linha, column=coluna, sticky="we", pady=(4, 4))
            tk.Label(bloco, text="{}  ·  {}".format(rotulo, codigo),
                     bg=COR_CARTAO, fg=COR_DICA, font=fonte(T_MINI),
                     anchor="w").pack(anchor="w")
            # O nome COPIA, e nao marca: e para colar na busca do SISPREVWEB.
            rotulo_nome = tk.Label(
                bloco, text=nome, bg=COR_CARTAO,
                fg=COR_ATENCAO if destaque_nome else COR_TEXTO,
                font=fonte(T_LEGENDA, True), anchor="w", cursor="hand2")
            rotulo_nome.pack(anchor="w")
            rotulo_nome.bind("<Button-1>",
                             lambda _e, n=nome: self._copiar(n))
            tk.Label(bloco, text="admissão {}".format(admissao),
                     bg=COR_CARTAO,
                     fg=COR_DICA if destaque_nome else COR_ATENCAO,
                     font=fonte(T_MINI), anchor="w").pack(anchor="w")
            for alvo in (bloco,) + tuple(bloco.winfo_children()):
                if alvo is not rotulo_nome:
                    alvo.bind("<Button-1>",
                              lambda _e, i=indice: self._alternar(i))
            widgets.append(bloco)
        seta = tk.Label(self.lista, text="→", bg=COR_CARTAO, fg=COR_DICA,
                        font=fonte(T_LEGENDA))
        seta.grid(row=linha, column=2, padx=10)
        divisa = tk.Frame(self.lista, bg=COR_BORDA, height=1)
        divisa.grid(row=linha + 1, column=0, columnspan=4, sticky="we")
        self._widgets[indice] = widgets + [seta, divisa]
        return linha + 2

    # ------------------------------------------------------------------ #
    def _alternar(self, indice: int) -> None:
        marca = self.marcas[indice]
        marca.set(not marca.get())
        self._contar()

    def _marcar_todas(self, valor: bool) -> None:
        """Marca so as que estao a vista: com um grupo fechado ou um filtro,
        "marcar todas" nao alcanca o que nao se ve."""
        for indice, marca in self.marcas.items():
            if self._visivel(indice):
                marca.set(valor)
        self._contar()

    def _copiar(self, texto: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.update()
        self.var_contagem.set("Copiado: {}".format(texto))

    def _abrir_fechar(self, motivo: str) -> None:
        self._aberto[motivo] = not self._aberto[motivo]
        self._setas[motivo].configure(text="▾" if self._aberto[motivo] else "▸")
        self._reaplicar()

    def _visivel(self, indice: int) -> bool:
        if not self._aberto.get(self._grupo[indice], True):
            return False
        filtro = self.var_filtro.get()
        marcada = self.marcas[indice].get()
        return filtro == "todas" or (filtro == "sim") == marcada

    def _reaplicar(self) -> None:
        for indice, widgets in self._widgets.items():
            mostrar = self._visivel(indice)
            for widget in widgets:
                if mostrar:
                    widget.grid()
                else:
                    widget.grid_remove()
        self.tela.yview_moveto(0)
        self._contar()

    def _contar(self) -> None:
        marcadas = sum(1 for m in self.marcas.values() if m.get())
        self.var_contagem.set("{} de {} sugestão(ões) marcada(s)".format(
            marcadas, len(self.marcas)))

    def _salvar(self) -> None:
        escolhas = {indice: marca.get() for indice, marca in self.marcas.items()}
        self.destroy()
        self.ao_salvar(escolhas)

    def _alinhar(self) -> None:
        largura = self.tela.winfo_width()
        if largura > 1:
            self.tela.itemconfigure(self._janela_lista, width=largura)

    def _rolar(self, evento) -> str:
        self.tela.yview_scroll(-1 * (evento.delta // 120), "units")
        return "break"

    def _posicionar(self, pai) -> None:
        self.update_idletasks()
        topo = pai.winfo_toplevel()
        largura = max(self.winfo_reqwidth(), 880)
        altura = min(self.winfo_reqheight(), topo.winfo_height() - 40)
        x = topo.winfo_rootx() + (topo.winfo_width() - largura) // 2
        y = topo.winfo_rooty() + max(20, (topo.winfo_height() - altura) // 2)
        self.geometry("{}x{}+{}+{}".format(largura, altura, max(0, x),
                                           max(0, y)))
