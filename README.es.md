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

<h3 align="center">Un contrato de trabajo para cada asistente de programación de IA que ejecutes.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Lo que impone</a> &bull;
  <a href="#supported-hosts">Hosts compatibles</a> &bull;
  <a href="#install">Instalación</a> &bull;
  <a href="#day-to-day">Día a día</a> &bull;
  <a href="#configuration">Configuración</a> &bull;
  <a href="#cost">Costo</a> &bull;
  <a href="#development">Desarrollo</a> &bull;
  <a href="#contributing">Contribución</a> &bull;
  <a href="#security">Seguridad</a> &bull;
  <a href="#license">Licencia</a>
</p>

<p align="center"><sub>El inglés es la fuente de la verdad; las traducciones pueden estar desactualizadas.</sub></p>

---

Un contrato de trabajo para cada asistente de programación de IA que ejecutes — Claude Code,
opencode, Codex, Cursor y el entorno dsh de DeepSeek — dentro de un conjunto de
raíces de repositorios configuradas.

Por sí solo, cada asistente tiene sus propios hábitos: uno responde en turco, otro
en inglés; uno usa grep para todo, otro consulta un grafo de código; uno dice
"hecho" sin ejecutar una prueba. Tezgah elimina esta desviación. Abre cualquier host y
obtendrás el mismo idioma, la misma disciplina y el mismo estándar de evidencia.

El diseño consta de dos capas. Las reglas residen una sola vez en un núcleo compartido; cada host obtiene
un adaptador ligero que traduce ese núcleo al formato que el host entiende.
Cambia una regla en un lugar y los cinco hosts la verán — sin necesidad de copiar el
mismo texto cinco veces.

<a id="what-it-enforces"></a>

## Lo que impone

- **Informes en turco centrados en los resultados.** Cada respuesta es en turco y comienza con
  el resultado o la decisión (BLUF), seguido de puntos ordenados por impacto. El código, los commits,
  la documentación y los prompts de los subagentes se mantienen en inglés; los nombres, los comandos de la CLI y las
  cadenas de error nunca se traducen.
- **Código mínimo (ponytail).** El cambio más perezoso que realmente funcione: YAGNI,
  luego reutilizar un helper existente, luego stdlib, luego una característica nativa de la plataforma,
  luego una dependencia instalada, luego una línea. Sin abstracciones no solicitadas.
  La validación, el manejo de errores y la seguridad nunca se simplifican ni se omiten.
- **Descubrimiento priorizando el grafo de código.** "Dónde está X", "quién llama a Y", "qué se rompe si
  Z cambia" van al grafo `codebase-memory-mcp` (`search_graph`,
  `trace_path`, `search_code`), no a grep. Grep sigue siendo adecuado para texto literal,
  configuraciones y archivos que no son de código.
- **Análisis de aplicaciones priorizando la accesibilidad.** Una aplicación web o móvil en ejecución se lee
  a través de su árbol de accesibilidad / DOM / vista nativa, no mediante una captura de pantalla por paso.
  `analyze-app` cubre un navegador (Playwright MCP), un simulador de iOS o emulador de Android
  (Mobile MCP) y diagnósticos web opcionales (Chrome DevTools MCP); una
  captura de pantalla es una acción explícita y bajo demanda para lo que el árbol no puede responder.
- **Segunda opinión externa.** Antes de una decisión no trivial o difícil de revertir,
  `~/.config/tezgah/bin/consult` consulta a modelos independientes a través de OpenRouter (o
  la API de DeepSeek con `--provider deepseek`) en paralelo, y el agente informa en qué
  estuvieron de acuerdo o en desacuerdo.
- **Investigación a través de OpenResearch.** Cuando el enrutador juzga que una tarea es de investigación — una
  revisión bibliográfica, formulación y prueba de hipótesis, ejecución de experimentos, un
  artefacto de investigación — dirige el trabajo a través de OpenResearch de alphaXiv (`orx`)
  y carga primero el manual de `orx`, en lugar de improvisar el protocolo. El descubrimiento de
  código simple se mantiene en el grafo de código. Cuando `orx` está ausente, el enrutador lo indica
  y recurre a un subagente del host.
