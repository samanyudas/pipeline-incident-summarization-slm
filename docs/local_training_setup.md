# Local training setup

The local environment uses Python 3.12.14, MLX 0.32.2, and MLX-LM 0.31.3 on Apple M3 with 16 GiB memory.
Exact installed versions are in `requirements-training.lock.txt`.
The environment is project-local under `.venv/`.

The checkpoint is the official post-trained `Qwen/Qwen3.5-0.8B` at revision `2fc06364715b967f1860aea9cf38778875588b17`.
The publisher labels it Apache 2.0, with the license saved alongside the checkpoint.
Source: https://huggingface.co/Qwen/Qwen3.5-0.8B/tree/2fc06364715b967f1860aea9cf38778875588b17
MLX LoRA documentation: https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md

The 32 accepted chat examples contain 624 to 2270 tokens using the official tokenizer and non-thinking chat template.
All target answers occur in full within the rendered template.
The training limit is 2560 tokens; overlength examples must fail rather than truncate.
The tuner verifies that the answer-mask offset matches the exact tokenized prompt prefix.

The first trial uses two steps, batch size one, rank eight, last four layers, learning rate 0.00001, seed zero, and gradient checkpointing.
Base parameters are frozen by the tuner before adapters are added.
Only adapter parameters may remain trainable.
The trial has no validation-loss dataset and uses no development targets for gradient updates.
No external compute service or paid training is used.
The smoke test is limited to two steps; further training requires a separate experiment record.

A fresh MLX base-model run precedes training for a same-backend comparison.
Reasoning is disabled explicitly, and generation uses temperature zero with a 700-token limit.
Final-test narratives remain excluded.

## Verified minimal profile

The initial four-layer test did not complete and saved no adapter.
The successful fallback uses rank 4 adapters only on `self_attn.q_proj` and `self_attn.v_proj` of the final layer.
It checks every accepted example for truncation and mask correctness, then selects the two shortest complete examples for the technical smoke test.
The explicit MLX allocator limit is 6 GiB and cache limit 256 MiB; the parent process enforces a 120-second timeout.
The observed two-step run finished in 14.05 seconds with 3.190 GB reported peak memory.
Fresh-process loading and generation passed.
This changes adapter scope, so it does not prove the original four-layer configuration is viable.
