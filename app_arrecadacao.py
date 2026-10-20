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

    def _formatos():
        """Os leitores de folha chegaram no pacote?

        Um `formatos/` que o PyInstaller nao levou junto so apareceria na
        maquina do colega, como "nenhum formato reconhece este PDF" numa folha
        que aqui abre normalmente.
        """
        from arrecadacao import formatos
        if len(formatos.LEITORES) < 2:
            raise AssertionError("faltam leitores: {}".format(formatos.nomes()))
        return ", ".join(formatos.nomes())

    def _telas():
        # Importar as telas pega o erro de import que so apareceria ao clicar
        # no item da barra lateral -- depois de o programa ja estar aberto.
        from casca import (revisar_sugestoes, tela_exportacoes, tela_folha,
                           tela_fontes, tela_inicio, tela_municipios,
                           tela_resumo, tela_validacao)
        return "7 telas"

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

    def _varias_folhas_num_pdf():
        """O 13o dentro da folha mensal sai na competencia 13, e nao no mes.

        O PDF de Barra do Garcas empilha cinco folhas num arquivo so -- mensal,
        13o, rescisao, rescisao complementar e complementar. Os servidores que
        estao na mensal E no 13o sairiam com duas linhas na mesma competencia,
        que a importacao recusa. Quem garante que nao e `Segurado.tipo_folha`,
        e e uma regra facil de perder numa refatoracao do layout.
        """
        from arrecadacao import layout
        from arrecadacao.folha import Competencia, Folha, Segurado, Verba

        def quem(tipo):
            s = Segurado(matricula="9999", nome="FULANA DE TAL", tipo_folha=tipo)
            s.verbas = [Verba("8850", "PREVIDENCIA MUNICIPAL", "D",
                              base=1000.0, valor=140.0)]
            return s

        teste = Folha(arquivo="teste.pdf", tipo="Normal",
                      competencia=Competencia(2026, 7),
                      segurados=[quem("Normal"), quem("13º Salário")])
        meses = [l.mes for l in layout.montar(teste, lambda _f: "1001")]
        if meses != [7, 13]:
            raise AssertionError("esperava meses [7, 13], veio {}".format(meses))

        # ... e o relatorio que JUNTA processamentos nao e folha de 13o. O
        # Agili de Paranatinga escreve "(Rescisão, 13º salário, Mensal)" no
        # subtitulo, e ler isso como 13o mandava a mensal inteira para o mes 13.
        combinado = Folha(arquivo="teste.pdf",
                          tipo="Rescisão, 13º salário, Mensal",
                          competencia=Competencia(2026, 7))
        if combinado.competencia_de_saida() != Competencia(2026, 7):
            raise AssertionError("relatório combinado saiu como 13º")
        return "13º separado da mensal; relatório combinado no mês"

    def _nomes_da_previdencia():
        """Cada jeito de escrever a verba de previdência ainda é reconhecido.

        A verba é achada pela DESCRIÇÃO, e cada município escreve a sua: a
        câmara de São José do Povo chama de "FUNPREV". Quem não é reconhecido
        sai com base e contribuição ZERO, sem erro nenhum na tela -- o jeito
        mais fácil de recolher a menos. Por isso os nomes são conferidos aqui,
        e não só confiados a quem mexer na função um dia.
        """
        from arrecadacao.folha import Verba

        devem_entrar = ("FUNDO PREVIDENCIA", "PREVIDENCIA - FUNDO",
                        "PREVIDÊNCIA - FUNDO", "FUNPREV",
                        "PREVIDENCIA MUNICIPAL", "PREV COLNIZA",
                        "PREV COLNIZA UNICA", "PREV COLNIZA - FÉRIAS",
                        "PREVILA", "I.M.P.V.B. - INST.PREV.PÚB. MUN.",
                        "PREVICON - NORMAL", "PREVISERV",
                        "PARANATINGA PREV FERIAS", "PREVIPORÃ")
        # "PREVIDENCIA - INSS" e "I.N.S.S." são regime GERAL; a
        # "COMPLEMENTAR" é a previdência complementar (Aripuanã); os
        # consignados levam o nome do fundo e são empréstimo; "ABONO
        # PERMANENCIA" é provento; "Base Prev Outros" é rótulo de coluna.
        devem_ficar_de_fora = (("PREVIDENCIA - INSS", "D"),
                               ("I.N.S.S.", "D"),
                               ("PREVIDENCIA COMPLEMENTAR", "D"),
                               ("CONSIGNAÇÃO COMODORO-PREVI 3/96", "D"),
                               ("CONSIGNADO IMPREV 001/036", "D"),
                               ("CAPEMISA-PREV/SEG", "D"),
                               ("BB PREV CONTRIBUIÇÃO DO", "D"),
                               ("ABONO PERMANENCIA", "P"),
                               ("B. PREV OUTROS", "D"),
                               ("BASE PREVIDENCIA FERIAS", "D"))

        for nome in devem_entrar:
            if not Verba("1", nome, "D", valor=1.0).e_previdencia_do_segurado:
                raise AssertionError("deixou de reconhecer {!r}".format(nome))
        for nome, tipo in devem_ficar_de_fora:
            if Verba("1", nome, tipo, valor=1.0).e_previdencia_do_segurado:
                raise AssertionError("passou a aceitar {!r}".format(nome))
        return "{} nomes aceitos, {} recusados".format(
            len(devem_entrar), len(devem_ficar_de_fora))

    def _fonte_do_documento_inteiro():
        """A folha que nao agrupa ninguem vira UMA fonte, e nao N orfaos.

        E' o caso da camara: duas das tres que temos nao trazem grupo nenhum.
        Sem isso, os 94 servidores de Barra do Garcas chegavam na tela como
        aviso ("sem fonte pagadora") e saiam no arquivo sem codigo.
        """
        from arrecadacao.extracao import _fonte_da_folha_inteira
        from arrecadacao.folha import Folha, Segurado

        teste = Folha(arquivo="camara.pdf",
                      entidade="CÂMARA MUNICIPAL DE TAL",
                      segurados=[Segurado(matricula="1"),
                                 Segurado(matricula="2")])
        _fonte_da_folha_inteira(teste)
        if len(teste.fontes) != 1 or teste.sem_fonte:
            raise AssertionError("esperava 1 fonte e nenhum órfão: {} / {}".format(
                len(teste.fontes), len(teste.sem_fonte)))
        if not teste.fontes[0].folha_inteira:
            raise AssertionError("a fonte não ficou marcada como do documento")
        return str(teste.fontes[0])

    def _regras_do_municipio():
        """A regra do municipio muda o resultado -- e a folha lida nao muda.

        O caso e o de Aripuana: a rescisao com "8847 PREVIDENCIA S/ 13o
        SALARIO RESCISAO" ao lado da previdencia do mes. Somar da uma linha;
        separar da duas, a do 13o na competencia 13. E as listas de verbas do
        municipio SOMAM-SE as da regra geral, nao a substituem.
        """
        import dataclasses
        import tempfile

        from arrecadacao import layout, regras
        from arrecadacao.complementar import LinhaComplementar
        from arrecadacao.folha import Competencia, Folha, Segurado, Verba

        jessica = Segurado(matricula="7876", nome="FULANA", tipo_folha="")
        jessica.verbas = [
            Verba("4070", "13º SALARIO RESCISÃO", "P", valor=1472.65),
            Verba("8847", "PREVIDENCIA S/ 13º SALARIO RESCISAO", "D",
                  base=1472.65, valor=206.17),
            Verba("8850", "PREVIDENCIA MUNICIPAL", "D", base=504.91,
                  valor=70.69),
            Verba("809", "CAPEMISA-PREV/SEG", "D", base=0.0, valor=88.0),
            Verba("777", "FUNDO DO SERVIDOR", "D", base=0.0, valor=1.0)]
        lida = Folha(arquivo="r.pdf", tipo="Rescisão",
                     competencia=Competencia(2026, 8), segurados=[jessica])

        def saida(folha):
            return [(l.mes, l.base, l.segurado)
                    for l in layout.montar(folha, lambda _f: "1")]

        somada = saida(regras.aplicar(lida, regras.Regras()))
        if somada != [(8, 1977.56, 276.86)]:
            raise AssertionError("somar: {}".format(somada))
        separada = saida(regras.aplicar(
            lida, regras.Regras(decimo_na_rescisao=regras.DECIMO_SEPARAR)))
        if separada != [(8, 504.91, 70.69), (13, 1472.65, 206.17)]:
            raise AssertionError("separar: {}".format(separada))
        if len(lida.segurados) != 1 or len(jessica.verbas) != 5:
            raise AssertionError("aplicar mexeu na folha lida")
        incluida = saida(regras.aplicar(lida, regras.Regras(incluir=["777"])))
        if incluida != [(8, 1977.56, 277.86)]:
            raise AssertionError("incluir pelo código: {}".format(incluida))

        with tempfile.TemporaryDirectory() as pasta:
            config = regras.Configuracao.carregar(pasta)
            config.geral.excluir = ["INSS"]
            config.definir_proprias("ARIPUANÃ", {"excluir": ["CAPEMISA"],
                                                 "decimo_na_rescisao": "separar"})
            config.salvar()
            relida = regras.Configuracao.carregar(pasta).regras_de("ARIPUANÃ")
            if relida.excluir != ["INSS", "CAPEMISA"] or \
                    relida.decimo_na_rescisao != "separar":
                raise AssertionError("configuração relida: {}".format(relida))

        # o CSV complementar troca a base de quem tem a MESMA contribuicao, e
        # o de outra competencia nao e usado
        csv = [LinhaComplementar("7876", "FULANA", 2026, 8, 1977.60, 276.86)]
        com_csv = regras.aplicar(lida, regras.Regras(), ("c.csv", csv))
        if saida(com_csv) != [(8, 1977.60, 276.86)]:
            raise AssertionError("CSV complementar: {}".format(saida(com_csv)))
        outro_mes = [dataclasses.replace(csv[0], mes=7)]
        sem_csv = regras.aplicar(lida, regras.Regras(), ("c.csv", outro_mes))
        if saida(sem_csv) != somada:
            raise AssertionError("CSV de outro mês foi usado")
        return "13º somado e separado; verbas do município; CSV complementar"

    def _matriculas_do_sisprevweb():
        """A matricula da folha trocada pelo codigo do cadastro do SISPREVWEB.

        Os casos de Colniza: o CSV repete o segurado a cada fonte pagadora (e
        um cadastro so, nao dois), a folha escreve "DA SILVA" onde o cadastro
        escreve "SILVA", e o sobrenome de casada so vira SUGESTAO -- trocar a
        matricula por nome parecido creditaria em outra pessoa.
        """
        import tempfile
        from arrecadacao.layout import Linha
        from arrecadacao.segurados_sisprev import (DIFERENTE, ENCONTRADA,
                                                   NAO_ENCONTRADO, comparar,
                                                   ler_cadastro)

        csv = ("CODIGO_ORGAO;NOME;ANO;MES;FONTE_PAG;DATA_ADMISSAO\n"
               "265-6;ANDERSON JOSE DA SILVA AZEVEDO;2026;9;A;11/03/2022\n"
               "7545-1;FERNANDA MAURA FIRMINO;2026;9;A;16/07/2020\n"
               "7545-1;FERNANDA MAURA FIRMINO;2026;9;B;16/07/2020\n"
               "4008;RAILDA ALBUQUERQUE SILVA;2026;9;A;20/03/2008\n"
               "17231;MARIA LUCIANA ANTUNES ALVES;2026;9;A;15/02/2018\n"
               "35;RILDO SANTOS MODESTO;2026;9;A;12/03/2002\n")
        import os
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "sisprev.csv")
            with open(caminho, "w", encoding="cp1252") as arquivo:
                arquivo.write(csv)
            cadastro = ler_cadastro(caminho)

        def linha(matricula, nome, admissao):
            return Linha(matricula, nome, 2026, 9, 1.0, 1.0, 0.0, 0.0, "1",
                         "Efetivo", admissao=admissao)
        resultado = comparar([
            linha("265-6", "Anderson José da Silva Azevedo", "11/03/2022"),
            linha("7545-1", "FERNANDA MAURA FIRMINO", "16/07/2020"),
            linha("2873-3", "RAILDA ALBUQUERQUE DA SILVA", "20/03/2008"),
            linha("6435-1", "MARIA LUCIANA ANTUNES DE OLIVEIRA", "15/02/2018"),
            linha("2941-1", "RILDO SANTOS MODESTO", "13/02/2002"),
        ], cadastro)
        esperado = [ENCONTRADA, ENCONTRADA, DIFERENTE, NAO_ENCONTRADO,
                    NAO_ENCONTRADO]
        obtido = [c.situacao for c in resultado.comparacoes]
        if obtido != esperado:
            raise AssertionError("situações {} != {}".format(obtido, esperado))
        matriculas = [l.matricula for l in resultado.linhas_ajustadas()]
        if matriculas != ["265-6", "7545-1", "4008", "6435-1", "2941-1"]:
            raise AssertionError("matrículas ajustadas: {}".format(matriculas))
        if not resultado.comparacoes[3].sugestao.startswith("17231"):
            raise AssertionError("faltou sugerir o 17231")
        # Mesmo nome, outra admissao: vira sugestao, nunca troca sozinho.
        if not resultado.comparacoes[4].sugestao.startswith("35 "):
            raise AssertionError("faltou sugerir o 35 (mesmo nome)")
        # A sugestao aceita entra trocada na comparacao seguinte.
        from arrecadacao.segurados_sisprev import chave_da_linha
        aceito = comparar([c.linha for c in resultado.comparacoes], cadastro,
                          aceitas={chave_da_linha(resultado.comparacoes[3]
                                                  .linha): "17231"})
        if (aceito.comparacoes[3].situacao, aceito.comparacoes[3]
                .matricula_ajustada) != (DIFERENTE, "17231"):
            raise AssertionError("o aceite não trocou a matrícula")

        # Codigo dado a duas pessoas nao vai para ninguem; nome contido no
        # outro, com a mesma admissao, vira sugestao.
        from arrecadacao.segurados_sisprev import SeguradoSisprev
        from datetime import date
        dia = date(2019, 2, 18)
        repetido = comparar(
            [linha("7038-1", "RONALDO GARCIA CABRAL", "18/02/2019"),
             linha("62-2", "ADINA DA SILVA BONETTO", "18/02/2019")],
            [SeguradoSisprev("17834", "KAUANA KELY DA SILVA", dia, 2),
             SeguradoSisprev("17834", "RONALDO GARCIA CABRAL", dia, 3),
             SeguradoSisprev("6653", "ADINA DA SILVA", dia, 4)])
        ronaldo, adina = repetido.comparacoes
        if ronaldo.situacao != NAO_ENCONTRADO or "17834" not in repetido.repetidos:
            raise AssertionError("código repetido foi usado")
        if not adina.sugestao.startswith("6653"):
            raise AssertionError("faltou sugerir o nome contido (6653)")

        # A fonte da folha conferida contra a do cadastro: a linha com valor
        # (lancamento antigo, na fonte errada) nao conta como cadastro.
        from arrecadacao.segurados_sisprev import conferir_fontes
        dalila = linha("6463-1", "DALILA PEREIRA DE FREITAS", "18/02/2019")
        dalila.fonte = "150"
        conferida = comparar([dalila], [
            SeguradoSisprev("17259", "DALILA PEREIRA DE FREITAS", dia, 2,
                            fonte="061010 - FUNDEB 70 % - EFETIVOS"),
            SeguradoSisprev("17259", "DALILA PEREIRA DE FREITAS", dia, 3,
                            fonte="09 - BENEFÍCIOS TEMPORÁRIOS",
                            com_valor=True)])
        if conferir_fontes(conferida, [
                SeguradoSisprev("17259", "DALILA PEREIRA DE FREITAS", dia, 2,
                                fonte="061010 - FUNDEB 70 % - EFETIVOS"),
                SeguradoSisprev("17259", "DALILA PEREIRA DE FREITAS", dia, 3,
                                fonte="09 - BENEFÍCIOS TEMPORÁRIOS",
                                com_valor=True)],
                {"150": "090707 - GABINETE DA SECRETARIA DE ASSISTENCIA "
                        "SOCIAL"}) != 1 or not conferida.comparacoes[0] \
                .fonte_cadastro.startswith("061010"):
            raise AssertionError("divergência de fonte não apontada")
        return "{} encontrada(s), {} trocada(s), {} não encontrada(s)".format(
            *[obtido.count(s) for s in (ENCONTRADA, DIFERENTE, NAO_ENCONTRADO)])

    def _validacao_e_resumo():
        """O que entrou no SISPREVWEB contra o arquivo, e o resumo em PDF.

        O caso de Colniza 09/2026: a fonte 112 recusada inteira. E o PDF do
        resumo de verdade, porque e ele que depende de um pedaco do PyMuPDF
        (Story) que o empacotamento pode deixar para tras.
        """
        import tempfile
        from arrecadacao.layout import Linha
        from arrecadacao.relatorios import gravar_resumo_pdf
        from arrecadacao.validacao import (CONFERE, NAO_ENTROU, Lancamento,
                                           resumir_por_fonte, validar)

        def linha(matricula, nome, base, fonte):
            return Linha(matricula, nome, 2026, 9, base, round(base * 0.14, 2),
                         0.0, 0.0, fonte, "Efetivo")

        def lancado(codigo, nome, base, fonte, valor=True):
            return Lancamento(codigo, nome, 2026, 9, base if valor else 0.0,
                              round(base * 0.14, 2) if valor else 0.0,
                              0.0, 0.0, fonte)
        folha = [linha("3995", "ABIGAIR FIRMINO", 2747.73, "1267"),
                 linha("3390", "ADRIANO SILVA DELFINO", 5015.80, "112")]
        sisprev = [lancado("3995", "ABIGAIR FIRMINO", 2747.73, "06 - APOIO"),
                   lancado("3995", "ABIGAIR FIRMINO", 0, "07 - SAUDE", False),
                   lancado("3390", "ADRIANO SILVA DELFINO", 0, "05 - X", False)]
        resultado = validar(folha, sisprev)
        if [i.situacao for i in resultado.itens] != [CONFERE, NAO_ENTROU]:
            raise AssertionError("situações: {}".format(
                [i.situacao for i in resultado.itens]))
        if resultado.fontes[0].fonte_enviada != "112":
            raise AssertionError("a fonte recusada não veio primeiro")
        if len(resumir_por_fonte(sisprev)) != 1:
            raise AssertionError("o resumo contou fonte sem valor")
        with tempfile.TemporaryDirectory() as pasta:
            import os
            pdf = gravar_resumo_pdf(sisprev, os.path.join(pasta, "r.pdf"))
            if os.path.getsize(pdf) < 500:
                raise AssertionError("PDF do resumo vazio")
        # O numero sozinho nao casa mais: vira sugestao, sem codigo.
        from arrecadacao.fontes import Cadastro, Fonte, FonteDaFolha
        cadastro = Cadastro(catalogo={"TESTE": [
            Fonte(codigo="112", nome="04 - A DEFINIR"),
            Fonte(codigo="200", nome="07 - AT. HOSP. AMBULATORIAL")]})
        casou = cadastro.casar("TESTE", FonteDaFolha(
            numero=4, nome="SECRETARIA MUNICIPAL DE ADMINISTRACAO"))
        if casou.codigo or casou.sugerido is None or \
                casou.sugerido.codigo != "112" or len(casou.candidatos) != 2:
            raise AssertionError("fonte casou só pelo número: {!r}".format(
                casou.codigo))
        # A Unidade de Colniza: o catalogo tem o nome-base e as variantes de
        # ferias e rescisao; a folha acrescenta "- EFETIVOS".
        cadastro = Cadastro(catalogo={"TESTE": [
            Fonte(codigo="128", nome="040808 - DEPARTAMENTO DE ADMINISTRACAO"),
            Fonte(codigo="111",
                  nome="040808 - DEPARTAMENTO DE ADMINISTRACAO - FÉRIAS"),
            Fonte(codigo="168", nome="122121 - DEPARTAMENTO DE AGUA E ESGOTO"),
            Fonte(codigo="246",
                  nome="122121 - DEPARTAMENTO DE AGUA E ESGOTO - FÉRIAS")]})
        unidade = cadastro.casar("TESTE", FonteDaFolha(
            numero=40808, nome="DEPARTAMENTO DE ADMINISTRACAO - EFETIVOS"))
        if unidade.codigo != "128":
            raise AssertionError("unidade com complemento: {!r}".format(
                unidade.codigo))
        agua = cadastro.casar("TESTE", FonteDaFolha(
            numero=122121, nome="DEPARTAMENTO DE AGUA - EFETIVOS"))
        if agua.codigo or agua.sugerido is None or agua.sugerido.codigo != "168":
            raise AssertionError("nome diferente deveria virar sugestão")
        # A tabela de ajustes: o que falta na linha, e o arquivo final so com
        # as marcadas e a matricula escolhida.
        from arrecadacao.ajustes import (FONTE, ZERADA, chave, diagnosticar,
                                         linhas_finais)
        sem_fonte = linha("1", "SEM FONTE", 1000.0, "")
        zerada = linha("2", "ZERADA", 0.0, "112")
        normal = linha("3", "NORMAL", 1000.0, "112")
        if diagnosticar(sem_fonte)[0][0] != FONTE or \
                diagnosticar(zerada)[0][0] != ZERADA or diagnosticar(normal):
            raise AssertionError("ajustes: diagnóstico errado")
        ajustes = {chave(normal): {"matricula": "999"}}
        finais = linhas_finais([sem_fonte, zerada, normal], {}, ajustes)
        if [l.matricula for l in finais] != ["1", "999"]:
            raise AssertionError("arquivo final: {}".format(
                [l.matricula for l in finais]))
        return ("fonte 112 recusada achada; PDF do resumo gerado; número "
                "sozinho vira sugestão; unidade com complemento casa; "
                "tabela de ajustes")

    conferir("PyMuPDF (leitura do PDF)", _pymupdf)
    conferir("openpyxl (gravação do xlsx)", _openpyxl)
    conferir("tkinter (janela)", _tk)
    conferir("arrastar e soltar", _dnd)
    conferir("motor de arrecadação", _motor)
    conferir("formatos de folha", _formatos)
    conferir("telas", _telas)
    conferir("folha → layout → CSV", _ida_e_volta)
    conferir("várias folhas num PDF", _varias_folhas_num_pdf)
    conferir("nomes da verba de previdência", _nomes_da_previdencia)
    conferir("folha sem fonte pagadora", _fonte_do_documento_inteiro)
    conferir("regras do município", _regras_do_municipio)
    conferir("matrículas do SISPREVWEB", _matriculas_do_sisprevweb)
    conferir("validação e resumo", _validacao_e_resumo)

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
