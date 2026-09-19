<p align="center">
  <a href="README.md">English</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.tr.md">Türkçe</a>
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
  <a href="#benchmark">Benchmark</a> &bull;
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
  La validación, el manejo de errores y la seguridad nunca se simplifican ni
  se omiten. El nivel de intensidad es un interruptor real -
  `tezgah-pony lite|full|ultra`, o `/tezgah:ponytail` en Claude - y un nivel
  no predeterminado viaja en el recordatorio por turno.
- **Forma de salida accionable (i-have-adhd).** La respuesta o la siguiente
  acción está en la primera línea; el trabajo de varios pasos es una lista
  numerada que reafirma su posición en una línea mientras se ejecuta; los
  temas tangenciales esperan a que termine el asunto en curso; los errores se
  leen como ubicación, causa, solución; una lista muestra como máximo cinco
  elementos clasificados y el resto se guarda en reserva; una estimación va en
  unidades concretas y se marca como estimación. El interruptor es
  `tezgah-adhd off|on` (o `/tezgah:adhd` en Claude; un repositorio puede
  desactivarla con `.no-adhd`). Incluido (vendored) y adaptado de
  `i-have-adhd` (MIT).
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
  la API de DeepSeek con `--provider deepseek`, o Inception Labs con
  `--provider inception`) en paralelo, y el agente informa en qué
  estuvieron de acuerdo o en desacuerdo.
- **Investigación a través de OpenResearch.** Cuando el enrutador juzga que una tarea es de investigación — una
  revisión bibliográfica, formulación y prueba de hipótesis, ejecución de experimentos, un
  artefacto de investigación — dirige el trabajo a través de OpenResearch de alphaXiv (`orx`)
  y carga primero el manual de `orx`, en lugar de improvisar el protocolo. El descubrimiento de
  código simple se mantiene en el grafo de código. Cuando `orx` está ausente, el enrutador lo indica
  y recurre a un subagente del host.
  El conocimiento de dominio que necesita un experimento viaja con él: la biblioteca
  `AI-research-SKILLs` integrada (98 skills, 23 categorías, MIT) llega como skill
  `ai-research` y se lee entrada por entrada desde su índice por etapas.
- **Honestidad bajo verificación.** Nada se reporta como hecho, probado o arreglado
  a menos que se haya visto el resultado. Una prueba fallida se reporta como fallida con su
  error exacto, y una comprobación omitida se declara claramente.
- **Sin atribución a la IA, en ninguna parte.** Nada de lo que se persista o publique — mensajes de commit,
  merge y etiquetas, texto de PR y problemas (issues), comentarios de código, encabezados de archivos, documentación
  — puede dar crédito al asistente, modelo, proveedor o "IA". Usar una herramienta está bien;
  firmar tu trabajo con su nombre no lo está.
- **Orquestación de dos niveles.** El hilo principal decide y verifica; un modelo
  económico (`~/.config/tezgah/bin/codegen`, OpenRouter por defecto, `--provider deepseek`
  o `--provider inception`) redacta
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

| Host | Conectado por |
|---|---|
| **omp** (oh-my-pi) — primario | `~/.omp/agent`: bloque always-on administrado `RULES.md`, habilidades, subagentes generados, `mcp.json`, y una extensión (`hooks/pre/tezgah-hook.ts`) que arma las reglas por prompt, pasa las herramientas por la puerta, registra evidencia y ejecuta la regla Stop; el cableado lo verifica `tezgah-setup` |
| **Claude Code** | marketplace de plugins local: hooks, comandos, dos agentes de solo lectura, estilo de salida |
| **opencode** | plugin + instrucciones + MCP + enrutador de habilidades generado (lista de habilidades nativa denegada), auto-indexación del repositorio en el primer mensaje |
| **Codex** | `hooks.json` + habilidades + MCP, incluyendo una puerta `PreToolUse` |
| **Cursor** | `hooks.json` + habilidades + MCP |
| **dsh** | puente de hooks de Claude Code + bloque de parche administrado (hooks, MCP, rutas LLM, una línea de estado Web fuera del árbol) |

