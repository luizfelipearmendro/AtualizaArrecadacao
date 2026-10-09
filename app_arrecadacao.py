# -*- coding: utf-8 -*-
"""Atualiza Arrecadacao - da folha de pagamento ao layout do SISPREVWEB.

    python app_arrecadacao.py               abre a janela
    python app_arrecadacao.py --autoteste   confere a instalacao e sai
"""

import logging
import sys
import traceback
from datetime import datetime

from casca.identidade import APP_NOME, APP_VERSAO, registrar_no_windows


def _configurar_log():
    """Sem console, o log e a unica forma de diagnosticar na maquina do colega."""
    try:
        from casca.janela import pasta_do_aplicativo
        pasta = pasta_do_aplicativo() / "logs"
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / "arrecadacao_{}.log".format(
            datetime.now().strftime("%Y%m%d_%H%M%S"))
        manipulador = logging.FileHandler(arquivo, encoding="utf-8")
        manipulador.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            datefmt="%H:%M:%S"))
        raiz = logging.getLogger()
        raiz.setLevel(logging.INFO)
        raiz.handlers = [manipulador]
        return arquivo
    except Exception:
        return None


def autoteste() -> int:
    r"""Confere, no lugar onde o programa vai rodar, que ele consegue rodar.

    Roda depois do build, sobre o .exe empacotado, e escreve o resultado em
    `autoteste.log` ao lado dele -- o exe e --windowed e nao imprime nada no
    terminal que o chamou.

    O que se quer pegar aqui e a falha que so aparece no pacote: uma biblioteca
    que o PyInstaller nao levou junto. Ela nao da erro no build nem na maquina
    de quem compilou (onde tudo esta instalado), so na do colega -- e como
    caixa de dialogo, sem log.
    """
    linhas = ["{} {}".format(APP_NOME, APP_VERSAO),
              "Python {}".format(sys.version.split()[0]), ""]
    falhas = 0

    def conferir(rotulo, funcao):
        nonlocal falhas
        try:
            detalhe = funcao() or "ok"
            linhas.append("  [ok]    {}: {}".format(rotulo, detalhe))
        except Exception as erro:
            falhas += 1
            linhas.append("  [FALHA] {}: {}".format(rotulo, erro))

    def _pymupdf():
        import fitz
        return fitz.__doc__.splitlines()[0] if fitz.__doc__ else "importado"

    def _openpyxl():
        import openpyxl
        return openpyxl.__version__

    def _tk():
        import tkinter
        return "Tcl/Tk {}".format(tkinter.TkVersion)

    def _dnd():
        from casca import arrastar
        return "disponível" if arrastar.DISPONIVEL else "ausente (opcional)"

    def _motor():
        from arrecadacao import exportacao, extracao, folha, fontes, layout
        return "{} colunas no modelo completo".format(
            len(layout.ORDEM[layout.MODELO_COMPLETO]))

    def _telas():
        # Importar as telas pega o erro de import que so apareceria ao clicar
        # no item da barra lateral -- depois de o programa ja estar aberto.
        from casca import (tela_exportacoes, tela_folha, tela_fontes,
                           tela_inicio)
        return "4 telas"

    def _ida_e_volta():
        """Le um PDF de mentira? Nao -- mas confere a conta que leva ao arquivo.

        Monta uma folha em memoria, passa pelo layout e pela gravacao do CSV, e
        confere o texto gerado. E o caminho inteiro do motor sem depender de
        nenhum arquivo externo, que e o que um autoteste pode garantir.
        """
        import tempfile
        from pathlib import Path

        from arrecadacao import exportacao, layout
        from arrecadacao.folha import Competencia, Folha, Segurado, Verba
        from arrecadacao.fontes import FonteDaFolha

        segurado = Segurado(
            matricula="9999", nome="FULANO DE TAL", estrutura="1.02.001",
            fonte=FonteDaFolha(numero=1, nome="2002 -GABINETE EFETIVOS F 1.500"))
        # So a previdencia do segurado: a verba de nota "10004 - Base Patronal"
        # existe na folha, mas nao e lida -- as duas colunas de patronal saem
        # zeradas (ver `arrecadacao.layout`).
        segurado.verbas = [
            Verba("8850", "PREVIDENCIA MUNICIPAL", "D", base=4810.11,
                  valor=673.42),
        ]
        teste = Folha(arquivo="teste.pdf", tipo="Mensal",
                      competencia=Competencia(2026, 8), segurados=[segurado])

        linhas_layout = layout.montar(teste, lambda _fonte: "1001")
        if len(linhas_layout) != 1:
            raise AssertionError("esperava 1 linha, veio {}".format(
                len(linhas_layout)))
        linha = linhas_layout[0]
        if linha.base != 4810.11 or linha.segurado != 673.42:
            raise AssertionError("valores errados: {} / {}".format(
                linha.base, linha.segurado))
        if linha.tem_pendencia:
            raise AssertionError("pendência inesperada: {}".format(
                linha.pendencias))

        with tempfile.TemporaryDirectory() as pasta:
            destino = exportacao.gravar_csv(
                linhas_layout, Path(pasta) / "t.csv", layout.MODELO_COMPLETO)
            texto = destino.read_text(encoding="utf-8-sig").strip()
        esperado = "9999;FULANO DE TAL;2026;8;4810,11;673,42;0,00;0,00;1001;Efetivo"
        if texto != esperado:
            raise AssertionError("CSV inesperado:\n  {}\n  {}".format(
                texto, esperado))
        return "CSV confere"

    conferir("PyMuPDF (leitura do PDF)", _pymupdf)
    conferir("openpyxl (gravação do xlsx)", _openpyxl)
    conferir("tkinter (janela)", _tk)
    conferir("arrastar e soltar", _dnd)
    conferir("motor de arrecadação", _motor)
    conferir("telas", _telas)
    conferir("folha → layout → CSV", _ida_e_volta)

    linhas.append("")
    linhas.append("RESULTADO: {}".format(
        "tudo certo." if not falhas else "{} falha(s).".format(falhas)))
    saida = "\n".join(linhas)

    try:
        from casca.janela import pasta_do_aplicativo
        (pasta_do_aplicativo() / "autoteste.log").write_text(
            saida, encoding="utf-8")
    except Exception:
        pass

    # O console do Windows abre em cp1252, que nao tem "→" nem "ç": imprimir
    # direto derrubava o autoteste com UnicodeEncodeError -- justamente o
    # programa cuja unica funcao e dizer se esta tudo certo. O log fica em
    # UTF-8, completo; a tela recebe o que ela consegue mostrar.
    try:
        print(saida)
    except UnicodeEncodeError:
        codificacao = getattr(sys.stdout, "encoding", None) or "ascii"
        print(saida.encode(codificacao, errors="replace").decode(codificacao))
    return 1 if falhas else 0