- **Honestidad bajo verificación.** Nada se reporta como hecho, probado o arreglado
  a menos que se haya visto el resultado. Una prueba fallida se reporta como fallida con su
  error exacto, y una comprobación omitida se declara claramente.
- **Sin atribución a la IA, en ninguna parte.** Nada de lo que se persista o publique — mensajes de commit,
  merge y etiquetas, texto de PR y problemas (issues), comentarios de código, encabezados de archivos, documentación
  — puede dar crédito al asistente, modelo, proveedor o "IA". Usar una herramienta está bien;
  firmar tu trabajo con su nombre no lo está.
- **Orquestación de dos niveles.** El hilo principal decide y verifica; un modelo
  económico (`~/.config/tezgah/bin/codegen`, OpenRouter por defecto o `--provider deepseek`) redacta
  ediciones limitadas y bien especificadas en un directorio temporal. Nada llega al repositorio
  excepto a través del enrutador, y un borrador fallido recurre automáticamente al modelo principal.
- **Subagentes por repositorio.** Al inicio de la sesión, el repositorio contenedor obtiene un pequeño conjunto de
  agentes con capacidades restringidas (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) más un `tezgah-orchestrator`, renderizados
  en la superficie nativa de cada host instalado (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` más una inyección de configuración en vivo, Codex
  `.codex/agents/`) e ignorados con un bloque `.gitignore` administrado. En Claude, la
  lista de permitidos `Agent(tezgah-*)` del orquestador solo tiene efecto cuando se ejecuta como el
  hilo principal (`claude --agent tezgah-orchestrator`); como subagente, la lista se
  ignora. dsh no tiene una superficie por rol, por lo que la regla del enrutador del contrato lo cubre.

<a id="supported-hosts"></a>

## Hosts compatibles

| Host | Conectado por | Línea de estado |
|---|---|---|
| **Claude Code** | marketplace de plugins local: hooks, comandos, dos agentes de solo lectura, estilo de salida | `statusLine` nativa |
| **opencode** | plugin + instrucciones + MCP + enrutador de habilidades generado (lista de habilidades nativa denegada), auto-indexación del repositorio en el primer mensaje | plugin TUI (sin statusLine de comando) |
| **Codex** | `hooks.json` + habilidades + MCP, incluyendo una puerta `PreToolUse` | hook `systemMessage` (la lista de elementos del pie de página está cerrada) |
| **Cursor** | `hooks.json` + habilidades + MCP | `statusLine` en `cli-config.json` |
| **dsh** | puente de hooks de Claude Code + bloque de parche administrado (hooks, MCP, rutas LLM, una línea de estado Web fuera del árbol) | plugin de UI Web: `tezgah-dsh-statusline` en el encabezado de la sesión |

La puerta de Codex ejecuta Bash, `exec_command`, `apply_patch`, Edit/Write, herramientas MCP,
y llamadas a subagentes a través de la misma comprobación que los otros hosts. En Claude, la
prohibición de atribución también se impone mecánicamente: la configuración `attribution` se
vacía (`commit`, `pr`, `sessionUrl`) para que los créditos de los commits y PRs estén desactivados
desde el origen.

### Línea de estado

Cada host renderiza la misma lista de verificación de una línea desde `tezgah-status`, por lo que
no pueden desviarse. El estado es el punto clave: una marca es **verde** cuando la regla está armada
y en vigor en esta sesión, **amarilla** cuando está armada pero bajo demanda (aún no utilizada),
y **roja** cuando un interruptor de apagado (kill switch) la desactivó. `idx` informa la preparación del grafo
por separado (`✓` indexado, `↻` obsoleto, `✗` no indexado, `–` no aplicable) y
`plans N (M blk)` los planes abiertos. `tezgah-status --legend` imprime la leyenda,
`--json` proporciona los mismos segmentos para una UI, y `--no-color` (o `NO_COLOR`)
fuerza el texto sin formato. Claude Code y Cursor colorean la línea de estado nativa; la
TUI de opencode colorea su propio componente y se actualiza en el bus de eventos del host; la
UI Web de dsh colorea su componente de encabezado y se actualiza solo mientras su pestaña es
visible; Codex muestra la cadena sin formato en `systemMessage`.

dsh ejecuta los mismos archivos de hooks de Claude a través de su puente `dsh-hooks-claude-code`,
por lo que el contrato de inicio de sesión, la puerta de atribución y el empujón (nudge) de usar grep primero
se aplican allí. dsh expone una única herramienta `subagent`, por lo que la denegación del explorador de solo grep
es inerte — no hay un subagente explorador que pueda rechazar. El sandbox predeterminado
`workspace-write` de dsh confina los subprocesos de los hooks al espacio de trabajo y al
directorio temporal de la plataforma, por lo que tezgah escribe el estado de sus hooks (marcas de empujón, sello de índice) a
una alternativa con permisos de escritura allí en lugar de fallar por una escritura denegada. El
worker del índice del grafo no puede escribir en la caché de `codebase-memory-mcp` desde dentro de ese sandbox, por lo que
el lanzador `dsh` prepara el índice en la shell no confinada del usuario antes de iniciar
dsh — un repositorio nuevo se indexa exactamente igual que en los otros hosts, con el sello de HEAD. Una
sesión iniciada sin el lanzador aún obtiene un informe claro de que el
servidor MCP sin sandbox sirve el grafo y necesita `index_repository` para un repositorio
que no ha indexado, en lugar de un `EPERM` crudo. El bloque de parche
administrado también declara dos rutas LLM compatibles con OpenAI en el adaptador pi-ai que
monta la composición base: `openrouter` (`OPENROUTER_API_KEY`) y `deepseek`
(`DEEPSEEK_API_KEY`), seleccionables junto al valor predeterminado nativo `deepseek-official`.
Las claves se resuelven desde el entorno de lanzamiento o el almacén de credenciales del entorno;
ninguna clave entra en el archivo de configuración. tezgah-setup también coloca un lanzador `dsh`
en el PATH (`~/.local/bin/dsh`) que encuentra la CLI instalada bajo
`$DSH_HOME`, por lo que `dsh --profile web` funciona desde cualquier directorio.

dsh no tiene una línea de estado de comando, por lo que tezgah incluye una como plugin de UI Web:
`tezgah-dsh-statusline`. Su mitad en el host sirve la cadena `tezgah-status` para el
espacio de trabajo de la sesión a través de una ruta autenticada `/api/tezgah.status` (con
`?format=json` para la vista coloreada); su mitad en el navegador la renderiza en el
encabezado de la sesión, coloreada por estado con una leyenda al pasar el cursor/hacer clic, y se actualiza
solo mientras la pestaña es visible. `tezgah-setup`
enlaza el plugin en el perfil web y lo habilita con una fila administrada en
`profiles/web/cordis.patch.yml` (solo web, porque la mitad del host inyecta el
servicio `connection` que es solo web); un perfil que nunca ha iniciado `web` se omite
con una sugerencia en lugar de escribirse a medias. En el modo `headless`, el puente de hooks
inyecta el contrato SessionStart como su propio turno final (su `agent/session-start`
llama a `agent.inject()` de forma separada, después de que la tarea de un solo uso ya es el primer
mensaje), por lo que `dsh --profile headless "<task>"` gasta un turno extra y, para un
prompt de respuesta literal, imprime la reacción del modelo al contrato en lugar de
la respuesta de la tarea; las sesiones web interactivas no se ven afectadas.

`bin/tezgah-setup --install` también activa `orx install-skills` para Claude,
Codex, opencode y Cursor cuando `orx` está en el PATH, para que la regla de investigación tenga un
manual que cargar. Los archivos shim pertenecen a orx, por lo que tezgah solo ejecuta ese instalador
y nunca los enumera para su desinstalación. dsh no tiene un entorno orx; la regla de investigación
allí recurre a `orx skill` en la shell.

El plugin de Claude también incluye dos agentes de solo lectura. `agents/tezgah-explorer.md`
realiza el descubrimiento de código desde el grafo y devuelve evidencia `file:line`;
`agents/tezgah-reviewer.md` convierte un diff en su conjunto de impacto con
`detect_changes` y luego busca defectos reales. Ambos tienen las herramientas de escritura y comandos
deshabilitadas; su salida es consultiva.

### Análisis de aplicaciones

`analyze-app` controla una aplicación en ejecución desde su árbol de accesibilidad. El
bucle predeterminado es abrir, leer el árbol, actuar, observar la consola/red/registros y
volver a leer el árbol — una captura de pantalla es una acción explícita para lo que el árbol no puede
responder (canvas, juegos, animaciones, regresión visual a nivel de píxeles). La habilidad es
una ruta única para todos los hosts; los servidores debajo de ella son una especificación compartida en
`hooks/tezgah_apps.py`:

| Servidor | Objetivo | Conectado por |
|---|---|---|
| `playwright` (`@playwright/mcp`) | páginas web, herramientas `browser_*` | opencode, Codex, Cursor, Claude (plugin `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | Simulador de iOS / emulador de Android, herramientas `mobile_*` | igual |
| `chrome-devtools` (opcional, `--devtools`) | trazas de rendimiento web, red profunda, consola con source-maps | igual |

El navegador ejecuta un perfil **aislado** por defecto, por lo que una ejecución nunca toca tu
estado real de Chrome; analizar un flujo con sesión iniciada es una conexión deliberada
(`--cdp-endpoint` o la extensión de Playwright), no un valor predeterminado. Las capturas de pantalla,
trazas y volcados del árbol terminan en `~/.cache/tezgah/apps` (se puede anular con
`TEZGAH_ARTIFACTS`) y el agente recibe una ruta de vuelta, nunca bytes de imagen en línea.
Los servidores se ejecutan a través de `npx`, por lo que necesitan node pero ninguna instalación propia;
`tezgah-setup --install --devtools` agrega el servidor opcional de diagnósticos web.
dsh conecta los mismos dos servidores a través de su puente `dsh-mcp-client`
(`serverName` / `command` / `args` / `env`, confirmado contra el esquema de configuración publicado),
y Claude los obtiene del `.mcp.json` del plugin
(`claude plugin details tezgah` enumera 2 servidores MCP y ambos se conectan).
`mobile-mcp` es la mitad con mayor fricción: macOS puede solicitar permisos de Accesibilidad /
Grabación de pantalla y el árbol de vistas puede caerse bajo carga, por lo que la habilidad
reintenta el árbol antes de recurrir a una captura de pantalla.

CI ejecuta un handshake determinista para ambos servidores (sin navegador, sin dispositivo):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. Dos pruebas de humo (smokes) locales
opcionales van más allá: `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` inicia
Playwright MCP, navega y lee la instantánea sin captura de pantalla;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` inicia Mobile MCP, verifica
las herramientas del árbol de vistas y enumera un dispositivo. Imprimen `SKIP: ...` cuando falta node, una
compilación del navegador o un dispositivo.

<a id="install"></a>

## Instalación

Requiere Python 3.8+. Se necesitan node + npm para el host dsh y, con `pnpm`,
para su línea de estado web. Las integraciones opcionales se degradan con gracia:
`codebase-memory-mcp` en el PATH impulsa el grafo; una clave de modelo impulsa `consult`
y `codegen` — OpenRouter por defecto (`OPENROUTER_API_KEY` o
`~/.config/openrouter/key`), o la API de DeepSeek con `--provider deepseek`
(`DEEPSEEK_API_KEY` o `~/.config/deepseek/key`); y `orx` de OpenResearch en el PATH
le da a la regla de investigación algo que controlar. Cuando falta la clave del proveedor
elegido, tezgah lo indica en lugar de fingir.

Clona, luego arma cada host detectado en una sola pasada:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

`--install` también instala las herramientas opcionales que faltan ejecutando el propio
instalador de cada proveedor **a través de la red**: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(su perfil de inicio a través de `npx`) y `pnpm` cuando dsh lo necesita (vía `npm`) —
`curl ... | sh` incluido. Ninguno necesita sudo; la ejecución se registra en
`~/.config/tezgah/install.log`. Previsualiza con `--dry-run`, omítelo con
`--no-deps` (útil en CI), o instala las herramientas solas con `--deps`. Las herramientas terminan
en `~/.local/bin` o `~/.cargo/bin`, por lo que puede ser necesaria una nueva shell antes de que
estén en el PATH; las propias comprobaciones de tezgah buscan en esos directorios de todos modos, por lo que una shell no interactiva
aún las reporta como presentes.

Si ya está presente una configuración predecesora, impórtala primero — se mueve a un lado,
no se elimina:

```bash
bin/tezgah-setup --adopt
```

Claude Code se instala a través de su propio canal de plugins:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Limita la instalación explícitamente cuando sea necesario:

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Día a día

Nada que ejecutar: las reglas se cargan cuando se inicia un host. Vale la pena conocer algunos comandos:

| Comando | Propósito |
|---|---|
| `bin/tezgah-setup` | Informar qué está armado, por host |
| `bin/tezgah-status [PATH]` | Mostrar si las reglas están activas en ese repositorio |
| `bin/tezgah-setup --status [PATH]` | Imprimir la lista de verificación de lo armado/usado |
| `bin/tezgah-setup --deps [--dry-run]` | Instalar herramientas opcionales faltantes (orx, cursor-agent, dsh) |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Informar el uso de disco del entorno; `--clean` elimina registros de índice antiguos y hace vacuum a la BD de opencode; `--prune-sessions` elimina sesiones inactivas (la única acción que realmente reduce la BD) |
| `/plan-add` | Convertir una parte del trabajo en un plan rastreado |
| `/plan-status` | Resumir los planes abiertos y elegir el siguiente |
| `/plan-sync` | Cerrar los planes terminados |
| `bin/tezgah-setup --version` | Imprimir la versión del plugin |
| `bin/tezgah-setup --uninstall` | Eliminar solo los enlaces simbólicos de tezgah, las entradas de hooks del host y el bloque administrado de dsh |

<a id="configuration"></a>

## Configuración

Tezgah se arma solo bajo sus raíces configuradas; en cualquier otro lugar permanece en silencio.

- Raíz predeterminada: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (lista separada por separadores de ruta) anula el archivo para casos únicos y CI.

Los interruptores de apagado (kill switches) residen en `~/.config/tezgah/`. Cada uno elimina su regla del
texto inyectado en la sesión, por lo que la regla realmente se detiene:

| Interruptor | Desactiva |
|---|---|
| `exec-mode.off` | informes en turco centrados en los resultados |
| `ponytail-auto.off` | la regla de código mínimo |
| `spec-off` | la regla de especificación antes de construir |
| `consult-off` | la regla de segunda opinión externa |
| `research-off` | el enrutamiento de tareas de investigación a OpenResearch |
| `orchestrate-off` | la delegación de subagentes (agrega una línea de no delegar) |
| `reminder-off` | el texto de recordatorio por turno |
| `pretooluse-off` | la puerta PreToolUse en sí (atribución, explorador, empujón de grep) |

Por repositorio, `.no-ponytail`, `.no-cbm` y `.no-lessons` desactivan la regla de código mínimo,
la regla del grafo de código (y su auto-indexación) y el registro de lecciones
respectivamente.

Cuando el usuario señala un error, el agente añade una lección de una línea a `.tezgah/lessons.md`
del repositorio; las líneas más recientes se inyectan al inicio de la sesión para que
el mismo error no pueda repetirse silenciosamente.

<a id="cost"></a>

## Costo

Medido en esta máquina (macOS, Python 3.10), no estimado:

- **Contexto.** Un inicio de sesión inyecta ~5.4 KB (~1.3k tokens) de texto de contrato.
  En Codex, un recordatorio de 480 bytes acompaña cada turno; Claude y los otros hosts
  no tienen un hook por turno, por lo que su costo por turno es cero. La habilidad completa `tezgah-contract`
  (~25k caracteres) se paga solo cuando una tarea la carga. En opencode, el contrato se envía como un
  archivo de instrucciones de ~5.8 KB. De lo contrario, opencode
  inyectaría texto de nombre/descripción/ubicación de habilidades en el prompt del sistema de cada sesión;
  tezgah deniega esa lista (`permission.skill = deny`) y en su lugar envía
  un enrutador de habilidades generado, por lo que una habilidad se encuentra leyendo su
  ruta `SKILL.md` desde el enrutador.
- **Latencia.** Los hooks son procesos de Python separados, por lo que el inicio del intérprete de ~19 ms domina.
  Además de eso, el inicio de sesión agrega ~25 ms, una llamada a herramienta controlada
  (Bash/Grep/Task) agrega ~9 ms, y el segmento Stop de Codex agrega ~15 ms por turno.
- **Disco.** La instalación toma ~58 ms y cada archivo que tezgah reescribe se conserva
  una vez como `<file>.tezgah-bak`.

La recompensa se nota en las preguntas del usuario. En un repositorio real, un `grep` predeterminado
ignoró la carpeta relevante y no encontró nada; con la opción de ignorar deshabilitada tomó
3.95 s y aún mezclaba definiciones con sitios de llamada. El grafo de código respondió la
misma pregunta en 16 ms, enumerando solo los 8 verdaderos sitios de llamada.

opencode también está armado para la higiene del contexto en sesiones largas: `tezgah-setup --install`
establece `compaction.prune` para que los resultados antiguos de las herramientas se borren del prompt
en lugar de reenviarse en cada paso, y una lista `watcher.ignore` mantiene al observador de archivos
fuera de `.git`, `node_modules` y directorios de compilación. Ambos se fusionan — un valor explícito del usuario
gana. Esto importa porque opencode solo auto-compacta cerca del límite de contexto del modelo
(para un modelo de 1M de tokens, alrededor de 980k), por lo que sin la poda, el conjunto de trabajo
crece a cientos de miles de tokens. `bin/tezgah-doctor` informa la huella de disco resultante;
`--prune-sessions DAYS` elimina sesiones inactivas a través de la CLI de opencode, que es la única acción
que realmente reduce la base de datos — VACUUM por sí solo no puede, ya que todas sus páginas están activas.

<a id="development"></a>

## Desarrollo

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI se ejecuta tanto en Python 3.10 como en 3.12. Para actualizar una copia instalada de Claude desde este checkout, usa `bin/tezgah-setup --sync`, y valida el manifiesto con `claude plugin validate .claude-plugin/plugin.json`. Al incrementar la versión, actualiza `.claude-plugin/plugin.json` y `.claude-plugin/marketplace.json` juntos — deben coincidir.

`codebase-memory-mcp` es instalado por el usuario. Los hooks y archivos de Orca no son parte de este proyecto y se dejan intactos. Claude recibe el núcleo siempre activo desde el hook SessionStart; `output-styles/tezgah.md` es un duplicado para las compilaciones que cargan estilos de salida de plugins, por lo que el hook es la ruta autoritativa.

<a id="contributing"></a>

## Contribución

Los cambios pequeños y de un solo propósito son los más fáciles de aceptar. Una regla pertenece al
núcleo compartido (`hooks/`) a menos que sea genuinamente específica del host; una diferencia de host
pertenece a su adaptador bajo `hosts/<name>/`. Mantén el diff tan corto como pueda
ser sin dejar de ser correcto — la propia regla de código mínimo del proyecto se aplica al proyecto.

Antes de abrir un pull request, ejecuta las mismas tres comprobaciones que ejecuta CI:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` proviene de `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
que es la única dependencia de desarrollo.

<a id="security"></a>

## Seguridad

Reporta las vulnerabilidades de forma privada a través de los avisos de seguridad de GitHub
(pestaña **Security** → **Report a vulnerability**) en lugar de un problema (issue) público.

tezgah ejecuta hooks de shell, escribe la configuración del host e inyecta texto en cada
sesión, por lo que cualquier cosa que haga que un hook ejecute código controlado por un atacante, filtre
una clave en un archivo de configuración, amplíe un sandbox o permita que el contenido del repositorio escale
a texto de instrucciones está dentro del alcance. Incluye el host, la versión de tezgah
(`bin/tezgah-setup --version`) y una reproducción mínima.

<a id="license"></a>

## Licencia

El archivo `LICENSE` (MIT) en la raíz cubre los propios archivos de tezgah. `skills/ponytail` y
`skills/no-ai-slop` se incluyen (vendored) bajo sus propios términos MIT, registrados en
`NOTICE`.
