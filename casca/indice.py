# -*- coding: utf-8 -*-
"""Indice dos relatorios gerados pelo aplicativo.

Um arquivo JSON ao lado do executavel, com o que o proprio programa produziu.
Preferido a varrer pastas: o usuario move e renomeia arquivos, e uma varredura
tanto perderia relatorios quanto acharia planilhas que nao sao nossas.

Entradas cujo arquivo nao existe mais aparecem marcadas, nao somem -- saber que
um relatorio foi gerado e depois movido e informacao util.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List

ARQUIVO = "relatorios.json"
LIMITE = 200          # mantem o indice enxuto; os mais antigos caem fora


@dataclass
class Registro:
    """Um relatorio produzido pelo aplicativo."""

    caminho: str
    tipo: str          # "conferencia" | "auditoria" | "consolidado"
    quando: str        # dd/mm/aaaa hh:mm
    resumo: str        # uma linha: orgao, quantidades

    @property
    def existe(self) -> bool:
        return Path(self.caminho).exists()

    @property
    def nome(self) -> str:
        return Path(self.caminho).name


class Indice:
    """Lista dos relatorios, do mais recente para o mais antigo."""

    def __init__(self, pasta: Path) -> None:
        self.caminho = Path(pasta) / ARQUIVO

    def carregar(self) -> List[Registro]:
        try:
            bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        registros = []
        for item in bruto:
            try:
                registros.append(Registro(**item))
            except TypeError:
                continue          # formato antigo: ignora a entrada
        return registros

    def registrar(self, caminho: str, tipo: str, resumo: str) -> None:
        """Anota um relatorio recem-gerado no topo da lista."""
        registros = [r for r in self.carregar()
                     if Path(r.caminho) != Path(caminho)]
        registros.insert(0, Registro(
            caminho=str(caminho), tipo=tipo,
            quando=datetime.now().strftime("%d/%m/%Y %H:%M"), resumo=resumo))
        self._gravar(registros[:LIMITE])

    def remover(self, caminho: str) -> None:
        self._gravar([r for r in self.carregar()
                      if Path(r.caminho) != Path(caminho)])

    def _gravar(self, registros: List[Registro]) -> None:
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            self.caminho.write_text(
                json.dumps([asdict(r) for r in registros], indent=2,
                           ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass          # o indice e conveniencia: nunca derruba o fluxo
