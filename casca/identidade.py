# -*- coding: utf-8 -*-
"""Nome do aplicativo, em um lugar so.

Modulo sem dependencia nenhuma de proposito: o nome aparece no titulo da
janela, na barra lateral e no cabecalho de toda caixa de dialogo, e sem um
lugar unico renomear o programa vira caca-los um por um.

O nome da PASTA de dados nao vem daqui (veja `preferencias.NOME_PASTA`): trocar
um titulo e trocar texto na tela, mas trocar o nome da pasta muda onde as
exportacoes e o cadastro de fontes pagadoras do usuario ficam.
"""

APP_NOME = "Atualiza Arrecadação"
APP_SUB = "Folha → SISPREVWEB"

# A versao mora AQUI, e em nenhum outro lugar. Quem a le: o pe da barra
# lateral, o log de abertura e o `build_arrecadacao.ps1`, que nomeia o pacote
# com ela. Escrita a mao na tela, ela deixaria de acompanhar release nenhum --
# e quem abrisse a versao seguinte reportaria problema como se fosse da
# anterior.
APP_VERSAO = "1.4.4"

# Identificador do aplicativo para o Windows. Sem ele a barra de tarefas trata a
# janela como pertencente ao host que a criou e mostra o icone DAQUELE -- a pena
# do Tk, no nosso caso -- ainda que a janela tenha o icone certo.
APP_ID_WINDOWS = "AgendaAssessoria.AtualizaArrecadacao"

# Quem responde pelo programa. Vai para as propriedades do executavel (aba
# Detalhes do Windows), lidas pelo `build_arrecadacao.ps1`. Executavel sem
# empresa, sem descricao e sem versao e um binario anonimo: o antivirus trata
# heuristica desse jeito com mais rigor, e quem recebe o arquivo nao tem como
# saber de onde ele veio. Sem ASCII aqui -- o recurso de versao e escrito pelo
# PowerShell, e acento sobrevive mal nesse caminho.
APP_EMPRESA = "Agenda Assessoria Planejamento e Informatica Ltda"
APP_DESCRICAO = "Atualiza Arrecadacao - folha de pagamento para o layout do SISPREVWEB"


def registrar_no_windows() -> str:
    """Declara o AppUserModelID. Devolve "" ou a explicacao da falha.

    Tem de rodar ANTES de a primeira janela existir: a barra de tarefas le a
    identidade do processo ao criar o botao, e depois nao reavalia.
    """
    import sys
    if not sys.platform.startswith("win"):
        return "nao e Windows"
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_ID_WINDOWS)
        return ""
    except Exception as erro:      # API ausente em Windows antigo
        return str(erro)