La puerta de Codex ejecuta Bash, `exec_command`, `apply_patch`, Edit/Write, herramientas MCP,
y llamadas a subagentes a través de la misma comprobación que los otros hosts. En Claude, la
prohibición de atribución también se impone mecánicamente: la configuración `attribution` se
vacía (`commit`, `pr`, `sessionUrl`) para que los créditos de los commits y PRs estén desactivados
desde el origen.

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
`~/.config/openrouter/key`), la API de DeepSeek con `--provider deepseek`
(`DEEPSEEK_API_KEY` o `~/.config/deepseek/key`), o Inception Labs con
`--provider inception` (`INCEPTION_API_KEY` o `~/.config/inception/key`); y `orx`
de OpenResearch en el PATH
le da a la regla de investigación algo que controlar. Cuando falta la clave del proveedor
elegido, tezgah lo indica en lugar de fingir.

Clona, luego arma cada host detectado en una sola pasada:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

En una terminal, ese comando sin argumentos es el asistente de instalación: pregunta qué
hosts armar, los directorios raíz, si instalar las herramientas opcionales faltantes, y si
cablear el DevTools MCP opcional, imprime el plan y solo escribe tras un sí. Las flags son
los valores por defecto del asistente, así que `--wizard --hosts omp` pregunta solo el
resto. Una ejecución por tubería, agente o CI nunca recibe prompt — imprime el informe,
exactamente como antes.

`--install` también instala las herramientas opcionales que faltan ejecutando el propio
instalador de cada proveedor **a través de la red**: `orx` (`openresearch.sh/install.sh`),
`cursor-agent` (`cursor.com/install`), `dsh` (su perfil de inicio a través de `npx`) y
`pnpm` cuando dsh lo necesita (vía `npm`) —
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

Claude Code se arma con el mismo script: el manifiesto del plugin es un archivo local, no versionado:

