# -*- coding: utf-8 -*-
"""Acento, digitos e CPF: a regra que os dois pacotes usavam em duas copias.

`conferidor` e `diario` tinham, cada um, a sua versao de "tirar o acento", "so
os digitos" e -- o que de fato importa -- da validacao do CPF pelo modulo 11.
As duas contas eram equivalentes, escritas de formas diferentes: duas copias da
mesma regra sao uma que vai divergir no dia em que alguem corrigir apenas uma
delas, e num programa que decide "este CPF confere" isso vira conclusao errada
no relatorio.

A conta passa a viver aqui. Cada pacote continua expondo os nomes que sempre
usou (`somente_digitos` de um lado, `so_digitos` do outro), porque renomear
chamada por chamada nao melhora nada e mexe em codigo que ninguem precisava
tocar.

O que NAO veio para ca, apesar do nome parecido:

* `diario.desacentuar` -- maiusculiza e PRESERVA o comprimento da string, para
  que as posicoes calculadas no texto original continuem valendo (e como o
  numero do ato e a data sao localizados perto da mencao ao servidor);
* `diario.normalizar` -- devolve tambem o mapa de posicoes;
* `conferidor.normalizar_texto` -- colapsa pontuacao em espaco, para busca por
  substring na folha.

Sao tres coisas diferentes que se parecem no nome. Unifica-las quebraria a
busca no diario.
"""

from __future__ import annotations

import re
import unicodedata

_NAO_DIGITO = re.compile(r"\D")


def sem_acento(valor: object) -> str:
    """Remove acentos e caracteres de combinacao, preservando a caixa."""
    decomposto = unicodedata.normalize("NFKD", str(valor if valor is not None else ""))
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def so_digitos(valor: object) -> str:
    """Apenas os digitos de um valor qualquer."""
    return _NAO_DIGITO.sub("", str(valor if valor is not None else ""))


def cpf_valido(valor: object) -> bool:
    """Valida os dois digitos verificadores (modulo 11).

    Aceita o valor com mascara ou sem: os digitos sao extraidos antes. Serve
    para nao confundir CPF com numero de protocolo ou de processo de 11
    digitos, que aparecem a toda hora nos atos.
    """
    digitos = so_digitos(valor)
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(digitos[i]) * (tamanho + 1 - i) for i in range(tamanho))
        resto = (soma * 10) % 11
        esperado = 0 if resto == 10 else resto
        if esperado != int(digitos[tamanho]):
            return False
    return True


def cpf_formatado(valor: object, manter_texto: bool = False) -> str:
    """A mascara XXX.XXX.XXX-XX quando da; senao, o valor como veio.

    Com menos de 11 digitos completa com zeros a esquerda: planilha em que a
    coluna de CPF foi salva como numero perde o zero inicial, e e caso comum
    nas bases recebidas.

    `manter_texto` decide o que fazer com a celula que nao tem digito nenhum --
    "SEM CPF", "-", "nao informado". Os dois lados do programa querem coisas
    diferentes, e essa diferenca e o motivo do parametro existir:

    * o relatorio da folha (Conferidor) devolve o texto como estava, porque a
      celula e a copia do que a base do orgao escreveu, e apagar isso esconde
      informacao de quem confere;
    * o relatorio do diario devolve vazio, porque ali a coluna e so o CPF do
      servidor auditado, e texto solto no meio de CPFs formatados e ruido.
    """
    digitos = so_digitos(valor)
    if not digitos:
        return str(valor or "") if manter_texto else ""
    if len(digitos) < 11:
        digitos = digitos.zfill(11)
    if len(digitos) != 11:
        return str(valor)
    return "{}.{}.{}-{}".format(digitos[:3], digitos[3:6], digitos[6:9],
                                digitos[9:])


def cpf_normalizado(valor: object) -> str:
    """Os 11 digitos do CPF (completando zeros a esquerda), ou vazio."""
    digitos = so_digitos(valor)
    if not digitos:
        return ""
    return digitos if len(digitos) > 11 else digitos.zfill(11)


def cpf_mascarado(valor: object) -> str:
    """CPF parcialmente oculto, para log e para tela de apoio."""
    digitos = so_digitos(valor)
    if len(digitos) < 9:
        return "***"
    digitos = digitos.zfill(11)
    return "***.{}.{}-**".format(digitos[3:6], digitos[6:9])
