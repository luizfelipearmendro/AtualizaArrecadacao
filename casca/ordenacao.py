# -*- coding: utf-8 -*-
"""Ordenacao e filtro por coluna nas tabelas.

Reordena movendo as linhas de lugar (`move`) e filtra escondendo-as (`detach`),
sem recria-las nunca. As telas identificam a linha selecionada pelo iid, que e o
indice na lista de origem: recriar as linhas renumeraria os iids e a selecao
passaria a apontar para outro registro. `detach` preserva o item e os valores,
so o tira da vista -- e por isso o filtro pode ser desfeito sem consultar nada
de novo.

A ordem e o filtro sao do usuario, nao da tabela: `reaplicar()` devolve a ordem
depois de repovoar a lista, para que um novo resultado nao volte a ordem de
origem sem ele pedir. O filtro, ao contrario, e descartado quando a tabela
troca de conteudo -- filtro herdado de outra auditoria esconderia linhas por
valores que talvez nem existam no resultado novo, e a tela apareceria vazia sem
explicacao.

Uma classe so cuida das duas coisas porque as duas escrevem no MESMO lugar: o
texto do cabecalho. Separadas, cada uma apagaria a marca da outra.
"""

from __future__ import annotations

import tkinter as tk

from .tema import estilizar_menu
import unicodedata
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

SETA_CRESCENTE = "  ▲"
SETA_DECRESCENTE = "  ▼"
MARCA_MENU = "  ▾"          # ha menu no botao direito
MARCA_FILTRO = "≡ "         # esta coluna esconde linhas


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def chave_texto(valor) -> str:
    """Nomes ordenam ignorando acento e caixa: Alvaro antes de Alzira."""
    return _sem_acento(str(valor or "").strip()).casefold()


def chave_data(valor) -> datetime:
    """dd/mm/aaaa, com hora opcional.

    A hora entra na comparacao quando existe: sem ela, dois relatorios gerados
    no mesmo dia empatariam. O que nao tem data ("-") vai para o inicio da
    ordem crescente.
    """
    texto = str(valor or "").strip()
    for formato, tamanho in (("%d/%m/%Y %H:%M", 16), ("%d/%m/%Y", 10)):
        try:
            return datetime.strptime(texto[:tamanho], formato)
        except ValueError:
            continue
    return datetime.min


CHAVES: Dict[str, Callable[[object], object]] = {
    "texto": chave_texto,
    "data": chave_data,
}

# Rotulos do menu: "A -> Z" nao diz nada sobre data.
ROTULOS_ORDEM = {
    "texto": ("Ordenar de A a Z", "Ordenar de Z a A"),
    "data": ("Ordenar da mais antiga", "Ordenar da mais recente"),
}

# Condicoes de filtro, alem da lista de valores. Existem porque marcar valor
# por valor nao serve a coluna cujo texto e quase unico por linha -- situacao
# funcional, numero do ato, trecho: ali a lista tem uma entrada por linha, e o
# que o usuario quer dizer e "contem aposentadoria".
OPERADORES: Dict[str, str] = {
    "contem": "contém",
    "nao_contem": "não contém",
    "comeca": "começa com",
    "termina": "termina com",
    "igual": "é igual a",
    "vazio": "está vazio",
    "nao_vazio": "não está vazio",
}

# Em coluna de data, comparar texto poe 01/2026 antes de 31/2025.
OPERADORES_DATA: Dict[str, str] = {
    "desde": "a partir de",
    "ate": "até",
    "entre": "entre",
}

SEM_TEXTO = ("vazio", "nao_vazio")       # operadores que nao pedem valor
COM_DOIS = ("entre",)                    # operadores que pedem dois valores


