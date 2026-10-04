<!-- vendored from orchestra-research/AI-research-SKILLs@773a52944ba4747a18bd4ae9ade53fff041adcbc 08-distributed-training/pytorch-fsdp2/references/pytorch_fsdp1_api.md; MIT (c) Orchestra Research -->
# Reference: Fully Sharded Data Parallel (FSDP1) API

**Source (official):** PyTorch docs — “Fully Sharded Data Parallel”  
https://docs.pytorch.org/docs/stable/fsdp.html  
Last accessed: Jan 30, 2026

## Key points (paraphrased from the API docs)
- `torch.distributed.fsdp.FullyShardedDataParallel` is the original FSDP wrapper for sharding module parameters across data-parallel workers.
