# -*- coding: utf-8 -*-
"""Os municipios cuja arrecadacao esta casa faz.

A lista existe porque o catalogo de fontes pagadoras e POR MUNICIPIO: os nomes
se repetem de uma prefeitura para outra ("001 - 2002 - GABINETE EFETIVOS"
existe em varias), e os codigos de integracao nao. Importar o arquivo de um
municipio sobre o cadastro de outro casaria tudo e creditaria a arrecadacao
inteira na fonte errada -- por isso o municipio e escolhido antes, e nao
deduzido do arquivo.

Digitada, e nao lida de lugar nenhum: sao 29 e mudam de tempos em tempos, e
uma lista fechada e o que permite escolher de uma lista em vez de digitar
"ARIPUANA" hoje e "Aripuana" no mes que vem -- duas grafias, dois cadastros,
metade das fontes sumindo sem erro nenhum.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional, Tuple

MUNICIPIOS: Tuple[str, ...] = (
    "ACORIZAL",
    "ARIPUANÃ",
    "BARÃO DE MELGAÇO",
    "BARRA DO GARÇAS",
    "CAMPINAPOLIS",
    "CHAPADA DOS GUIMARÃES",
    "COCALINHO",
    "COLNIZA",
    "CONFRESA",
    "GAÚCHA DO NORTE",
    "JANGADA",
    "JAURU",
    "JUARA",
    "NOVA MARILANDIA",
    "NOVA NAZARÉ",
    "NOVA SANTA HELENA",
    "PARANATINGA",
    "PRIMAVERA DO LESTE",
    "RESERVA DO CABAÇAL",
    "ROSARIO OESTE",
    "SANTA TEREZINHA",
    "SANTO AFONSO",
    "SANTO ANTÔNIO DO LESTE",
    "SANTO ANTÔNIO DO LEVERGER",
    "SÃO FÉLIX DO ARAGUAIA",
    "SÃO JOSÉ DO POVO",
    "TABAPORÃ",
    "TERRA NOVA DO NORTE",
    "TORIXORÉU",
    "VALE DE SÃO DOMINGOS",
    "VILA BELA",
)


def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in decomposto if not unicodedata.combining(c)).upper()


def reconhecer(entidade: str) -> Optional[str]:
    """Adivinha o municipio pelo cabecalho da folha. None se nao reconhecer.

    Cada sistema de folha escreve o cabecalho do seu jeito, e o municipio esta
    sempre no meio de alguma moldura:

        "1 - DE ARIPUANA-MT"                       (Agili)
        "PREFEITURA MUNICIPAL DE ROSARIO OESTE MT" (ARFolha)

    O que esta funcao faz e descascar a moldura -- a numeracao da frente, o
    "PREFEITURA MUNICIPAL", o "DE", a sigla do estado no fim -- e comparar o
    que sobra com a lista. Serve para a tela ja vir com o municipio certo
    escolhido, que continua editavel: adivinhar o municipio errado e o comeco
    de creditar na fonte errada.
    """
    alvo = sem_acento(entidade)
    alvo = re.sub(r"^\s*\d+\s*-\s*", "", alvo)      # "1 - DE ARIPUANA-MT"
    # A moldura vem na frente ou atras, conforme o gerador: "PREFEITURA
    # MUNICIPAL DE ROSARIO OESTE MT" poe na frente e "SAO JOSE DO POVO CAMARA
    # MUNICIPAL" poe atras. Tirar so a da frente deixava o municipio sem
    # reconhecer, e a tela abria no municipio errado -- que e o comeco de
    # casar as fontes contra o catalogo da cidade errada.
    # "MUNICIPAL" e opcional: Primavera escreve so "PREFEITURA DE PRIMAVERA
    # DO LESTE".
    moldura = r"(?:PREFEITURA|CAMARA)(?:\s+MUNICIPAL)?"
    alvo = re.sub(r"^\s*" + moldura + r"\s*", "", alvo)
    alvo = re.sub(r"\s*" + moldura + r"\s*$", "", alvo)
    alvo = re.sub(r"^\s*DE\s+", "", alvo)
    alvo = re.sub(r"\s*-?\s*[A-Z]{2}\s*$", "", alvo)  # "-MT" ou " MT" do fim
    alvo = " ".join(alvo.split())
    if not alvo:
        return None

    for municipio in MUNICIPIOS:
        if sem_acento(municipio) == alvo:
            return municipio
    # "VILA BELA DA SANTISSIMA TRINDADE" para "VILA BELA", e o contrario
    for municipio in MUNICIPIOS:
        limpo = sem_acento(municipio)
        if alvo.startswith(limpo) or limpo.startswith(alvo):
            return municipio
    return None