class Ordenador:
    """Liga o cabecalho a ordenacao e, se `filtravel`, ao filtro por valor.

    `tipos` diz como comparar cada coluna ("texto", o padrao, ou "data"); as
    colunas ausentes do dicionario ordenam como texto.

    `filtravel` nao muda o clique esquerdo: ele continua ordenando em um toque.
    O menu -- ordenar nas duas direcoes, filtrar, limpar -- vem no botao
    direito, e o cabecalho ganha um ▾ para dizer que existe.

    `ao_mudar` e chamado depois de qualquer ordenacao ou filtro, para a tela
    atualizar o que mostra sobre o estado (quantas linhas, quais filtros).
    """

    def __init__(self, tabela, titulos: Dict[str, str],
                 tipos: Optional[Dict[str, str]] = None,
                 filtravel: bool = False,
                 ao_mudar: Optional[Callable[[], None]] = None) -> None:
        self.tabela = tabela
        self.titulos = dict(titulos)
        self.tipos = dict(tipos or {})
        self.filtravel = filtravel
        self.ao_mudar = ao_mudar
        self.coluna = ""
        self.decrescente = False
        self.filtros: Dict[str, Set[str]] = {}
        # (operador, valor, valor2) por coluna -- o filtro por condicao
        self.condicoes: Dict[str, Tuple[str, str, str]] = {}
        # busca que vale para TODAS as colunas de uma vez
        self.busca = ""
        # Ordem de origem de TODAS as linhas, escondidas inclusive: e a ela que
        # o filtro devolve as linhas quando e desfeito.
        self._ordem: List[str] = []
        for coluna in self.titulos:
            # `anchor` no cabecalho, e nao no estilo: o Treeview guarda o
            # alinhamento por coluna, e o do estilo nao chega a ele.
            tabela.heading(coluna, text=self.titulos[coluna], anchor="w",
                           command=lambda c=coluna: self.ordenar(c))
        self._pintar_cabecalhos()

    # ------------------------------------------------------------------ #
    # ordenacao
    # ------------------------------------------------------------------ #
    def ordenar(self, coluna: str, decrescente: Optional[bool] = None) -> None:
        """Sem `decrescente`, o clique repetido no mesmo cabecalho inverte."""
        if decrescente is None:
            decrescente = self.coluna == coluna and not self.decrescente
        self.decrescente = decrescente
        self.coluna = coluna
        self._aplicar()
        self._pintar_cabecalhos()
        self._avisar()

    def reaplicar(self) -> None:
        """Depois de repovoar a tabela: registra a ordem de origem e reordena.

        O filtro cai aqui de proposito -- ver o modulo.
        """
        self.filtros.clear()
        self.condicoes.clear()
        self.busca = ""
        self._ordem = list(self.tabela.get_children(""))
        if self.coluna:
            self._aplicar()
        self._pintar_cabecalhos()
        self._avisar()

    def esvaziar(self) -> None:
        """Apaga a tabela INTEIRA, escondidas inclusive.

        `delete(*get_children(""))` deixaria para tras as linhas que o filtro
        escondeu: `get_children` so devolve as visiveis. Elas continuariam
        vivas, com iid ocupado, e reapareceriam no proximo filtro misturadas ao
        resultado novo.
        """
        todas = set(self._ordem) | set(self.tabela.get_children(""))
        if todas:
            self.tabela.delete(*todas)
        self._ordem = []
        self.filtros.clear()
        self.condicoes.clear()
        self.busca = ""
        self._pintar_cabecalhos()
        self._avisar()

    def limpar(self) -> None:
        """Volta a ordem de origem e apaga as setas."""
        self.coluna, self.decrescente = "", False
        self._pintar_cabecalhos()
        self._avisar()

    # ------------------------------------------------------------------ #
    # filtro
    # ------------------------------------------------------------------ #
    def menu(self, evento) -> bool:
        """Menu do cabecalho. False quando o clique nao foi num cabecalho."""
        if not self.filtravel:
            return False
        if self.tabela.identify_region(evento.x, evento.y) != "heading":
            return False
        coluna = self.coluna_em(evento.x)
        if not coluna or coluna not in self.titulos:
            return False

        crescente, decrescente = ROTULOS_ORDEM.get(
            self.tipos.get(coluna, "texto"), ROTULOS_ORDEM["texto"])
        menu = estilizar_menu(tk.Menu(self.tabela, tearoff=0))
        menu.add_command(label=crescente,
                         command=lambda: self.ordenar(coluna, False))
        menu.add_command(label=decrescente,
                         command=lambda: self.ordenar(coluna, True))
        menu.add_separator()
        menu.add_command(label="Filtrar valores...",
                         command=lambda: self.filtrar(coluna, evento.x_root,
                                                     evento.y_root))
        menu.add_command(
            label="Limpar o filtro de {}".format(self.titulos[coluna]),
            command=lambda: self.definir_filtro(coluna, set()),
            state="normal" if self.filtros.get(coluna) else "disabled")
        menu.add_command(label="Limpar todos os filtros",
                         command=self.limpar_filtros,
                         state="normal" if self.filtros else "disabled")
        try:
            menu.tk_popup(evento.x_root, evento.y_root)
        finally:
            menu.grab_release()
        return True

    def filtrar(self, coluna: str, x: Optional[int] = None,
                y: Optional[int] = None) -> None:
        from .filtro_coluna import PainelFiltro

        PainelFiltro(
            self.tabela.winfo_toplevel(), self.titulos.get(coluna, coluna),
            self.valores_de(coluna), self.filtros.get(coluna, set()),
            lambda permitidos, condicao: self.definir_filtro(
                coluna, permitidos, condicao),
            x, y, condicao=self.condicao_de(coluna),
            tipo=self.tipos.get(coluna, "texto"))

    def definir_filtro(self, coluna: str, permitidos: Set[str],
                       condicao: Optional[Tuple[str, str, str]] = None) -> None:
        """Guarda o filtro da coluna: a lista de valores e/ou a condicao.

        As duas convivem e se somam (E, nao OU): marcar "Exoneracao" em Tipo de
        Ato e pedir 'contem "a pedido"' no trecho responde a pergunta real do
        auditor, que e a combinacao das duas.
        """
        if permitidos:
            self.filtros[coluna] = set(permitidos)
        else:
            self.filtros.pop(coluna, None)

        if condicao and condicao[0]:
            self.condicoes[coluna] = condicao
        else:
            self.condicoes.pop(coluna, None)

        self._refiltrar()
        self._pintar_cabecalhos()
        self._avisar()

    def definir_busca(self, texto: str) -> None:
        """Busca rapida: esconde a linha que nao tem o texto em coluna nenhuma."""
        novo = str(texto or "").strip()
        if novo == self.busca:
            return
        self.busca = novo
        self._refiltrar()
        self._pintar_cabecalhos()
        self._avisar()

    def condicao_de(self, coluna: str) -> Tuple[str, str, str]:
        return self.condicoes.get(coluna, ("", "", ""))

    def limpar_filtros(self) -> None:
        if not self.escondendo():
            return
        self.filtros.clear()
        self.condicoes.clear()
        self.busca = ""
        self._refiltrar()
        self._pintar_cabecalhos()
        self._avisar()

    def valores_de(self, coluna: str) -> List[Tuple[str, int]]:
        """Valores distintos da coluna, com quantas linhas cada um responde.

        Conta so as linhas que passam pelos filtros das OUTRAS colunas, como faz
        uma planilha: filtrando "Aposentadoria" em Tipo de Ato, a lista de
        Orgao Publicador passa a mostrar os orgaos que publicaram
        aposentadoria. O filtro da propria coluna e ignorado, senao os valores
        que ela ja esconde desapareceriam da lista e nao haveria como remarcar.
        """
        contagem: Dict[str, int] = {}
        for iid in self._todas():
            if not self._visivel(iid, ignorar=coluna):
                continue
            valor = str(self.tabela.set(iid, coluna))
            contagem[valor] = contagem.get(valor, 0) + 1
        chave = CHAVES.get(self.tipos.get(coluna, "texto"), chave_texto)
        return sorted(contagem.items(), key=lambda par: chave(par[0]))

    def colunas_filtradas(self) -> List[str]:
        """Titulos das colunas com filtro, na ordem em que aparecem na tabela."""
        titulos = [titulo for coluna, titulo in self.titulos.items()
                   if self.filtros.get(coluna) or self.condicoes.get(coluna)]
        if self.busca:
            titulos.insert(0, 'busca "{}"'.format(self.busca))
        return titulos

    def visiveis(self) -> int:
        return len(self.tabela.get_children(""))

    def total(self) -> int:
        return len(self._todas())

    def escondendo(self) -> bool:
        return bool(self.filtros or self.condicoes or self.busca)

    def coluna_em(self, x: int) -> str:
        """Nome da coluna sob a coordenada x, ou vazio."""
        referencia = self.tabela.identify_column(x)
        if not referencia.startswith("#"):
            return ""
        try:
            indice = int(referencia[1:]) - 1
        except ValueError:
            return ""
        colunas = self._colunas_visiveis()
        return colunas[indice] if 0 <= indice < len(colunas) else ""

    # ------------------------------------------------------------------ #
    def _colunas_visiveis(self) -> List[str]:
        mostradas = self.tabela.cget("displaycolumns")
        if isinstance(mostradas, str):
            mostradas = (mostradas,) if mostradas else ()
        if mostradas and tuple(mostradas) != ("#all",):
            return [str(c) for c in mostradas]
        colunas = self.tabela.cget("columns")
        if isinstance(colunas, str):
            colunas = colunas.split()
        return [str(c) for c in (colunas or ())]

    def _todas(self) -> List[str]:
        """Todas as linhas, escondidas inclusive."""
        if self._ordem:
            return self._ordem
        return list(self.tabela.get_children(""))

    def _visivel(self, iid: str, ignorar: str = "") -> bool:
        for coluna, permitidos in self.filtros.items():
            if coluna == ignorar or not permitidos:
                continue
            if str(self.tabela.set(iid, coluna)) not in permitidos:
                return False

        for coluna, condicao in self.condicoes.items():
            if coluna == ignorar:
                continue
            if not self._passa_condicao(iid, coluna, condicao):
                return False

        if self.busca and not self._passa_busca(iid):
            return False
        return True

    def _passa_busca(self, iid: str) -> bool:
        """A busca rapida olha TODAS as colunas da linha, sem acento nem caixa."""
        procurado = chave_texto(self.busca)
        return any(procurado in chave_texto(self.tabela.set(iid, coluna))
                   for coluna in self.titulos)

    def _passa_condicao(self, iid: str, coluna: str,
                        condicao: Tuple[str, str, str]) -> bool:
        operador, alvo, alvo2 = condicao
        valor = str(self.tabela.set(iid, coluna))

        if operador in OPERADORES_DATA:
            return self._passa_data(valor, operador, alvo, alvo2)

        texto = chave_texto(valor)
        procurado = chave_texto(alvo)
        if operador == "vazio":
            return not texto or texto == "-"
        if operador == "nao_vazio":
            return bool(texto) and texto != "-"
        if not procurado:
            return True                   # condicao sem valor nao filtra nada
        if operador == "contem":
            return procurado in texto
        if operador == "nao_contem":
            return procurado not in texto
        if operador == "comeca":
            return texto.startswith(procurado)
        if operador == "termina":
            return texto.endswith(procurado)
        if operador == "igual":
            return texto == procurado
        return True

    @staticmethod
    def _passa_data(valor: str, operador: str, alvo: str, alvo2: str) -> bool:
        """Compara como data, nunca como texto.

        Linha sem data nao passa por condicao de data: "publicado a partir de
        marco" nao pode incluir o que nao tem data de publicacao -- seria
        afirmar algo que a publicacao nao diz.
        """
        data = chave_data(valor)
        if data == datetime.min:
            return False
        inicio = chave_data(alvo) if alvo else datetime.min
        fim = chave_data(alvo2) if alvo2 else datetime.max
        if operador == "desde":
            return data >= inicio
        if operador == "ate":
            return data <= (inicio if alvo else datetime.max)
        if operador == "entre":
            if alvo and alvo2 and inicio > fim:
                inicio, fim = fim, inicio      # datas trocadas de lugar
            return inicio <= data <= fim
        return True

    def _refiltrar(self) -> None:
        todas = self._todas()
        if not todas:
            return
        visiveis = [iid for iid in todas if self._visivel(iid)]
        self.tabela.detach(*todas)
        for posicao, iid in enumerate(visiveis):
            self.tabela.reattach(iid, "", posicao)

        # Linha escondida nao pode continuar selecionada: o painel de baixo
        # seguiria mostrando o trecho de uma evidencia que saiu da tela.
        mostradas = set(visiveis)
        perdidas = [iid for iid in self.tabela.selection()
                    if iid not in mostradas]
        if perdidas:
            self.tabela.selection_remove(*perdidas)
        if self.coluna:
            self._aplicar()

    def _aplicar(self) -> None:
        chave = CHAVES.get(self.tipos.get(self.coluna, "texto"), chave_texto)
        linhas = [(chave(self.tabela.set(iid, self.coluna)), iid)
                  for iid in self.tabela.get_children("")]
        # sort estavel: empates conservam a ordem em que a tabela foi montada,
        # que e a ordem de relevancia calculada pelo auditor.
        linhas.sort(key=lambda par: par[0], reverse=self.decrescente)
        for posicao, (_, iid) in enumerate(linhas):
            self.tabela.move(iid, "", posicao)

    def _pintar_cabecalhos(self) -> None:
        seta = SETA_DECRESCENTE if self.decrescente else SETA_CRESCENTE
        for coluna, titulo in self.titulos.items():
            texto = titulo
            if self.filtros.get(coluna) or self.condicoes.get(coluna):
                texto = MARCA_FILTRO + texto
            if coluna == self.coluna:
                texto += seta
            elif self.filtravel:
                texto += MARCA_MENU
            self.tabela.heading(coluna, text=texto)

    def _avisar(self) -> None:
        if self.ao_mudar is not None:
            self.ao_mudar()
