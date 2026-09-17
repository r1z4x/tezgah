<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh.md">简体中文</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.br.md">Português (Brasil)</a> |
  <a href="README.tr.md">Türkçe</a>
</p>

# Tezgah

<p align="center">
  <img src="assets/logo/tezgah-logo.svg" alt="tezgah logo" width="220">
</p>

<h3 align="center">Um único contrato de trabalho para cada assistente de código de IA que você executa.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">O que ele impõe</a> &bull;
  <a href="#supported-hosts">Hosts suportados</a> &bull;
  <a href="#install">Instalação</a> &bull;
  <a href="#day-to-day">Dia a dia</a> &bull;
  <a href="#configuration">Configuração</a> &bull;
  <a href="#benchmark">Benchmark</a> &bull;
  <a href="#cost">Custo</a> &bull;
  <a href="#development">Desenvolvimento</a> &bull;
  <a href="#contributing">Contribuição</a> &bull;
  <a href="#security">Segurança</a> &bull;
  <a href="#license">Licença</a>
</p>

<p align="center"><sub>O inglês é a fonte da verdade; as traduções podem estar desatualizadas em relação a ele.</sub></p>

---

Um único contrato de trabalho para cada assistente de código de IA que você executa — Claude Code,
opencode, Codex, Cursor e o harness dsh da DeepSeek — dentro de um conjunto de
raízes de repositório configuradas.

Deixados por conta própria, cada assistente tem seus próprios hábitos: um responde em turco, outro
em inglês; um usa grep para tudo, outro consulta um grafo de código; um diz
"concluído" sem executar um teste. O tezgah remove esse desvio. Abra qualquer host e você
obterá o mesmo idioma, a mesma disciplina e o mesmo padrão de evidência.

O design tem duas camadas. As regras vivem uma única vez em um núcleo compartilhado; cada host recebe
um adaptador fino que traduz esse núcleo para o formato que o host entende.
Mude uma regra em um lugar e todos os cinco hosts a verão — sem cópias quíntuplas do
mesmo texto.

<a id="what-it-enforces"></a>

## O que ele impõe

- **Relatórios em turco focados no resultado.** Toda resposta é em turco e começa com
  o resultado ou decisão (BLUF), seguida de pontos ordenados por impacto. Código, commits,
  documentação e prompts de subagentes permanecem em inglês; nomes, comandos de CLI e strings de
  erro nunca são traduzidos.
- **Código mínimo (ponytail).** A alteração mais preguiçosa que realmente funciona: YAGNI,
  depois reutilizar um helper existente, depois a stdlib, depois um recurso nativo da plataforma,
  depois uma dependência instalada, depois uma linha. Sem abstrações não solicitadas.
  Validação, tratamento de erros e segurança nunca são simplificados ou removidos.
- **Descoberta baseada primeiro no grafo de código.** "Onde está X", "quem chama Y", "o que quebra se
  Z mudar" vão para o grafo `codebase-memory-mcp` (`search_graph`,
  `trace_path`, `search_code`), não para o grep. O grep continua sendo a escolha certa para texto literal,
  configurações e arquivos que não são de código.
- **Análise de aplicativo baseada primeiro em acessibilidade.** Um aplicativo web ou mobile em execução é lido
  através de sua árvore de acessibilidade / DOM / visualização nativa, não por uma captura de tela a cada passo.
  `analyze-app` cobre um navegador (Playwright MCP), um Simulador iOS ou emulador Android (Mobile MCP),
  e diagnósticos web opcionais (Chrome DevTools MCP); uma captura de tela é uma ação explícita e sob demanda
  para o que a árvore não consegue responder.
- **Segunda opinião externa.** Antes de uma decisão não trivial ou difícil de reverter,
  `~/.config/tezgah/bin/consult` consulta modelos independentes através do OpenRouter (ou a API da DeepSeek
  com `--provider deepseek`) em paralelo, e o agente relata onde eles
  concordaram ou discordaram.
- **Pesquisa via OpenResearch.** Quando o roteador julga que uma tarefa é de pesquisa — uma
  revisão de literatura, formulação e teste de hipóteses, execução de experimentos, um
  artefato de pesquisa — ele conduz o trabalho através do OpenResearch da alphaXiv (`orx`)
  e carrega o manual do `orx` primeiro, em vez de improvisar o protocolo. A descoberta de código
  simples permanece no grafo de código. Quando o `orx` está ausente, o roteador informa
  isso e recorre a um subagente do host.
  O conhecimento de domínio de que um experimento precisa vem junto: a biblioteca
  `AI-research-SKILLs` integrada (98 skills, 23 categorias, MIT) chega como a skill
  `ai-research` e é lida entrada por entrada a partir do seu índice por estágio.
