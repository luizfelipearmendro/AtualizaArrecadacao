# Atualiza Arrecadação

Lê a folha de pagamento em PDF e monta o arquivo de importação do módulo de
arrecadação do SISPREVWEB.

A equipe de arrecadação anexa o PDF da folha, confere a tabela na tela e
exporta em `.xlsx` (para conferir) ou `.csv` (para importar).

---

## Como rodar

```
python -m pip install -r requirements.txt
python app_arrecadacao.py
```

Para gerar o executável, **duplo clique em `gerar_exe.bat`** — ele instala o
PyInstaller se faltar, chama o `build_arrecadacao.ps1` e roda o autoteste
sobre o `.exe` já empacotado. O `.bat` existe porque o Windows abre `.ps1` no
Notepad em vez de executar.

```
gerar_exe.bat                  gera dist\AtualizaArrecadacao\
gerar_exe.bat -Empacotar       gera também o .zip com a versão no nome
```

Confira uma instalação com:

```
AtualizaArrecadacao.exe --autoteste
```

---

## O layout

Do documento *LAYOUT DE IMPORTAÇÃO / MÓDULO DE ARRECADAÇÃO*, modelo
**simplificado** (segurados já cadastrados). Todos os campos são obrigatórios.

| # | Campo | De onde sai |
|---|-------|-------------|
| 01 | Identificador do Segurado (Matrícula) | coluna *Matrícula* do bloco do funcionário |
| 02 | Nome | coluna *Funcionário(a)* |
| 03 | Ano | cabeçalho `FOLHA DE PAGAMENTO - 08/2026` |
| 04 | Mês | idem — **13** quando o subtítulo é `(13º salário)` |
| 05 | Remuneração de Contribuição | soma da coluna *Base* das verbas de previdência — **não** é o total de proventos; ver abaixo |
| 06 | Contribuição Previdenciária – Segurado | soma da coluna *Valor* das mesmas verbas |
| 07 | Patronal Normal | `0,00` — não é coletado da folha; ver abaixo |
| 08 | Patronal Custo Especial | `0,00` — idem |
| 09 | Identificador da Fonte Pagadora | catálogo do SISPREVWEB, casado pelo cabeçalho de fonte da folha |
| 10 | Categoria | `Efetivo` |

O modelo **reduzido**, de 8 campos, é o mesmo sem as colunas 07 e 08 (a fonte
pagadora e a categoria passam a ser 07 e 08). A escolha é feita na tela, antes
de exportar.

### Os dois patronais vão zerados

Por decisão de quem recolhe: o arquivo leva o que o **segurado** contribuiu, e
a parte do empregador é apurada fora daqui. As colunas continuam no arquivo,
com `0,00` — o campo é obrigatório e o importador conta posição, então tirá-las
faria a fonte pagadora cair na coluna do patronal.

A folha até traz a verba de nota `10004 - Base Patronal para RPPS`, e o
programa já a somou na coluna 07. Voltar a ler dali é trocar a constante
`PATRONAL_NORMAL` em `arrecadacao/layout.py` por `segurado.patronal_normal` —
o código que fazia isso está no histórico do git. Custo especial nunca existiu
nesta folha: é um aporte de plano de amortização.

### Remuneração de contribuição ≠ total de proventos

O rodapé da folha mensal fecha em **R$ 4.767.480,36** de proventos; a tela
mostra **4.126.327,68** de remuneração de contribuição. A diferença de
**641.152,68** (13,4%) não é erro de leitura — a soma dos proventos lidos bate
com o rodapé, centavo a centavo. São coisas diferentes: proventos é tudo o que
foi pago; remuneração de contribuição é só o que a folha usou como base do
desconto previdenciário, e é isso que a coluna 05 pede.

Nesta folha a diferença se decompõe em:

* **518.032,66, em 341 servidores** — verbas pagas fora da base: aulas
  excedentes, horas extras, 1/3 de férias, adicional de insalubridade,
  periculosidade, gratificações, abono de permanência;
* **123.120,02, em 50 servidores** — a base é menor que o que a pessoa recebeu.
  A maior parte é quem tem cargo efetivo e exerce comissionado (a folha marca
  *"Cargo efetivo ao exercer cargo comissionado"*): um deles recebeu 7.713,92
  e contribuiu sobre 2.664,81, que é o vencimento do efetivo. O resto
  são faltas descontadas, que reduzem a base, e férias com base repartida entre
  `8850` e `8857`.

