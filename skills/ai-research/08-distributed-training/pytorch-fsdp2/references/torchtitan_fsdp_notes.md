<!-- vendored from orchestra-research/AI-research-SKILLs@773a52944ba4747a18bd4ae9ade53fff041adcbc 08-distributed-training/pytorch-fsdp2/references/torchtitan_fsdp_notes.md; MIT (c) Orchestra Research -->
# Reference: TorchTitan notes on FSDP/FSDP2 (production-oriented)

**Source (official-ish, PyTorch org):** TorchTitan — FSDP docs  
https://github.com/pytorch/torchtitan/blob/main/docs/fsdp.md

## Why include this
TorchTitan is a PyTorch reference stack for large-scale LLM training. Its FSDP documentation often contains pragmatic guidance around:
- configuration choices (e.g., sharding strategy vs memory/perf)
- checkpointing workflows in larger systems
- composition with other parallelisms

## Agent guidance
Treat TorchTitan as a “how people do it in production” complement to the API docs/tutorials. Always defer to the official API docs on semantics.
