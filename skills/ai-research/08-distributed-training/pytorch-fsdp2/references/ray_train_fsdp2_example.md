<!-- vendored from orchestra-research/AI-research-SKILLs@773a52944ba4747a18bd4ae9ade53fff041adcbc 08-distributed-training/pytorch-fsdp2/references/ray_train_fsdp2_example.md; MIT (c) Orchestra Research -->
# Reference: Ray Train FSDP2 integration guide (third-party, useful patterns)

**Source (third-party):** Ray docs — “Get started with PyTorch FSDP2 (Ray Train)”  
https://docs.ray.io/en/latest/train/examples/pytorch/pytorch-fsdp/README.html

## Why include this
- Shows how to integrate FSDP2 into a higher-level training orchestrator.
- Mentions common mitigation knobs (mixed precision, CPU offload, sharding granularity).
- Demonstrates checkpointing with DCP in a managed training environment.

## Agent guidance
Use as integration inspiration, not as the semantic source of truth.
