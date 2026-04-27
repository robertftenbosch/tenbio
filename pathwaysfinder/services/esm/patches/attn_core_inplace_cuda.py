"""Stub module replacing openfold's attn_core_inplace_cuda C extension.

Provides forward_/backward_ as pure PyTorch ops for inference on runtime images
without the CUDA toolkit.
"""
import torch


def forward_(attention_logits, flat_size, last_dim):
    """In-place softmax over the last dimension."""
    attention_logits.copy_(torch.softmax(attention_logits, dim=-1))


def backward_(attention_logits, grad_output, v, flat_size, last_dim, v_dim):
    """In-place backward pass for softmax attention (not needed for inference)."""
    raise NotImplementedError("CUDA attention backward stub - inference only")