def main() -> int:
    if "--autoteste" in sys.argv:
        return autoteste()

    arquivo_log = _configurar_log()
    # Primeira linha do log: e a pergunta que toda ajuda a distancia comeca
    # fazendo -- qual versao esta rodando na maquina de quem reportou.
    logging.getLogger("arrecadacao").info("%s %s", APP_NOME, APP_VERSAO)
    try:
        # ANTES de qualquer janela: a barra de tarefas le a identidade do
        # processo ao criar o botao e nao reavalia depois.
        falha = registrar_no_windows()
        if falha:
            logging.getLogger("arrecadacao").warning(
                "AppUserModelID nao definido: %s", falha)

        import tkinter as tk
        try:
            from tkinterdnd2 import TkinterDnD
            raiz = TkinterDnD.Tk()
        except Exception:
            raiz = tk.Tk()

        # Sem console, uma excecao em callback do Tk desaparece: o usuario clica
        # no botao e "nao acontece nada". Este gancho leva o erro para a tela.
        def erro_em_callback(tipo, valor, pilha):
            texto = "".join(traceback.format_exception(tipo, valor, pilha))
            logging.getLogger("arrecadacao").error("Erro em callback: %s", texto)
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    APP_NOME,
                    "{}: {}\n\n{}".format(tipo.__name__, valor, texto[-900:]))
            except Exception:
                print(texto, file=sys.stderr)

        raiz.report_callback_exception = erro_em_callback

        from casca.janela import Janela
        Janela(raiz)
        raiz.mainloop()
        return 0
    except Exception as exc:
        logging.getLogger("arrecadacao").exception("Falha fatal na inicializacao")
        detalhe = "{}\n\n{}".format(exc, traceback.format_exc()[-1200:])
        if arquivo_log:
            detalhe += "\n\nDetalhes em: {}".format(arquivo_log)
        try:
            import tkinter as tk
            from tkinter import messagebox
            aviso = tk.Tk()
            aviso.withdraw()
            messagebox.showerror(APP_NOME, detalhe)
            aviso.destroy()
        except Exception:
            print(detalhe, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