- **Honestidade sob verificação.** Nada é relatado como concluído, testado ou corrigido
  a menos que a saída tenha sido vista. Um teste que falha é relatado como falho com seu
  erro exato, e uma verificação ignorada é declarada claramente.
- **Sem atribuição de IA, em lugar nenhum.** Nada persistido ou publicado — mensagens de commit,
  merge e tag, textos de PR e issues, comentários de código, cabeçalhos de arquivos, documentação
  — pode dar crédito ao assistente, modelo, fornecedor ou "IA". Usar uma ferramenta é aceitável;
  assinar o nome dela no seu trabalho não é.
- **Orquestração em duas camadas.** A thread principal decide e verifica; um modelo barato
  (`~/.config/tezgah/bin/codegen`, OpenRouter por padrão ou `--provider deepseek`) elabora
  rascunhos de edições limitadas e bem especificadas em um diretório temporário. Nada chega ao repositório
  exceto através do roteador, e um rascunho que falha retorna automaticamente para o modelo principal.
- **Subagentes por repositório.** No início da sessão, o repositório em questão recebe um pequeno conjunto de
  agentes com capacidades restritas (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) mais um `tezgah-orchestrator`, renderizados
  na superfície nativa de cada host instalado (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` mais uma injeção de configuração em tempo real, Codex
  `.codex/agents/`) e ignorados com um bloco `.gitignore` gerenciado. No Claude, a
  lista de permissões `Agent(tezgah-*)` do orquestrador só entra em vigor quando ele é executado como a
  thread principal (`claude --agent tezgah-orchestrator`); como um subagente, a lista é
  ignorada. O dsh não tem superfície por função, então a regra do roteador do contrato o cobre.

<a id="supported-hosts"></a>

## Hosts suportados

| Host | Conectado por |
|---|---|
| **omp** (oh-my-pi) — primário | `~/.omp/agent`: bloco always-on gerenciado `RULES.md`, skills, subagentes gerados, `mcp.json`, e uma extensão (`hooks/pre/tezgah-hook.ts`) que arma as regras por prompt, passa ferramentas pelo portão, registra evidências e executa a regra Stop; a fiação é verificada por `tezgah-setup` |
| **Claude Code** | marketplace de plugins local: hooks, comandos, dois agentes somente leitura, estilo de saída |
| **opencode** | plugin + instruções + MCP + roteador de skills gerado (lista de skills nativa negada), auto-indexação do repositório na primeira mensagem |
| **Codex** | `hooks.json` + skills + MCP, incluindo um portão `PreToolUse` |
| **Cursor** | `hooks.json` + skills + MCP |
| **dsh** | ponte de hooks do Claude Code + bloco de patch gerenciado (hooks, MCP, rotas de LLM, uma linha de status Web fora da árvore) |

O portão do Codex executa Bash, `exec_command`, `apply_patch`, Edit/Write, ferramentas MCP,
e chamadas de subagentes através da mesma verificação que os outros hosts. No Claude, a
proibição de atribuição também é imposta mecanicamente: a configuração `attribution` é
esvaziada (`commit`, `pr`, `sessionUrl`) para que os créditos de commit e PR sejam desativados na origem.

### Análise de aplicativo

`analyze-app` conduz um aplicativo em execução a partir de sua árvore de acessibilidade. O
loop padrão é abrir, ler a árvore, agir, observar console/rede/logs e
reler a árvore — uma captura de tela é uma ação explícita para o que a árvore não consegue
responder (canvas, jogo, animação, regressão visual em nível de pixel). A skill é
um caminho único para todos os hosts; os servidores sob ela são uma especificação compartilhada em
`hooks/tezgah_apps.py`:

| Servidor | Alvo | Conectado por |
|---|---|---|
| `playwright` (`@playwright/mcp`) | páginas web, ferramentas `browser_*` | opencode, Codex, Cursor, Claude (plugin `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | Simulador iOS / emulador Android, ferramentas `mobile_*` | o mesmo |
| `chrome-devtools` (opt-in, `--devtools`) | rastreamentos de desempenho web, rede profunda, console com source-map | o mesmo |

O navegador executa um perfil **isolado** por padrão, então uma execução nunca toca no
seu estado real do Chrome; analisar um fluxo logado é um anexo deliberado
(`--cdp-endpoint` ou a extensão do Playwright), não um padrão. Capturas de tela,
rastreamentos e dumps de árvore vão para `~/.cache/tezgah/apps` (substitua com
`TEZGAH_ARTIFACTS`) e o agente recebe um caminho de volta, nunca bytes de imagem inline.
Os servidores são executados através do `npx`, então eles precisam do node, mas não de uma instalação própria;
`tezgah-setup --install --devtools` adiciona o servidor opcional de diagnósticos web.
O dsh conecta os mesmos dois servidores através de sua ponte `dsh-mcp-client`
(`serverName` / `command` / `args` / `env`, confirmados contra o esquema de configuração
publicado), e o Claude os obtém do `.mcp.json` do plugin
(`claude plugin details tezgah` lista os servidores MCP 2 e ambos se conectam).
`mobile-mcp` é a metade com maior atrito: o macOS pode solicitar permissão de Acessibilidade /
Gravação de Tela e a árvore de visualização pode cair sob carga, então a skill
tenta novamente a árvore antes de recorrer a uma captura de tela.

A CI executa um handshake determinístico para ambos os servidores (sem navegador, sem dispositivo):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. Dois testes de fumaça locais
opt-in vão além: `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` inicia o
Playwright MCP, navega e lê o snapshot sem captura de tela;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` inicia o Mobile MCP, verifica
as ferramentas de árvore de visualização e lista um dispositivo. Eles imprimem `SKIP: ...` quando o node,
uma build de navegador ou um dispositivo estão ausentes.

<a id="install"></a>

## Instalação

Requer Python 3.8+. node + npm são necessários para o host dsh e, com `pnpm`,
para sua linha de status web. As integrações opcionais degradam graciosamente:
`codebase-memory-mcp` no PATH alimenta o grafo; uma chave de modelo alimenta `consult`
e `codegen` — OpenRouter por padrão (`OPENROUTER_API_KEY` ou
`~/.config/openrouter/key`), ou a API da DeepSeek com `--provider deepseek`
(`DEEPSEEK_API_KEY` ou `~/.config/deepseek/key`); e o `orx` do OpenResearch
no PATH dá à regra de pesquisa algo para conduzir. Quando a chave do provedor escolhido
está ausente, o tezgah informa isso em vez de fingir.

Clone e, em seguida, arme todos os hosts detectados em uma única passagem:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

Em um terminal, esse comando sem argumentos é o assistente de instalação: ele pergunta quais
hosts armar, os diretórios-raiz, se deve instalar as ferramentas opcionais ausentes, e se
deve fiar o DevTools MCP opcional, imprime o plano, e só escreve depois de um sim. As flags
são os padrões do assistente, então `--wizard --hosts omp` pergunta só o resto. Uma execução
em pipe, agente ou CI nunca é solicitada — ela imprime o relatório, exatamente como antes.

`--install` também instala as ferramentas opcionais que estão ausentes executando o próprio
instalador de cada fornecedor **pela rede**: `orx` (`openresearch.sh/install.sh`),
`cursor-agent` (`cursor.com/install`), `dsh` (seu perfil home através do `npx`), e `pnpm`
quando o dsh precisa dele (via `npm`) — `curl ... | sh` incluído. Nenhum precisa de sudo; a
execução é registrada em
`~/.config/tezgah/install.log`. Visualize com `--dry-run`, ignore com
`--no-deps` (útil em CI), ou instale apenas as ferramentas com `--deps`. As ferramentas vão
para `~/.local/bin` ou `~/.cargo/bin`, então um novo shell pode ser necessário antes que
elas estejam no PATH; as próprias verificações do tezgah procuram nesses diretórios independentemente,
então um shell não interativo ainda as relata como presentes.

Se uma configuração anterior já estiver presente, importe-a primeiro — ela é movida para o lado,
não excluída:

```bash
bin/tezgah-setup --adopt
```

O Claude Code é armado pelo mesmo script - o manifesto do plugin é um arquivo local, não versionado:

```bash
bin/tezgah-setup --install --hosts claude
```

Limite a instalação explicitamente quando necessário:

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Dia a dia

Nada para executar: as regras são carregadas quando um host é iniciado. Vale a pena conhecer alguns comandos:

| Comando | Propósito |
|---|---|
| `bin/tezgah-setup` | No terminal: o assistente de instalação; em um pipe ou na CI: relatar o que está armado, por host |
| `bin/tezgah-setup --wizard` | Forçar o assistente de instalação em qualquer lugar; `--report` força o relatório |
| `bin/tezgah-status [PATH]` | Mostrar se as regras estão ativas naquele repositório |
| `bin/tezgah-setup --status [PATH]` | Imprimir a checklist armada/usada |
| `bin/tezgah-setup --deps [--dry-run]` | Instalar ferramentas opcionais ausentes (orx, cursor-agent, dsh) |
| `bin/tezgah-research init\|check\|status\|claim` | Cria e verifica uma linha de pesquisa: estado, findings, claims e a regra protocolo-antes-dos-resultados |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Relatar o uso de disco do harness; `--clean` exclui logs de índice antigos e faz vacuum no BD do opencode; `--prune-sessions` exclui sessões ociosas (a única ação que realmente reduz o BD) |
| `/tezgah:plan-add` | Transformar um trabalho em um plano rastreado |
| `/tezgah:plan-status` | Resumir planos abertos e escolher o próximo |
| `/tezgah:plan-sync` | Fechar planos concluídos |
| `bin/tezgah-setup --version` | Imprimir a versão do plugin |
| `bin/tezgah-setup --uninstall` | Remover apenas os links simbólicos do tezgah, entradas de hook do host e o bloco gerenciado do dsh |

<a id="configuration"></a>

## Configuração

O Tezgah é armado apenas sob suas raízes configuradas; em qualquer outro lugar, ele é silencioso.

- Raiz padrão: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (lista separada por separador de caminho) substitui o arquivo para casos isolados e CI.

Os kill switches vivem em `~/.config/tezgah/`. Cada um remove sua regra do
texto injetado na sessão, para que a regra realmente pare:

| Switch | Desativa |
|---|---|
| `exec-mode.off` | relatórios em turco focados no resultado |
| `ponytail-auto.off` | a regra de código mínimo |
| `spec-off` | a regra de especificação antes de construir |
| `consult-off` | a regra de segunda opinião externa |
| `research-off` | o roteamento de tarefas de pesquisa para o OpenResearch |
| `orchestrate-off` | a delegação de subagentes (adiciona uma linha de não delegar) |
| `reminder-off` | o texto de lembrete por turno |
| `pretooluse-off` | o próprio portão PreToolUse (atribuição, explorador, lembrete de grep) |

Por repositório, `.no-ponytail`, `.no-cbm` e `.no-lessons` desativam a regra de código mínimo,
a regra de grafo de código (e sua auto-indexação) e o registro de lições, respectivamente.

Quando o usuário sinaliza um erro, o agente anexa uma lição de uma linha ao
`.tezgah/lessons.md` do repositório; as linhas mais recentes são injetadas no início da sessão para que
o mesmo erro não possa se repetir silenciosamente.

<a id="benchmark"></a>

## Benchmark

Este contrato melhora o trabalho, ou só parece que deveria? Isso é medido em
`benchmarks/arm-bench/`, não afirmado: verificações ocultas que o agente nunca vê, custo a
partir do próprio registro de uso do host, e edições colaterais pontuadas como falhas.
`PREREGISTRATION.md` fixa os endpoints antes de uma execução e `python3 bench.py report` os
imprime; o estudo completo, com os ids das execuções, é
`docs/research/2026-09-16-tezgah-quality.md`. Cada número abaixo é um log de execução.

| Bloco | Execuções | O que ele resolveu |
|---|---|---|
| dois hosts, 28 tarefas, k=3 | 336 | `omp+tezgah` 0.95 e `opencode+tezgah` 0.96 têm intervalos sobrepostos e o mesmo custo por tarefa resolvida; nos braços nus o omp é mais barato ($0.0047 contra $0.0074 CPS), então o cavalo de batalha diário é o omp sem custo em qualidade |
| família difícil, 5 tarefas, k=5, duas famílias de modelos | 200 | agrupados, três dos quatro braços chegam a 40/50: nenhum efeito de harness nesse tamanho, e o único sinal que o primeiro modelo produziu se inverteu no segundo |
| família do portão, portão armado | 36 | nenhum braço pegou a rota de atalho; o mecanismo do portão é verificado diretamente (uma edição de skip é recusada), seu efeito sobre o trabalho ainda não é medido |
| ablação de cláusulas, as duas regras que separam, k=8 | 160 | os braços com contrato passam 23/32 (0.72) contra 12/32 (0.38) da âncora nua |


**Ele ajuda exatamente onde o padrão do modelo está errado.** `c04` (um prompt em inglês
onde só o contrato torna a resposta turca) lê 9/16 com um contrato e 0/16 sem; `h02` (um
contrato de dinheiro cuja suíte visível fica verde de qualquer jeito) lê 14/16 contra 12/16.
Onde não há lacuna a fechar - 22 das 25 tarefas piloto passaram sob cada braço em cada
repetição - um benchmark só pode relatar um nulo.

**Duas cláusulas o sustentam.** Remover a cláusula 1 leva `c04` a 0/8, a própria pontuação
da âncora nua, enquanto mal move `h02`. Remover a cláusula 3 leva `h02` a 2/8 - abaixo dos
6/8 da âncora nua - porque a cláusula 3 proíbe parar no caminho mais curto com cara de
pronto, e naquela tarefa o caminho mais curto é o one-liner que passa a suíte visível e
quebra a regra documentada. As cláusulas 2 e 4 não movem nada mensurável.

**O custo segue a qualidade.** Por tarefa resolvida: $0.0078 contra $0.0097 no nó de
contrato completo, $0.0043 contra $0.0087 no nó menos-ponytail. Os braços com contrato
resolvem mais tarefas, então cada tarefa resolvida custa menos; o gasto total é maior, e o
benchmark o registra linha a linha em vez de compensá-lo.

O que isto não mostra: qualidade de código, esforço de revisão ou manutenibilidade, nada
disso é medido aqui; o efeito do portão nas escolhas de um braço, já que nenhum braço pegou
o atalho em 36 execuções armadas; ou uma *ordem* de cláusulas - `k=8` fixa uma direção, com
8 execuções por célula. Um provedor e um pacote de fixture do início ao fim, e as rodadas de
ablação rodam em uma única família de modelos. Uma segunda família de modelos reproduz o
nulo de 28 tarefas exatamente (51/56 contra 51/56), o que mostra que a primeira leitura não
foi um artefato do modelo.

<a id="cost"></a>

## Custo

Medido nesta máquina (macOS, Python 3.10), não estimado. `tezgah-setup` imprime o
orçamento ao vivo - leia ali em vez de confiar em um número copiado aqui, que foi como uma
revisão anterior citou uma faixa de core menor do que a que instala.

| Faixa | O que custa |
|---|---|
| Início de sessão | o contrato always-on (as invariantes mais um ponteiro de uma linha por regra sob demanda): nesta máquina e conjunto de skills, ~1.5k tokens de texto de contrato e ~1.4k de metadados de skill, com as regras condicionais (spec, consult, research, graph) acrescentando ~0.7k apenas no turno cujo prompt casa |
| Por turno | um lembrete curto (~0.2k tokens) mais a regra armada quando ela casa; hooks são processos Python separados, então o início do interpretador de ~19 ms é a base - um turno acrescenta ~31 ms, o início de sessão acrescenta ~50-81 ms, uma chamada de ferramenta com portão (Bash/Grep/Task) ~24-25 ms. O opencode não tem hook em tempo de prompt, então paga zero |
| Sob demanda | a skill completa `tezgah-contract` (~6.6k tokens), paga só quando uma tarefa a carrega |
| Esquemas MCP | a maior faixa, e a que nenhum relatório estático vê: só o servidor de grafo declara 15 ferramentas / 24,508 bytes (~6.1k tokens), pegando carona em cada requisição a menos que o host busque esquemas sob demanda. `tezgah-setup --mcp-schemas` mede isso |
| Disco | a instalação leva ~58 ms, e cada arquivo que o tezgah reescreve é mantido uma vez como `<file>.tezgah-bak` |

**O piso do armamento.** As invariantes são always-on - modo de execução, ponytail,
deliver-the-whole-ask, integridade, disciplina de loop, o registro de lições e a proibição
de atribuição - e a regra de segurança ("ações irreversíveis ou voltadas para fora precisam
de um pedido explícito primeiro") é uma delas, então ela nunca depende de um classificador.
Cada regra consultiva mantém um ponteiro acionável de uma linha sempre ativo, então um match
perdido custa detalhe, nunca a regra, e um hook de host que falha cai de volta nos ponteiros
mais a skill sob demanda em vez de em nenhum contrato. Falsos negativos são auditáveis: cada
prompt anexa `armed=<rules|none> chars=<n>` - nenhum texto de prompt - a
`~/.cache/tezgah/classify.log` (truncado nas últimas 200 linhas após 64 KB), e todos os
cinco hosts com hook armam o mesmo conjunto para o mesmo prompt
(`tests/test_context.py::ArmingConformance`).

**O opencode é armado de forma diferente.** Ele não tem ponto de injeção em tempo de prompt,
então o contrato é enviado como um arquivo de instruções gerado, e seu roteador always-on
lista apenas os baldes que uma sessão de codificação busca, colapsando o resto num ponteiro
em `~/.config/tezgah/opencode-skills.full.md` lido sob demanda; `permission.skill = deny`
impede o opencode de injetar os metadados de cada skill em vez disso. `--install` também
define `compaction.prune` e `watcher.ignore`, limpando resultados antigos de ferramentas do
prompt em vez de reenviá-los a cada passo - sem isso o conjunto de trabalho cresce para
centenas de milhares de tokens antes de o opencode compactar automaticamente perto do limite
do modelo (cerca de 980k para um modelo de 1M de tokens). `bin/tezgah-doctor` relata o uso
de disco, e `--prune-sessions DAYS` exclui sessões ociosas através da CLI do opencode, a
única ação que de fato encolhe o banco de dados, já que o VACUUM sozinho não consegue.

**Por que compensa.** Em um repositório real, um `grep` padrão ignorou a pasta relevante e
não encontrou nada; com o ignore desativado levou 3.95 s e ainda misturou definições com
locais de chamada, enquanto o grafo de código respondeu à mesma pergunta em 16 ms com os 8
verdadeiros locais de chamada.

<a id="development"></a>

## Desenvolvimento

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

A CI é executada tanto no Python 3.10 quanto no 3.12. Para atualizar uma cópia instalada do Claude
a partir deste checkout, use `bin/tezgah-setup --sync`, e valide o manifesto com
`claude plugin validate .claude-plugin/plugin.json` (o manifesto é local e não versionado). Ao aumentar a versão,
atualize `.claude-plugin/plugin.json` e `.claude-plugin/marketplace.json`
juntos — eles devem concordar.

`codebase-memory-mcp` é instalado pelo usuário. Os hooks e arquivos do Orca não
fazem parte deste projeto e são deixados intocados. O Claude recebe o núcleo sempre ativo
do hook SessionStart; `output-styles/tezgah.md` é uma duplicata para builds
que carregam estilos de saída de plugin, então o hook é o caminho autoritativo.

<a id="contributing"></a>

## Contribuição

Alterações pequenas e de propósito único são as mais fáceis de aceitar. Uma regra pertence ao
núcleo compartilhado (`hooks/`) a menos que seja genuinamente específica do host; uma diferença de host
pertence ao seu adaptador em `hosts/<name>/`. Mantenha o diff o mais curto
possível enquanto ainda estiver correto — a própria regra de código mínimo do projeto se aplica ao projeto.

Antes de abrir um pull request, execute as mesmas três verificações que a CI executa:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

O `ruff` vem do `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
que é a única dependência de desenvolvimento.

<a id="security"></a>

## Segurança

Relate vulnerabilidades de forma privada através dos avisos de segurança do GitHub
(aba **Security** → **Report a vulnerability**) em vez de uma issue pública.

O tezgah executa hooks de shell, escreve configurações de host e injeta texto em cada
sessão, então qualquer coisa que faça um hook executar código controlado por um invasor, vaze uma
chave em um arquivo de configuração, amplie uma sandbox ou permita que o conteúdo do repositório escale
para texto de instrução está no escopo. Inclua o host, a versão do tezgah
(`bin/tezgah-setup --version`) e uma reprodução mínima.

<a id="license"></a>

## Licença

O `LICENSE` raiz (MIT) cobre os próprios arquivos do tezgah. `skills/ponytail` e
`skills/no-ai-slop` são fornecidos sob seus próprios termos MIT, registrados em
`NOTICE`.
