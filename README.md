# Atualiza Arrecadação

Lê a folha de pagamento em PDF e monta o arquivo de importação do módulo de
arrecadação do SISPREVWEB.

A equipe de arrecadação escolhe o município — que traz as regras dele —,
anexa o PDF da folha, confere a tabela na tela e exporta em `.xlsx` (para
conferir) ou `.csv` (para importar).

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
quando a última é resolvida. Cada linha diz também **quem está naquela fonte** —
quantos segurados e de qual unidade, com a lista completa no balão e um clique
que a copia. O nome do grupo (`600 - 2067 - SAMU EFETIVOS 1.600.000.603`) às
vezes não diz nada a quem vai procurar no SISPREVWEB; o servidor que está nele
diz, e a unidade dele diz mais ainda. A aba *Resumo* do XLSX registra o município e
quantas linhas vieram de cada regra, e o município entra no nome sugerido do
arquivo — `Arrecadacao_Aripuana_2026-08_Mensal.csv` —, porque a mesma
competência sai para 29 prefeituras e ordenar a pasta por nome tem de agrupar
por cidade.

---

## Regras por município

O trabalho anda em quatro etapas, desenhadas no Início ("Como o trabalho
anda") e repetidas no alto da tela da arrecadação, onde mostram o que já foi
feito e o que falta:

    1 · Município     →  2 · Folhas          →  3 · Conferência       →  4 · Exportar
    traz as regras       PDFs e complementar     números, avisos, fontes   o arquivo do SISPREVWEB

O município vem **antes** do PDF porque é ele que diz o que fazer com a folha.
A tela **Municípios** tem a *regra geral* e, para cada município, só o que ele
tem de diferente — cada campo começa em "Seguir a regra geral (…)". Mudar a
regra geral muda todos os que a seguem.

| Regra | O que decide |
|---|---|
| Formato da folha | qual leitor usar; o padrão é o programa reconhecer sozinho |
| 13º dentro da rescisão | **somar** à linha do mês ou **separar** na competência 13 |
| Arquivo complementar | o município manda um CSV junto (Nova Olímpia) |
| Categoria | a coluna 10 do layout |
| Descontos que não são / que são do RPPS | código da verba ou pedaço da descrição; **somam-se** aos da regra geral |
| Observações | o que quem faz a arrecadação precisa lembrar |

As regras ficam em `%LOCALAPPDATA%\AtualizaArrecadacao\regras_municipios.json`,
ao lado do cadastro de fontes. Na primeira abertura, Nova Olímpia já vem
pedindo o CSV complementar. Município que falta na lista se acrescenta na
própria tela.

Trocar o município ou uma regra **depois** da leitura refaz as linhas sem reler
o PDF: `regras.aplicar` trabalha sobre uma cópia da folha lida, que fica
intacta. E se o cabeçalho da folha falar de outra cidade que não a escolhida,
a tela avisa — é o jeito de perceber o PDF do município errado antes de
creditar nas fontes erradas.

### O 13º dentro da rescisão

A rescisão que paga o 13º proporcional traz a previdência dele no mesmo bloco.
Em Aripuanã, FULANA DE TAL:

| Verba | Base | Valor |
|---|---|---|
| 8850 PREVIDENCIA MUNICIPAL | 504,91 | 70,69 |
| 8847 PREVIDENCIA S/ 13º SALARIO RESCISAO | 1.472,65 | 206,17 |
| 10004 Base Patronal para RPPS | 1.977,56 | 276,86 |

A própria folha soma os dois na base patronal, e **somar** (o padrão) faz o
mesmo: uma linha em 08 com 1.977,56 / 276,86. **Separar** dá duas — 08 com
504,91 / 70,69 e 13 com 1.472,65 / 206,17 —, levando junto o provento de 13º
para a conferência de proventos continuar fechando. Se toda a previdência do
bloco era de 13º (Barra do Garças, `992 PREVIDENCIA FUNDO 13º SALARIO
PROPORC`), o bloco inteiro muda para 13, em vez de deixar uma linha de base
zero no mês. Casos nas folhas de `arquivos_base/`: 4 em Aripuanã, 2 em
Paranatinga, 3 em Barra do Garças.

### O arquivo complementar (Nova Olímpia)

A Dura Lex não imprime a base de cada servidor, só a contribuição, e a base
deduzida dela fica alguns centavos longe da real. Nova Olímpia manda junto um
CSV que **já está no layout do SISPREVWEB** (matrícula; nome; ano; mês; base;
contribuição; patronal; especial; fonte; categoria). Ele é anexado com os PDFs
— arrastado junto, ou pelo PROCURAR — e lido por `complementar.py`.

O PDF continua sendo lido: o CSV é o que a prefeitura diz que descontou, e a
folha é o que ela pagou. Os dois se conferem, e o que não bate vira aviso:

* a base vem do CSV **só para quem tem a mesma contribuição** nos dois;
* contribuição diferente, servidor só na folha, matrícula só no CSV e fonte
  pagadora diferente são listados na tela;
* o CSV de **outra competência não é usado** — o de 08/2026 anexado à folha de
  07/2026 fica de fora, com aviso;
* a fonte pagadora que o catálogo não resolve sai do código que o CSV dá para
  os servidores dela, quando todos dizem o mesmo (origem "arquivo
  complementar do município"). Nova Olímpia não tem catálogo na pasta: com o
  CSV, as fontes sem código caem de 42 para 4.

As matrículas casam sem os zeros da frente: "000014" no PDF é "14" no CSV.

---

## Como o PDF é lido

O PDF da folha não tem tabela — tem texto posicionado. Pedir
`pagina.get_text()` devolve as palavras na ordem interna do arquivo, que
intercala o bloco dos rótulos com o bloco dos valores; ler assim é adivinhar.

`arrecadacao/leitor_pdf.py` remonta a página pelas **coordenadas**: palavras
com o mesmo topo formam uma linha, um vão grande separa uma célula da outra, e
cada célula vai para a coluna do cabeçalho mais próxima.

"Mesmo topo" é: até 2 pontos abaixo da palavra mais alta da linha. Antes era
arredondando o topo a faixas fixas de 3 pontos, e faixa tem fronteira — a
descrição "PREVIDENCIA - FUNDO" em y=727,3 e o código "942" com os valores em
727,6 caíam em faixas vizinhas e viravam duas linhas. A verba ficava sem nome e
o servidor sem previdência: 77 em Barra do Garças e 58 em Confresa saíam
zerados assim.

Outras duas medidas foram calibradas contra a folha real e estão comentadas no
código:

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

### Mais de um formato de folha

Cada prefeitura contrata o seu sistema de folha, e os PDFs não têm uma linha em
comum. São 29 municípios: o programa lê **uma família de formatos**, não um.

| formato | município de referência | o que abre o bloco |
|---|---|---|
| `Agili` | Aripuanã, Paranatinga | `Funcionário(a)  Matrícula  Situação …` |
| `ARFolha` | Rosário Oeste, Barra do Garças, Confresa, Chapada dos Guimarães, Tabaporã, Santo Antônio de Leverger | `SERVIDOR: 9999.1 - FULANA …` |
| `Betha` | São José do Povo | `Func.: 9999 - FULANA … CPF: …` |
| `Betha (extrato mensal)` | Vila Bela da Santíssima Trindade, Santa Terezinha | `Código  Funcionário  C.P.F.  Admissão …` |
| `Centi` | Campinápolis (câmara), São Félix do Araguaia | `Funcionário 1 - FULANA … CPF` … `Base calc. previdência:` |
| `Dura Lex` | Nova Olímpia | `Código  Nome  Tipo  Func.  Função …` |
| `FastReport` | Campinápolis (prefeitura) | `Funcionário: 1990 - FULANA C.P.F.: …` |
| `Fiorilli` | Primavera do Leste, Colniza, Comodoro, Jauru, Cocalinho | `Matrícula  Nome do Trabalhador  Admissão …` |

O **Dura Lex** é o único em que a contribuição não é verba: o relatório já vem
filtrado pelo RPPS e traz só o valor, no rodapé de cada servidor, e a base
apenas nos resumos de seção. A parte do 13º sai exata (o provento de 13º é a
base dele) num segurado à parte, na competência 13; a base **mensal** é
deduzida da contribuição e calibrada seção a seção contra o resumo — os
totais fecham com a folha, mas cada servidor pode ficar até 7 centavos de base
longe do verdadeiro (a contribuição, não: ela é lida). Ver o cabeçalho de
`formatos/duralex.py`.

No **Centi** de São Félix do Araguaia, o fecho `Base calc. previdência` de cada
bloco imprime o **dobro** da base: a verba `142 PREVIDENCIA RPPS` tem base
3.297,92 e retém 461,70 (14%), e o fecho diz 6.595,84. O resumo do RPPS no fim
do PDF soma as bases das verbas, então é a coluna da verba que vale; o fecho só
é usado quando a verba vem sem base.

Dois deles põem **proventos à esquerda e descontos à direita**, duas verbas por
linha visual; a linha é cortada na divisa e cada metade lida com o seu próprio
cabeçalho. Ler a linha inteira como uma verba juntaria o vencimento com a
mensalidade do sindicato.

Cada um é um módulo em `arrecadacao/formatos/` que responde duas perguntas:

```python
pontuar(linhas) -> int      # quantos blocos MEUS este PDF tem?
ler(linhas, folha)          # extraia o cabeçalho e os segurados
```

Quem abre o arquivo não escolhe nada: `extracao.ler` pergunta a todos e fica
com o de maior pontuação. As marcas são exclusivas — o PDF de um gerador
pontua **zero** no outro —, então a escolha não é palpite. Quando ninguém
reconhece, a mensagem diz quais formatos existem, porque "formato não
reconhecido" sozinho não dá o que fazer a quem leu.

**Acrescentar o próximo formato** é escrever um módulo com essas duas funções
e inscrevê-lo em `formatos.LEITORES`. Nada do que já está em produção é
tocado — e esse é o ponto: o próximo município com folha diferente não deve
exigir mexer no leitor que já funciona.

O que é comum fica fora dos formatos: emendar as páginas, somar a base,
reconhecer o desconto previdenciário pela descrição, casar a fonte pagadora,
montar o layout. Os leitores entregam o **mesmo** `Segurado`, com as verbas
marcadas `P`/`D` pela coluna em que o valor caiu, e daí para a frente o
caminho é um só.

### Como o desconto previdenciário é reconhecido

Pela **descrição** da verba de desconto, com uma regra de palavra
(`folha.RE_NOME_DA_PREVIDENCIA`): uma palavra que começa por `PREVI`, a palavra
`PREV` sozinha, `FUNPREV`, `RPPS` ou `I.M.P.V.B.`. Começou como uma lista de
nomes, um por município, e a lista perdeu a corrida — cada prefeitura batiza o
próprio fundo: `PREVIDÊNCIA - FUNDO`, `FUNPREV`, `PREV COLNIZA`, `PREVILA`,
`PREVICON`, `PREVISERV`, `PARANATINGA PREV`, `PREVIPORÃ`, `PREVI-CAMP`… Sete
folhas chegaram de uma vez com todos os servidores zerados, porque o nome do
fundo não estava na lista.

O que tem cara de previdência e **não** é a do regime próprio fica de fora
(`folha.RE_NAO_E_DO_RPPS`): INSS (regime geral), previdência complementar ou
privada (em Aripuanã, `8900 PREVIDENCIA COMPLEMENTAR` é 8,5% sobre o que passa
do teto do RPPS; em Jauru, `715 BB PREV CONTRIBUIÇÃO DO`, a do Banco do
Brasil), seguradora (`809 CAPEMISA-PREV/SEG` em Leverger), consignado e
empréstimo tomados no fundo (`CONSIGNAÇÃO COMODORO-PREVI 3/96`) e rótulos de
coluna lidos como verba (`B. Prev Outros`, Palavra inteira, não pedaço: `CONSIGNADO IMPREV` tem "PREV" no meio e não
entra. O que a regra de palavra errar num município se corrige na tela
Municípios, sem mexer no código.

Na câmara de Colniza a folha de **férias** vem no mesmo PDF da mensal, e a
mensal já traz as férias por dentro (inclusive a `947 PREV COLNIZA - FÉRIAS`).
O leitor Fiorilli não soma os dois blocos — cobraria a contribuição das férias
duas vezes. Ele usa a base de férias impressa no bloco de férias para a verba
947 do mensal, e o bloco de férias sai da lista: uma linha por servidor, com
base e contribuição do mês inteiro.

Vila Bela não usa a palavra "previdência" em nenhuma das duas folhas: a
prefeitura desconta `56 PREVILA` (o nome do fundo) e a câmara `56 I.M.P.V.B. -
INST.PREV.PÚB. MUN.`. O extrato do Betha traz ainda os processamentos Mensal,
Férias e Complementar no mesmo PDF, e o mesmo servidor em mais de um bloco — o
mensal, com a previdência, e outro de base zero com as diárias ou o 1/3 de
férias. O leitor junta os blocos da matrícula num servidor só; se dois deles
tiverem previdência, não junta, e o aviso de matrícula repetida aparece.

É aqui que mora o erro mais perigoso do programa: a verba que não é
reconhecida não dá erro — o servidor sai com base e contribuição **zero**, e a
planilha fecha. O erro do outro lado é tão silencioso quanto: a verba que entra
sem ser do RPPS infla base e contribuição. Por isso o autoteste confere os
nomes que devem entrar **e** os que devem ficar de fora, cada um vindo de uma
folha real.

### Vários documentos, e vários tipos de folha num PDF

A arrecadação de um mês raramente cabe num arquivo só: a prefeitura exporta a
folha dela e a câmara a sua, e o SISPREVWEB recebe **um arquivo por
município**. `extracao.ler_varios` lê cada PDF com o seu próprio leitor e
devolve uma folha só, guardando em `Folha.origens` de qual documento veio cada
coisa — é o que permite o aviso nomear o arquivo certo quando um deles vem
digitalizado.

No sentido contrário, um PDF pode trazer **várias folhas**: o de Barra do
Garças empilha mensal, 13º salário, rescisão, rescisão complementar e
complementar. Por isso `Segurado.tipo_folha` guarda de qual delas veio o
bloco — os servidores que estão na mensal *e* na de 13º sairiam com duas
linhas na mesma competência, que a importação recusa.

Atenção ao relatório que **junta** processamentos sem separá-los: o Agili de
Paranatinga escreve "(Rescisão, 13º salário, Mensal)" no subtítulo. Isso não é
folha de 13º — quando o tipo fala também em mensal ou normal, a folha é a do
mês. E a rescisão que paga o 13º proporcional junto (`8101 PARANATINGA PREV 13
SALARIO`) segue a regra do município — ver [O 13º dentro da
rescisão](#o-13º-dentro-da-rescisão).

---

## Estrutura

```
app_arrecadacao.py        ponto de entrada e autoteste
arrecadacao/              o motor, sem nenhuma dependência de interface
  leitor_pdf.py             palavras -> linhas -> colunas
  extracao.py               escolhe o formato, emenda as páginas, avisa
  formatos/                 um leitor por gerador de folha (ver a tabela acima)
  folha.py                  modelos: Folha, Segurado, Verba, Competência
  regras.py                 as regras de cada município, e a aplicação delas
  complementar.py           o CSV que o município manda junto com a folha
  layout.py                 segurados -> colunas do layout, e as pendências
  fontes.py                 catálogo do SISPREVWEB e o casamento com a folha
  municipios.py             os municípios atendidos, e qual deles a folha é
  exportacao.py             gravação do .xlsx e do .csv, e o nome sugerido
casca/                    a janela — mesma casca do AutoArial
  tela_inicio.py            "Como o trabalho anda" e os pontos de partida
  tela_folha.py             a arrecadação: município, anexar, conferir, exportar
  tela_municipios.py        a regra geral e a de cada município
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
| Mensal | 225 | 774 | 4.121.735,97 | 577.043,04 |
| Rescisão | 4 | 4 | 8.639,47 | 1.209,53 |
| 13º salário | 1 | 1 | 5.364,84 | 751,08 |

A mensal saía antes com 4.126.327,68 / 577.433,34: somava a `8900 PREVIDENCIA
COMPLEMENTAR` de três servidores acima do teto, que não é do RPPS.

E, conferidas contra o que a **própria folha imprime** — o resumo do RPPS, a
base impressa por servidor ou o total geral do PDF:

| Folha | Leitor | Segurados | Base | Conferido contra |
|---|---|---|---|---|
| Comodoro | Fiorilli | 573 | 3.516.378,12 | "Total Geral" da última página |
| Vila Bela (prefeitura / câmara) | Betha extrato | 536 / 20 | 2.167.525,34 / 117.778,27 | Base Prev de cada bloco; totais de proventos e descontos |
| Chapada dos Guimarães | ARFolha | 258 | 1.944.840,85 | "Base Previdência" de cada servidor |
| Tabaporã (prefeitura / câmara) | ARFolha | 377 / 5 | 2.353.116,91 / 32.299,04 | "Base Previdência" de cada servidor |
| Paranatinga | Agili | 628 | 3.863.840,90 | "Base Patronal para RPPS" de cada servidor |
| Campinápolis câmara | Centi | 7 blocos | 48.794,04 | resumo RPPS (retido 6.831,14) |
| Campinápolis prefeitura | FastReport | 420 | 2.556.140,75 | total geral de proventos e descontos; 14% em todos |
| Nova Olímpia prefeitura | Dura Lex | 383 (+59 de 13º) | 2.180.543,51 + 44.237,19 | resumo SIMPREV (305.274,74 + 6.192,93) |
| Nova Olímpia câmara | Dura Lex | 5 | 36.640,38 | resumo SIMPREV (5.129,65) |
| São Félix do Araguaia prefeitura | Centi | 88 | 453.303,57 | resumo RPPS (retido 63.462,04); totais de proventos e descontos |
| São Félix do Araguaia câmara | Centi | 23 blocos (10 com RPPS) | 118.451,99 | resumo RPPS (retido 16.583,22) |
| Santo Antônio de Leverger câmara | ARFolha | 3 | 27.835,77 | "Base Previdência" dos TOTAIS (3 servidores, proventos 44.254,30) |
| Santo Antônio de Leverger prefeitura | ARFolha | 240 (231 normal, 2 rescisão, 7 complementar) | 1.138.935,20 | blocos e "TOTAL PROVENTOS" de cada bloco (1.611.757,14); retido 159.449,83 |
| Jauru prefeitura | Fiorilli | 263 | 1.248.422,78 | "Total Geral" e a "Base Prev." de cada servidor; retido 174.779,33 |
| Jauru câmara | Fiorilli | 6 | 46.653,38 | "Total Geral" e a "Base Prev." de cada servidor; retido 6.531,47 |
| Cocalinho (folha mensal) | Fiorilli | 174 | 766.465,24 | "Base Prev." de cada servidor — 173 de 174; ver abaixo |
| Santa Terezinha prefeitura | Betha extrato | 202 (204 blocos) | 1.055.808,59 | "Base Prev" de cada bloco e "Totais da quebra" (proventos 1.310.132,93); retido 147.813,20 |

Em Cocalinho o "Total Geral" diz 764.265,24 de base, 2.200,00 a menos que o
programa. A diferença é um servidor só: FULANO DE TAL
desconta "947 PREVIDÊNCIA FÉRIAS - FUNDO 14,00 308,00" e a folha imprime "Base
Prev. 0,00" — a coluna não leva a base das férias, como na câmara de Colniza.
Os 308,00 são do RPPS, e 2.200,00 é a base deles a 14%. A outra folha de
Cocalinho ("folha de concursado") é uma página digitalizada, sem texto: a
tela avisa e não lê nada dela.

A câmara de Santa Terezinha chegou como **foto** (Adobe Scan do celular): a
imagem cobre a página e o texto que o OCR reconheceu fica por cima, invisível
— "11.158.38", "PREVIDÉNCIA", colunas fora de ordem. Ter texto não a torna
legível: `leitor_pdf._e_escaneada` trata como digitalizada a página com uma
imagem cobrindo 90% dela **e** mais texto invisível que visível, e esse texto
não é lido. Nas folhas de `arquivos_base/` só as duas páginas do Adobe Scan
cumprem as duas condições; nenhuma folha gerada por sistema tem imagem acima de
6% da página. A tela pede o PDF gerado pelo sistema, em vez de sugerir um
leitor novo.

Em Jauru o **total de proventos** da tela não fecha com o da folha (só a
conferência; não vai no arquivo): o PDF desenha o último dígito do salário por
baixo da coluna vizinha — "SALARIO BASE 30.00D 17.055,2" para 17.055,26 —, e
há bloco em que o provento inteiro se perde. Base e contribuição fecham
servidor a servidor.

Nas folhas ARFolha, além disso, o número de blocos `SERVIDOR:` lidos é
conferido contra os contados no texto cru do PDF, e a soma de proventos contra
o "TOTAL PROVENTOS" de cada bloco — bate em todas. Foi essa conferência que
achou os servidores cuja matrícula curta fica longe do rótulo `SERVIDOR:` (ela
é alinhada à direita no campo) e cujo nome encosta no `CPF:`: sumiam em
silêncio 14 em Leverger, **102 em Barra do Garças** (3.233 → 3.335) e **10 em
Confresa** (534 → 544).

Mais o catálogo real de Aripuanã (`arquivos_base/fontes_pag/`, 1.215 fontes):
das 59 fontes da folha mensal, 51 casam sozinhas — 726 dos 774 segurados — e as
8 restantes são as três com número repetido no catálogo e as cinco que ainda
não existem nele.

Todos os 779 registros com CPF válido (módulo 11) e matrícula numérica, sem
aviso nenhum. Dos 774 da folha mensal, 50 têm **dois** descontos
previdenciários no mês (`8850 + 8857` em férias, `8850 + 8873` em
auxílio-doença) e são somados numa linha só.
