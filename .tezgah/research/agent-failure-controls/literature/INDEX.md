# Literature index

Fetched 2026-09-17 with `orx discover` (alphaXiv keyword/embedding) and read with
`orx paper`. One file per source, `<alphaxiv-id>.md`, holding the full alphaXiv
report. Group tags name where the note is load-bearing in this line.

41 files: 38 fetched in the main retrieval loop, and `2605.05403`,
`2608.29646` and `2608.25920` fetched afterwards because writer briefs named
them before they existed here.

| id | title | group | why it is here |
|---|---|---|---|
| 2608.23623 | When May an Agent Stop? Evidence-Carrying Termination for Tool-Using LLMs | A, F | the completion gate as a typed certificate bound to a ledger digest, with replay; 0/288 unsafe completions vs 252/288 for a critic core |
| 2608.27768 | Why Didn't It Check? Unsupported Final Claims and Their Repair | A, D | how unsupported final claims are produced and repaired in two tool-equipped models |
| 2609.00652 | Self-Reports Are Not Verification: Environment-Grounded Auditing | A | grading an operator's work from the environment rather than from its self-report |
| 2609.12205 | Plans They Abandon, Reports They Author: The Narrative Layer of Autonomous Agents | A | the gap between the plan an agent followed and the report it wrote |
| 2607.13071 | Compaction as Epistemic Failure | A, C | how compaction fabricates confirmed results from killed processes |
| 2609.09090 | Measuring LLM Sycophancy under Sustained Multi-Turn Pressure | A | the apology/agreement loop measured over turns |
| 2605.05403 | When Helpfulness Becomes Sycophancy | A | sycophancy as a boundary failure between social alignment and epistemic integrity |
| 2608.23635 | ToolRobustBench: Stage-Wise Perturbation Evaluation and Failure Diagnosis for Tool-Calling Agents | B | four perturbation families aligned with the tool-use pipeline: interface, intent, observation, runtime |
| 2608.22676 | Robustness Analysis of Agentic AI to Inconsistent and Incomplete Tool Responses | B | typing a tool failure at the moment the return enters context |
| 2609.05587 | Agents Trust Tools Too Much: Measuring Reliance on Unreliable Tools | B, E | adoption of corrupted tool returns, mean over a third, 68% for web search |
| 2608.26189 | Invocation-Level Reliability of Tool-Using Agents | B | reliability measured per invocation rather than per task |
| 2608.02645 | Verified Tool Calls Improve LLM Agent Reliability Under Non-Atomic Failures | B | what verification of a call buys under partial failure |
| 2608.25403 | Retry Amplification in Distributed Systems | B, F | why an uncapped retry policy turns a local failure into a cascade |
| 2608.21159 | AID-Guard: Stateful Authorization for Delegated Agent Effects | B, E | authorization state carried across a delegated effect |
| 2608.01710 | Beyond Single-Use Tokens: Durable Authorization State for Replay-Resistant LLM Agent Actions | B, E | replay resistance, i.e. the idempotency problem for agent actions |
| 2607.09510 | Failure as a Process: An Anatomy of CLI Coding Agent Trajectories | B, D | 3,843 trajectories, seven models: onset, evolution and recovery of failure |
| 2606.29718 | Diagnosing and Mitigating Context Rot in Long-horizon Search | C | failure under long context, including premature termination |
| 2609.01660 | How Fast Do Agents Rot? | C, F | long-horizon degradation as a geometric law in a per-step reliability parameter |
| 2608.21690 | Context as an Environment: Programmatic Context Management for Long-Horizon Agents | C | context as an append-only event log plus a persistent namespace, not a prompt |
| 2608.20664 | DreamBench-SWE: A Multi-Session Memory-Hygiene Benchmark | C | memory hygiene scored across sessions |
| 2608.04574 | When Memory Lies: An Empirical Study of Spatial Memory Staleness | C | staleness as a measurable memory defect |
| 2605.06445 | Constraint Decay: The Fragility of LLM Agents in Backend Code Generation | C, D | a standing constraint losing its effect as the task runs |
| 2609.03267 | Refusing the Impossible: A Taxonomy and Benchmark for Code Hallucination | D | a taxonomy of non-existent APIs and impossible code |
| 2607.08981 | The Patchwork Problem in LLM-Generated Code | D | integration defects in generated code |
| 2608.07899 | TelemetrySuffBench: Is Agent Telemetry Sufficient for Failure-Origin Diagnosis? | D, F | whether the telemetry a harness records is enough to find the cause |
| 2608.24271 | Observability and Fault Injection for LLM-Based Multi-Agent Systems in Software Engineering | D, F | fault injection as the way to test a harness's own detection |
| 2608.02464 | Real-Time Detection and Repair of LLM Agent Failures | D, F | detection and repair at run time |
| 2609.11596 | From Intent to Execution Grant: An Execution-Boundary Conformance Profile for High-Risk AI Actions | E, G | the boundary at which an intent becomes an authorized execution |
| 2608.18351 | Task-Conditioned Least-Privilege Learning for Executable Terminal and MCP Agents | E, G | least privilege for terminal and MCP tools |
| 2608.22868 | AgentFlow: A Flow-Centric Policy Language and Framework for Securing LLM Agent Systems | E, G | policies as a flow rather than a per-call rule |
| 2608.23282 | From Natural Language Policies to Executable Obligations | E, G | compiling a natural-language policy into checkable obligations |
| 2609.14744 | AcquireBound: Runtime Authorization for Resources Acquired by AI Agents | E, G | authorization for resources acquired mid-run |
| 2608.10669 | REDAgentBench: Executable Red Teaming and Faithful Measurement of LLM Agent Systems | E | attack-derived red teaming with effect verification |
| 2608.26195 | Cost-Utility Alignment in LLM Agent Trajectories | F | profiling and attributing cost against utility |
| 2608.24361 | Adaptive Influence Graphs for Failure Attribution in Multi-Agent Systems | F | a failed trace turned into a navigable graph |
| 2608.29646 | Detect Before You Attribute: Cascade Failure Attribution | F | detecting an anomalous execution before attributing it |
| 2608.23670 | Automata from Agent Traces: Failure and Next-Step Prediction | F | learning a trace automaton for prediction |
| 2609.01466 | Parsing the Stream: A Live Trace Model for Long-Horizon Agents | F | a live trace model for an observer |
| 2608.25920 | Repair or Resample? Rethinking Failure Debugging in LLM Multi-Agent Systems | F | whether a repair is causal or just resampling |
| 2608.17597 | HarnessRisk: A Lifecycle-Oriented Benchmark for Agent Harness Safety | all | harness safety split into six phases: configuration, extension, runtime, state persistence, action control, incident recovery |
| 2607.20982 | GuardianAgentBench: Where Agents Fail and How to Guard Them | B, F | two failure regimes: stronger models under-call, weaker ones mis-select and over-call |

Not fetched: the OpenAlex reviews on prompt-injection in agent systems
(10.3390/info17010054) and MCP tool poisoning (10.3390/jcp6030084) were seen in
the discovery output only; their titles and abstracts are quoted from that output
and their full text was not read.
