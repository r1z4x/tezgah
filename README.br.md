<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh.md">简体中文</a> |
  <a href="README.zht.md">繁體中文</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.it.md">Italiano</a> |
  <a href="README.da.md">Dansk</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pl.md">Polski</a> |
  <a href="README.ru.md">Русский</a> |
  <a href="README.bs.md">Bosanski</a> |
  <a href="README.no.md">Norsk</a> |
  <a href="README.br.md">Português (Brasil)</a> |
  <a href="README.th.md">ไทย</a> |
  <a href="README.tr.md">Türkçe</a> |
  <a href="README.uk.md">Українська</a> |
  <a href="README.bn.md">বাংলা</a>
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

| Host | Conectado por | Linha de status |
|---|---|---|
| **Claude Code** | marketplace de plugins local: hooks, comandos, dois agentes somente leitura, estilo de saída | `statusLine` nativa |
| **opencode** | plugin + instruções + MCP + roteador de skills gerado (lista de skills nativa negada), auto-indexação do repositório na primeira mensagem | plugin TUI (sem statusLine de comando) |
| **Codex** | `hooks.json` + skills + MCP, incluindo um portão `PreToolUse` | hook `systemMessage` (lista de itens do rodapé é fechada) |
| **Cursor** | `hooks.json` + skills + MCP | `statusLine` em `cli-config.json` |
| **dsh** | ponte de hooks do Claude Code + bloco de patch gerenciado (hooks, MCP, rotas de LLM, uma linha de status Web fora da árvore) | Plugin de UI Web: `tezgah-dsh-statusline` no cabeçalho da sessão |

O portão do Codex executa Bash, `exec_command`, `apply_patch`, Edit/Write, ferramentas MCP,
e chamadas de subagentes através da mesma verificação que os outros hosts. No Claude, a
proibição de atribuição também é imposta mecanicamente: a configuração `attribution` é
esvaziada (`commit`, `pr`, `sessionUrl`) para que os créditos de commit e PR sejam desativados na origem.

### Linha de status

Todo host renderiza a mesma checklist de uma linha do `tezgah-status`, para que não possam divergir.
O estado é o ponto principal: uma marca é **verde** quando a regra está armada
e em vigor nesta sessão, **amarela** quando está armada, mas sob demanda (ainda não usada),
e **vermelha** quando um kill switch a desativou. `idx` relata a prontidão do grafo
separadamente (`✓` indexado, `↻` obsoleto, `✗` não indexado, `–` não aplicável) e
`plans N (M blk)` os planos abertos. `tezgah-status --legend` imprime a legenda,
`--json` fornece os mesmos segmentos para uma UI, e `--no-color` (ou `NO_COLOR`)
força texto simples. Claude Code e Cursor colorem a linha de status nativa; a
TUI do opencode colore seu próprio componente e atualiza no barramento de eventos do host; a
UI Web do dsh colore seu componente de cabeçalho e atualiza apenas enquanto sua aba está
visível; o Codex mostra a string simples em `systemMessage`.

O dsh executa os mesmos arquivos de hook do Claude através de sua ponte `dsh-hooks-claude-code`,
então o contrato de início de sessão, o portão de atribuição e o lembrete de primeiro-grep
se aplicam lá. O dsh expõe uma única ferramenta `subagent`, então a negação do grep-only-explorer
é inerte — não há subagente explorador para ele recusar. A sandbox padrão
`workspace-write` do dsh confina os subprocessos de hook ao workspace e ao
diretório temporário da plataforma, então o tezgah escreve seu estado de hook (marcas de lembrete, carimbo de índice) em
um fallback gravável lá, em vez de falhar em uma gravação negada. O worker de índice do grafo
não pode gravar o cache do `codebase-memory-mcp` de dentro dessa sandbox, então
o launcher do `dsh` aquece o índice no shell não confinado do usuário antes de iniciar
o dsh — um novo repositório é indexado exatamente como nos outros hosts, com carimbo do HEAD. Uma
sessão iniciada sem o launcher ainda recebe um relatório claro de que o
servidor MCP sem sandbox serve o grafo e precisa de `index_repository` para um repositório
que ele não indexou, em vez de um `EPERM` bruto. O bloco de patch
gerenciado também declara duas rotas de LLM compatíveis com OpenAI no adaptador pi-ai
que a composição base monta: `openrouter` (`OPENROUTER_API_KEY`) e `deepseek`
(`DEEPSEEK_API_KEY`), selecionáveis ao lado do padrão nativo `deepseek-official`.
As chaves são resolvidas a partir do ambiente de inicialização ou do armazenamento de credenciais do harness;
nenhuma das chaves entra no arquivo de configuração. O tezgah-setup também coloca um launcher do `dsh`
no PATH (`~/.local/bin/dsh`) que encontra a CLI instalada em
`$DSH_HOME`, para que `dsh --profile web` funcione a partir de qualquer diretório.

O dsh não tem linha de status de comando, então o tezgah envia uma como um plugin de UI Web:
`tezgah-dsh-statusline`. Sua metade host serve a string `tezgah-status` para o
workspace da sessão através de uma rota autenticada `/api/tezgah.status` (com
`?format=json` para a visualização colorida); sua metade navegador a renderiza no
cabeçalho da sessão, colorida por estado com uma legenda ao passar o mouse/clicar, e atualiza apenas enquanto a
aba está visível. O `tezgah-setup`
vincula o plugin ao perfil web e o habilita com uma linha gerenciada em
`profiles/web/cordis.patch.yml` (apenas web, porque a metade host injeta o
serviço `connection` que é apenas web); um perfil que nunca iniciou `web` é ignorado
com uma dica em vez de ser escrito pela metade. No modo `headless`, a ponte de hooks
injeta o contrato SessionStart como seu próprio turno final (seu `agent/session-start`
chama `agent.inject()` de forma desanexada, depois que a tarefa de disparo único já é a primeira mensagem),
então `dsh --profile headless "<task>"` gasta um turno extra e, para um
prompt de resposta literal, imprime a reação do modelo ao contrato em vez da
resposta da tarefa; sessões web interativas não são afetadas.