```bash
bin/tezgah-setup --install --hosts claude
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
| `bin/tezgah-setup` | En una terminal: el asistente de instalación; en una tubería o en CI: informa qué está armado, por host |
| `bin/tezgah-setup --wizard` | Fuerza el asistente de instalación en cualquier lugar; `--report` fuerza el informe |
| `bin/tezgah-status [PATH]` | Mostrar si las reglas están activas en ese repositorio |
| `bin/tezgah-setup --status [PATH]` | Imprimir la lista de verificación de lo armado/usado |
| `bin/tezgah-setup --deps [--dry-run]` | Instalar herramientas opcionales faltantes (orx, cursor-agent, dsh) |
| `bin/tezgah-research init\|check\|status\|claim` | Crea y comprueba una línea de investigación: estado, hallazgos, afirmaciones y la regla protocolo-antes-de-resultados |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Informar el uso de disco del entorno; `--clean` elimina registros de índice antiguos y hace vacuum a la BD de opencode; `--prune-sessions` elimina sesiones inactivas (la única acción que realmente reduce la BD) |
| `/tezgah:plan-add` | Convertir una parte del trabajo en un plan rastreado |
| `/tezgah:plan-status` | Resumir los planes abiertos y elegir el siguiente |
| `/tezgah:plan-sync` | Cerrar los planes terminados |
| `bin/tezgah-setup --version` | Imprimir la versión del plugin |
| `bin/tezgah-setup --uninstall` | Eliminar solo los enlaces simbólicos de tezgah, las entradas de hooks del host y el bloque administrado de dsh |

La línea de estado marca cada regla con su estado primero: una marca de
verificación significa armada y en vigor en esta sesión (o always-on), un
círculo significa armada pero bajo demanda - aún no usada en esta sesión - y
una cruz significa desactivada por un interruptor de apagado o una marca
`.no-*`. `pony` y `adhd` se leen como círculo hasta que la sesión haya leído
realmente el texto completo de esa habilidad, y como marca de verificación
después; en Claude, opencode y omp esa lectura es observable, mientras que en
codex, cursor y dsh no lo es a un coste aceptable, así que allí esas dos
marcas se muestran atenuadas y sin glifo: la línea no afirma nada en lugar de
declarar que la habilidad nunca se abrió. Un interruptor de apagado sigue
mostrándose en rojo en todas partes.

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
| `adhd-off` | la forma de salida accionable (i-have-adhd) |
| `spec-off` | la regla de especificación antes de construir |
| `consult-off` | la regla de segunda opinión externa |
| `research-off` | el enrutamiento de tareas de investigación a OpenResearch |
| `orchestrate-off` | la delegación de subagentes (agrega una línea de no delegar) |
| `reminder-off` | el texto de recordatorio por turno |
| `pretooluse-off` | la puerta PreToolUse en sí (atribución, explorador, empujón de grep) |

Por repositorio, `.no-ponytail`, `.no-adhd`, `.no-cbm` y `.no-lessons`
desactivan la regla de código mínimo, la forma de salida accionable, la regla
del grafo de código (y su auto-indexación) y el registro de lecciones
respectivamente.

Cuando el usuario señala un error, el agente añade una lección de una línea a `.tezgah/lessons.md`
del repositorio; las líneas más recientes se inyectan al inicio de la sesión para que
el mismo error no pueda repetirse silenciosamente.

<a id="benchmark"></a>

## Benchmark

¿Mejora este contrato el trabajo, o solo parece que debería? Eso se mide, no se afirma:
verificaciones ocultas que el agente nunca ve, costo a partir del propio registro de uso del
host, y ediciones colaterales puntuadas como fallos. El instrumento - los brazos, el
prerregistro y `bench.py` - vive en la rama `benchmarks/lab`, así que esta rama lleva los
resultados y no el laboratorio; el estudio completo, con los ids de ejecución, es el
proyecto OpenResearch `tezgah-harness-research`. Cada cifra de abajo es un registro de
ejecución.

| Bloque | Ejecuciones | Qué resolvió |
|---|---|---|
| dos hosts, 28 tareas, k=3 | 336 | `omp+tezgah` 0.95 y `opencode+tezgah` 0.96 tienen intervalos superpuestos y el mismo costo por tarea resuelta; en los brazos desnudos omp es más barato ($0.0047 contra $0.0074 CPS), así que el caballo de batalla diario es omp sin costo en calidad |
| familia difícil, 5 tareas, k=5, dos familias de modelos | 200 | agrupados, tres de los cuatro brazos llegan a 40/50: ningún efecto de harness a ese tamaño, y la única señal que produjo el primer modelo se invirtió en el segundo |
| familia de la puerta, puerta armada | 36 | ningún brazo tomó la ruta del atajo; el mecanismo de la puerta se verifica directamente (una edición de skip se rechaza), su efecto sobre el trabajo aún no se mide |
| ablación de cláusulas, las dos reglas que separan, k=8 | 160 | los brazos con contrato pasan 23/32 (0.72) contra 12/32 (0.38) del ancla desnuda |


**Ayuda exactamente donde el valor por defecto del modelo está equivocado.** `c04` (un
prompt en inglés donde solo el contrato hace que la respuesta sea turca) lee 9/16 con un
contrato y 0/16 sin uno; `h02` (un contrato de dinero cuya suite visible queda verde de
cualquier forma) lee 14/16 contra 12/16. Donde no hay brecha que cerrar - 22 de las 25
tareas piloto pasaron bajo cada brazo en cada repetición - un benchmark solo puede reportar
un nulo.

**Dos cláusulas lo sostienen.** Quitar la cláusula 1 lleva `c04` a 0/8, la propia puntuación
del ancla desnuda, mientras apenas mueve `h02`. Quitar la cláusula 3 lleva `h02` a 2/8 - por
debajo del 6/8 del ancla desnuda - porque la cláusula 3 prohíbe detenerse en el camino más
corto que parece terminado, y en esa tarea el camino más corto es el one-liner que pasa la
suite visible mientras rompe la regla documentada. Las cláusulas 2 y 4 no mueven nada
medible.

**El costo sigue a la calidad.** Por tarea resuelta: $0.0078 contra $0.0097 en el nodo de
contrato completo, $0.0043 contra $0.0087 en el nodo menos-ponytail. Los brazos con contrato
resuelven más tareas, así que cada tarea resuelta cuesta menos; el gasto total es mayor, y
el benchmark lo registra fila por fila en vez de compensarlo.

Lo que esto no muestra: calidad del código, esfuerzo de revisión o mantenibilidad, nada de
lo cual se mide aquí; el efecto de la puerta en las decisiones de un brazo, ya que ningún
brazo recurrió al atajo en 36 ejecuciones armadas; ni un *orden* de cláusulas - `k=8` fija
una dirección, con 8 ejecuciones por celda. Un proveedor y un paquete de fixture de
principio a fin, y las rondas de ablación corren en una sola familia de modelos. Una segunda
familia de modelos reproduce el nulo de 28 tareas exactamente (51/56 contra 51/56), que es
lo que muestra que la primera lectura no fue un artefacto del modelo.

<a id="cost"></a>

## Costo

Medido en esta máquina (macOS, Python 3.10), no estimado. `tezgah-setup` imprime el
presupuesto en vivo - léalo allí en lugar de confiar en una cifra copiada aquí, que es
como una revisión anterior llegó a citar una banda de núcleo menor que la que instala.

| Banda | Qué cuesta |
|---|---|
| Inicio de sesión | el contrato always-on (las invariantes más un puntero de una línea por regla bajo demanda): en esta máquina y conjunto de habilidades, ~1.5k tokens de texto de contrato y ~1.4k de metadatos de habilidad, con las reglas condicionales (spec, consult, research, graph) añadiendo ~0.7k solo en el turno cuyo prompt coincide |
| Por turno | un recordatorio corto (~0.2k tokens) más la regla armada cuando coincide; los hooks son procesos Python separados, así que el arranque del intérprete de ~19 ms es la base - un turno añade ~31 ms, el inicio de sesión añade ~50-81 ms, una llamada de herramienta con puerta (Bash/Grep/Task) ~24-25 ms. opencode no tiene hook en tiempo de prompt, así que paga cero |
| Bajo demanda | la habilidad completa `tezgah-contract` (~6.6k tokens), pagada solo cuando una tarea la carga |
| Esquemas MCP | la banda más grande, y la que ningún informe estático ve: solo el servidor de grafo declara 15 herramientas / 24,508 bytes (~6.1k tokens), viajando en cada petición salvo que el host obtenga los esquemas bajo demanda. `tezgah-setup --mcp-schemas` lo mide |
| Disco | la instalación tarda ~58 ms, y cada archivo que tezgah reescribe se conserva una vez como `<file>.tezgah-bak` |

**El suelo del armado.** Las invariantes son always-on - modo de ejecución, ponytail,
deliver-the-whole-ask, integridad, disciplina de bucle, el registro de lecciones y la
prohibición de atribución - y la regla de seguridad ("las acciones irreversibles o de cara
al exterior necesitan una petición explícita primero") es una de ellas, así que nunca
depende de un clasificador. Cada regla consultiva mantiene un puntero accionable de una
línea siempre activo, así que un match perdido cuesta detalle, nunca la regla, y un hook de
host que falla recae en los punteros más la habilidad bajo demanda en vez de en ningún
contrato. Los falsos negativos son auditables: cada prompt añade `armed=<rules|none>
chars=<n>` - sin texto de prompt - a `~/.cache/tezgah/classify.log` (truncado a las últimas
200 líneas tras 64 KB), y los cinco hosts con hook arman el mismo conjunto para el mismo
prompt (`tests/test_context.py::ArmingConformance`).

**opencode se arma de forma distinta.** No tiene punto de inyección en tiempo de prompt, así
que el contrato se envía como un archivo de instrucciones generado, y su enrutador always-on
lista solo los grupos que una sesión de programación busca, colapsando el resto en un
puntero a `~/.config/tezgah/opencode-skills.full.md` leído bajo demanda; `permission.skill =
deny` impide que opencode inyecte los metadatos de cada habilidad en su lugar. `--install`
también define `compaction.prune` y `watcher.ignore`, limpiando resultados antiguos de
herramientas del prompt en vez de reenviarlos a cada paso - sin eso el conjunto de trabajo
crece a cientos de miles de tokens antes de que opencode compacte automáticamente cerca del
límite del modelo (unos 980k para un modelo de 1M de tokens). `bin/tezgah-doctor` informa el
uso de disco, y `--prune-sessions DAYS` elimina sesiones inactivas a través de la CLI de
opencode, la única acción que realmente encoge la base de datos, ya que VACUUM por sí solo
no puede.

**Por qué compensa.** En un repositorio real un `grep` por defecto ignoró la carpeta
relevante y no encontró nada; con el ignore desactivado tardó 3.95 s y aún mezcló
definiciones con sitios de llamada, mientras el grafo de código respondió la misma pregunta
en 16 ms con los 8 verdaderos sitios de llamada.

<a id="development"></a>

## Desarrollo

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI se ejecuta tanto en Python 3.10 como en 3.12. Para actualizar una copia instalada de Claude desde este checkout, usa `bin/tezgah-setup --sync`, y valida el manifiesto con `claude plugin validate .claude-plugin/plugin.json` (el manifiesto es local y no está versionado). Al incrementar la versión, actualiza `.claude-plugin/plugin.json` y `.claude-plugin/marketplace.json` juntos — deben coincidir.

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

El archivo `LICENSE` (MIT) en la raíz cubre los propios archivos de tezgah. `skills/ponytail`,
`skills/no-ai-slop` y `skills/i-have-adhd` se incluyen (vendored) bajo sus propios términos MIT, registrados en
`NOTICE`.