Conferir é direto: em cada bloco do PDF a verba de previdência traz a própria
base na coluna *Base*, e a verba de nota `10004 - Base Patronal para RPPS`
repete a mesma soma. Se a tela batesse com o total de proventos, é que estaria
errada — recolheria sobre verba que não é de contribuição.

Por isso os dois números ficam **lado a lado na tela**, com a conta escrita
abaixo (`proventos − o que não compõe a base = remuneração de contribuição`) e
a explicação no balão do cartão. O total de proventos não vai no arquivo: é
conferência, e sai também na aba *Resumo* do XLSX.

### Categoria

Sempre `Efetivo`. A folha tem duas colunas que *parecem* responder isso —
*Situação* (Ativo, Exonerado) e *Forma de ingresso* — mas nenhuma delas é a
categoria: a primeira é a situação funcional e a segunda é como a pessoa
entrou. O seletor na tela aceita os outros valores do layout, para o caso de
outra prefeitura.

### Fonte pagadora

É o único campo do layout que a folha não traz pronto, e o mais perigoso de
errar: um código de fonte errado **não** rejeita a importação — ele credita a
contribuição na fonte errada, e isso só aparece meses depois, na conciliação.

**O que a folha traz.** A folha agrupa os servidores por fonte e escreve o
grupo como cabeçalho, logo abaixo da estrutura ADM:

```
1.02.001 - GABINETE DO EXECUTIVO
2 - 1 - 2002 -GABINETE EFETIVOS F 1.500        <- a fonte
Funcionário(a)  Matrícula  Situação  ...
```

Três campos: a ordem do grupo na folha (`2`), o **número** da fonte (`1`) e o
nome (`2002 -GABINETE EFETIVOS F 1.500`). No SISPREVWEB a mesma fonte se chama
`001 - 2002 -GABINETE EFETIVOS F 1.500` e tem código `5085`.

Isso é mais fino que a estrutura ADM: a folha mensal de 08/2026 tem **22
estruturas e 59 fontes**. Sair por estrutura agrupa fontes diferentes sob o
mesmo código.

**O catálogo.** O SISPREVWEB exporta o cadastro com seis colunas; destas o
programa usa `FONTE_PAG_ID` e `NOME`, achadas **pelo nome na primeira linha** e
não pela posição — `ORGAO_ID`, `CODIGO_CLIENTE`, `AFASTADOS` e
`FONTE_PAG_INATIVO` são ignoradas, e a ordem não importa. O arquivo entra como
sai do SISPREVWEB, sem ninguém abrir o Excel para apagar coluna. Casar por
posição seria mais curto e importaria `ORGAO_ID` como código de integração na
primeira vez que a exportação mudasse de forma.

O arquivo (`.csv` ou `.xlsx`) é importado na tela *Fontes pagadoras*,
**por município** — são 29 prefeituras e os nomes das fontes se repetem entre
elas, então importar o arquivo de uma sobre o cadastro de outra casaria tudo
sem erro nenhum. O município vem escolhido pelo cabeçalho da folha
(`1 - DE ARIPUANÃ-MT`) e é corrigível na tela.

**Como casa**, em `arrecadacao/fontes.py`, contra o catálogo real de Aripuanã
(1.215 fontes) e a folha mensal (59):

| Regra | Fontes |
|-------|--------|
| número igual e nome igual (sem acento, sem pontuação, sem caixa) | 50 |
| número igual e nome do catálogo **começando** pelo da folha — o PDF corta nome longo na largura da coluna | 1 |
| número igual, candidato único, nome diferente — casa, mas a tela avisa | 0 |
| **não casa sozinho** | 8 |

Os 8 que sobram não são falha do casamento; são coisas que o arquivo não
responde:

* **mais de uma fonte com o mesmo número** (3). O catálogo tem
  `351 - 2061 - SAUDE - SAUDE BUCAL` duas vezes, códigos 5144 e 5048, e ainda
  as variantes `- FÉRIAS` e `- AUX. DOENÇA`. A tela mostra os candidatos numa
  lista e quem sabe escolhe;