`bin/tezgah-setup --install` também aciona `orx install-skills` para Claude,
Codex, opencode e Cursor quando o `orx` está no PATH, para que a regra de pesquisa tenha um
manual para carregar. Os arquivos shim pertencem ao orx, então o tezgah apenas executa esse instalador
e nunca os lista para desinstalação. O dsh não tem harness orx; a regra de pesquisa
lá recorre a `orx skill` no shell.

O plugin do Claude também envia dois agentes somente leitura. `agents/tezgah-explorer.md`
faz a descoberta de código a partir do grafo e retorna evidências `arquivo:linha`;
`agents/tezgah-reviewer.md` transforma um diff em seu conjunto de impacto com
`detect_changes` e então procura por defeitos reais. Ambos têm ferramentas de gravação e comando
desativadas; a saída deles é consultiva.

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

`--install` também instala as ferramentas opcionais que estão ausentes executando o próprio instalador
de cada fornecedor **pela rede**: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(seu perfil home através do `npx`), e `pnpm` quando o dsh precisa dele (via `npm`) —
`curl ... | sh` incluído. Nenhum precisa de sudo; a execução é registrada em
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

O Claude Code é instalado através de seu próprio canal de plugins:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
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
| `bin/tezgah-setup` | Relatar o que está armado, por host |
| `bin/tezgah-status [PATH]` | Mostrar se as regras estão ativas naquele repositório |
| `bin/tezgah-setup --status [PATH]` | Imprimir a checklist armada/usada |
| `bin/tezgah-setup --deps [--dry-run]` | Instalar ferramentas opcionais ausentes (orx, cursor-agent, dsh) |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Relatar o uso de disco do harness; `--clean` exclui logs de índice antigos e faz vacuum no BD do opencode; `--prune-sessions` exclui sessões ociosas (a única ação que realmente reduz o BD) |
| `/plan-add` | Transformar um trabalho em um plano rastreado |
| `/plan-status` | Resumir planos abertos e escolher o próximo |
| `/plan-sync` | Fechar planos concluídos |
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

<a id="cost"></a>

## Custo

Medido nesta máquina (macOS, Python 3.10), não estimado:

- **Contexto.** O início de uma sessão injeta ~4,8 KB (~1,2k tokens) de texto de contrato.
  No Codex, um lembrete de 480 bytes acompanha cada turno; Claude e os outros hosts
  não têm hook por turno, então o custo por turno deles é zero. A skill completa `tezgah-contract`
  (~19,9k caracteres) é paga apenas quando uma tarefa a carrega. No opencode,
  o contrato é enviado como um arquivo de instruções de ~5,5 KB. Caso contrário, o opencode
  injetaria ~53 KB de texto de nome/descrição/localização de skill no
  prompt de sistema de cada sessão; o tezgah nega essa lista (`permission.skill = deny`) e
  envia um roteador de skills gerado de ~16 KB em seu lugar, para que uma skill seja
  encontrada lendo seu caminho `SKILL.md` a partir do roteador.
- **Latência.** Hooks são processos Python separados, então o início do interpretador de ~19 ms
  domina. Além disso, o início da sessão adiciona ~25 ms, uma chamada de ferramenta com portão
  (Bash/Grep/Task) adiciona ~9 ms, e o segmento Stop do Codex adiciona ~15 ms por turno.
- **Disco.** A instalação leva ~58 ms e cada arquivo que o tezgah reescreve é mantido
  uma vez como `<file>.tezgah-bak`.

A recompensa aparece nas perguntas de quem chama. Em um repositório real, um `grep` padrão
ignorou a pasta relevante e não encontrou nada; com a opção de ignorar desativada, levou
3,95 s e ainda misturou definições com locais de chamada. O grafo de código respondeu à
mesma pergunta em 16 ms, listando apenas os 8 verdadeiros locais de chamada.

O opencode também está armado para a higiene de contexto de sessões longas: `tezgah-setup --install`
define `compaction.prune` para que resultados antigos de ferramentas sejam limpos do prompt
em vez de serem reenviados a cada passo, e uma lista `watcher.ignore` mantém o observador de arquivos
fora de `.git`, `node_modules` e diretórios de build. Ambos se mesclam — um valor explícito do usuário
vence. Isso é importante porque o opencode só compacta automaticamente perto do limite de contexto do modelo
(para um modelo de 1M de tokens, cerca de 980k), então sem a poda, o conjunto de trabalho
cresce para centenas de milhares de tokens. `bin/tezgah-doctor` relata o
uso de disco resultante; `--prune-sessions DAYS` exclui sessões ociosas através da
CLI do opencode, que é a única ação que realmente reduz o banco de dados — o
VACUUM sozinho não consegue, já que suas páginas estão todas ativas.

<a id="development"></a>

## Desenvolvimento

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

A CI é executada tanto no Python 3.10 quanto no 3.12. Para atualizar uma cópia instalada do Claude
a partir deste checkout, use `bin/tezgah-setup --sync`, e valide o manifesto com
`claude plugin validate .claude-plugin/plugin.json`. Ao aumentar a versão,
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
