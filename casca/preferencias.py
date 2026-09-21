# -*- coding: utf-8 -*-
r"""Preferencias do usuario, e a pasta onde o programa guarda o que e dele.

Preferencias, indice de relatorios e cache ficam em %LOCALAPPDATA%\AtualizaArrecadacao,
e nao ao lado do executavel: a pasta do programa e substituida inteira a cada
versao nova, e o que fica ali se perde em toda atualizacao -- foi o que
acontecia com o historico de relatorios.

O padrao e "Documentos\AtualizaArrecadacao". Documentos e resolvida pelo proprio Windows,
nao por concatenacao de nome: com OneDrive corporativo a pasta real fica em
"OneDrive - <empresa>\Documentos", enquanto "~/Documents" costuma existir como
sobra de perfil antigo -- gravar la e gravar onde o usuario nunca olha.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)

ARQUIVO = "preferencias.json"
NOME_PASTA = "AtualizaArrecadacao"


# ---------------------------------------------------------------------- #
# pastas do Windows
# ---------------------------------------------------------------------- #
def _documentos_pelo_windows() -> Optional[Path]:
    """FOLDERID_Documents: e o unico caminho que respeita o redirecionamento."""
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", ctypes.c_uint32),
                        ("Data2", ctypes.c_uint16),
                        ("Data3", ctypes.c_uint16),
                        ("Data4", ctypes.c_ubyte * 8)]

        documentos = GUID(0xFDD39AD0, 0x238F, 0x46AF,
                          (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85,
                                               0x48, 0x03, 0x69, 0xC7))
        destino = ctypes.c_wchar_p()
        codigo = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(documentos), 0, None, ctypes.byref(destino))
        if codigo != 0 or not destino.value:
            return None
        try:
            return Path(destino.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(destino)
    except Exception:
        return None


def _documentos_pelo_registro() -> Optional[Path]:
    """Plano B: a mesma informacao, lida do registro."""
    if not sys.platform.startswith("win"):
        return None
    try:
        import winreg
        chave = (r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                 r"\User Shell Folders")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave) as k:
            bruto, _ = winreg.QueryValueEx(k, "Personal")
        return Path(os.path.expandvars(bruto))
    except Exception:
        return None


def pasta_documentos() -> Path:
    """A pasta Documentos que o usuario ve no Explorer."""
    for tentativa in (_documentos_pelo_windows, _documentos_pelo_registro):
        caminho = tentativa()
        if caminho is not None and caminho.is_dir():
            return caminho
    # Sem os dois, "~/Documents" e palpite pior que a raiz do perfil.
    return Path.home()


def pasta_padrao() -> Path:
    return pasta_documentos() / NOME_PASTA


def pasta_de_dados() -> Path:
    """Onde ficam as preferencias, o indice de relatorios e o cache."""
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) / NOME_PASTA) if base else (Path.home() / ".atualizaarrecadacao")


ARQUIVOS_A_MIGRAR = ("relatorios.json", "fontes_pagadoras.json")


def preparar_pasta_de_dados(pasta_do_programa: Path) -> Path:
    """A pasta de dados, criada, com o que ficou na pasta do programa trazido.

    O indice de relatorios e o cache moravam ao lado do executavel, e a pasta
    do programa e substituida INTEIRA a cada versao nova -- foi por isso que as
    preferencias vieram para ca. Ficando la, o historico de relatorios
    desaparecia na atualizacao, sem ninguem perceber: a lista simplesmente
    voltava vazia.

    O indice e um arquivo de poucos KB: e movido na primeira abertura. O cache
    nao: ele passa de cem megabytes e costuma estar em outro volume (o programa
    em D:, o `%LOCALAPPDATA%` em C:), onde mover significa copiar tudo e
    atrasar a abertura. Ele fica onde esta, e a tela Relatorios passa a medir e
    limpar as duas pastas -- na primeira limpeza a antiga desaparece sozinha.
    """
    dados = pasta_de_dados()
    try:
        dados.mkdir(parents=True, exist_ok=True)
    except OSError as erro:                  # perfil sem escrita: segue na pasta antiga
        _log.warning("pasta de dados indisponivel (%s): %s", dados, erro)
        return Path(pasta_do_programa)

    for nome in ARQUIVOS_A_MIGRAR:
        antigo, novo = Path(pasta_do_programa) / nome, dados / nome
        if not antigo.is_file() or novo.exists():
            continue
        try:
            shutil.move(str(antigo), str(novo))
            _log.info("%s migrado para %s", nome, dados)
        except OSError as erro:
            _log.warning("nao foi possivel migrar %s: %s", nome, erro)
    return dados


def cache_na_pasta_do_programa(pasta_do_programa: Path) -> Optional[Path]:
    """O cache antigo, se ele ainda existir ao lado do programa."""
    antigo = Path(pasta_do_programa) / "cache"
    return antigo if antigo.is_dir() else None


def pasta_gravavel(preferida: Path) -> "tuple[Path, bool]":
    """Devolve (pasta, mudou). Testa a escrita ANTES de gerar o relatorio.

    Uma busca no diario leva dezenas de minutos: descobrir no fim que a pasta e
    somente leitura, ou que o compartilhamento de rede caiu, e perder tudo. O
    plano B e a pasta padrao, sob a Documentos que o Windows resolve -- nunca
    "~/Documents" concatenado na mao.
    """
    try:
        preferida.mkdir(parents=True, exist_ok=True)
        teste = preferida / ".atualizaarrecadacao_escrita"
        teste.write_text("x", encoding="utf-8")
        teste.unlink()
        return preferida, False
    except OSError:
        pass
    alternativa = pasta_padrao()
    try:
        alternativa.mkdir(parents=True, exist_ok=True)
        return alternativa, True
    except OSError:
        return Path.home(), True


# ---------------------------------------------------------------------- #
# preferencias
# ---------------------------------------------------------------------- #
@dataclass
class Preferencias:
    """Escolhas do usuario que sobrevivem ao fechamento do programa."""

    pasta_relatorios: Path
    ao_lado_da_origem: bool = False

    # ------------------------------------------------------------------ #
    @classmethod
    def carregar(cls) -> "Preferencias":
        """Le o arquivo. Qualquer defeito nele cai no padrao, sem reclamar."""
        alvo = pasta_de_dados() / ARQUIVO
        try:
            bruto = json.loads(alvo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls(pasta_relatorios=pasta_padrao())
        escolhida = str(bruto.get("pasta_relatorios") or "").strip()
        return cls(
            pasta_relatorios=Path(escolhida) if escolhida else pasta_padrao(),
            ao_lado_da_origem=bool(bruto.get("ao_lado_da_origem", False)),
        )

    def salvar(self) -> None:
        alvo = pasta_de_dados() / ARQUIVO
        try:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text(
                json.dumps({"pasta_relatorios": str(self.pasta_relatorios),
                            "ao_lado_da_origem": self.ao_lado_da_origem},
                           indent=2, ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass          # preferencia e conveniencia: nunca derruba o fluxo

    # ------------------------------------------------------------------ #
    def destino(self, origem: Optional[Path] = None) -> Path:
        """A pasta onde gravar, dada a pasta de onde veio o arquivo de entrada."""
        if self.ao_lado_da_origem and origem is not None:
            return Path(origem)
        return Path(self.pasta_relatorios)

    def descricao(self) -> str:
        """Uma linha para a barra de status e para a tela de relatorios."""
        if self.ao_lado_da_origem:
            return "ao lado do arquivo conferido"
        return str(self.pasta_relatorios)