* **número que não existe no catálogo** (5). Fonte nova, ainda não exportada —
  aí é campo de digitar.

As duas escolhas ficam gravadas por município e são reaproveitadas na folha
seguinte. Tudo mora em
`%LOCALAPPDATA%\AtualizaArrecadacao\catalogo_fontes.json`, e não ao lado do
executável: a pasta do programa é substituída a cada versão.

A tela da folha mostra o que sobrou, com o motivo em cada linha, e sai da tela
quando a última é resolvida. A aba *Resumo* do XLSX registra o município e
quantas linhas vieram de cada regra, e o município entra no nome sugerido do
arquivo — `Arrecadacao_Aripuana_2026-08_Mensal.csv` —, porque a mesma
competência sai para 29 prefeituras e ordenar a pasta por nome tem de agrupar
por cidade.

---

## Como o PDF é lido

O PDF da folha não tem tabela — tem texto posicionado. Pedir
`pagina.get_text()` devolve as palavras na ordem interna do arquivo, que
intercala o bloco dos rótulos com o bloco dos valores; ler assim é adivinhar.

`arrecadacao/leitor_pdf.py` remonta a página pelas **coordenadas**: palavras
com o mesmo topo formam uma linha, um vão grande separa uma célula da outra, e
cada célula vai para a coluna do cabeçalho mais próxima.

Duas medidas foram calibradas contra a folha real e estão comentadas no código:

* **o vão entre células é 8 pontos** — entre palavras de um mesmo nome ele é
  1,9; o menor vão *entre colunas* é o de 10,8 que separa a data de admissão do
  CPF. Com 12, data e CPF viravam uma célula só e o CPF saía vazio nos 774
  registros, sem erro nenhum aparecer;
* **texto centraliza, dinheiro alinha à direita** — matrícula, situação,
  estrutura, data, CPF e PIS batem centro com centro; já `4.810,11` e
  `17.055,84` começam em pontos diferentes e terminam no mesmo. Casar número
  pela borda esquerda erra por uma coluna inteira, e o erro é silencioso: o
  valor do desconto entra como base de cálculo.

As colunas são lidas do cabeçalho de **cada bloco**, e não fixadas em
constantes — é o que permite abrir uma folha de outro layout sem reescrever o
extrator.

---

## Estrutura

```
app_arrecadacao.py        ponto de entrada e autoteste
arrecadacao/              o motor, sem nenhuma dependência de interface
  leitor_pdf.py             palavras -> linhas -> colunas
  extracao.py               linhas -> segurados (percorre os blocos)
  folha.py                  modelos: Folha, Segurado, Verba, Competência
  layout.py                 segurados -> colunas do layout, e as pendências
  fontes.py                 catálogo do SISPREVWEB e o casamento com a folha
  municipios.py             os 29 municípios, e qual deles a folha é
  exportacao.py             gravação do .xlsx e do .csv, e o nome sugerido
casca/                    a janela — mesma casca do AutoArial
  tela_folha.py             a tela principal: anexar, conferir, exportar
  tela_fontes.py            importação do catálogo, por município
  tela_exportacoes.py       histórico e pasta de destino
```

O motor não importa nada da casca: o mesmo código serve à janela e a um
script.

---

## Verificado contra

As três folhas de `arquivos_base/` (competência 08/2026, Aripuanã-MT):

| Folha | Páginas | Segurados | Base | Contribuição |
|-------|---------|-----------|------|--------------|
| Mensal | 225 | 774 | 4.126.327,68 | 577.433,34 |
| Rescisão | 4 | 4 | 8.639,47 | 1.209,53 |
| 13º salário | 1 | 1 | 5.364,84 | 751,08 |

Mais o catálogo real de Aripuanã (`arquivos_base/fontes_pag/`, 1.215 fontes):
das 59 fontes da folha mensal, 51 casam sozinhas — 726 dos 774 segurados — e as
8 restantes são as três com número repetido no catálogo e as cinco que ainda
não existem nele.

Todos os 779 registros com CPF válido (módulo 11) e matrícula numérica, sem
aviso nenhum. Dos 774 da folha mensal, 50 têm **dois** descontos
previdenciários no mês (`8850 + 8857` em férias, `8850 + 8873` em
auxílio-doença) e são somados numa linha só.
