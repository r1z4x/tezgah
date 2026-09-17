<!-- vendored from orchestra-research/AI-research-SKILLs@773a52944ba4747a18bd4ae9ade53fff041adcbc 08-distributed-training/pytorch-fsdp2/references/pytorch_examples_fsdp2.md; MIT (c) Orchestra Research -->
# Reference: Official `pytorch/examples` FSDP2 scripts

**Sources (official, code):**
- `pytorch/examples` repository: https://github.com/pytorch/examples
- FSDP2 checkpoint example: https://github.com/pytorch/examples/blob/main/distributed/FSDP2/checkpoint.py

## Why this matters
The FSDP2 tutorial explicitly points users to `pytorch/examples` for end-to-end scripts, especially for:
- optimizer state dict save/load with the DCP state-dict helpers
- runnable command lines and minimal scaffolding

## How agents should use this
- Prefer copying patterns from these scripts over inventing new checkpoint logic.
- Keep the script structure (init distributed, build model, shard, optimizer, train loop, save/load) similar to ease debugging.
