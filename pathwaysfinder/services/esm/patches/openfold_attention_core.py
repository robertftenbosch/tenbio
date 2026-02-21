"""Pure PyTorch replacement for openfold's CUDA attention kernel."""
import torch


def attention_core(q, k, v, bias_1=None, bias_2=None):
    attn = torch.matmul(q, k.transpose(-1, -2))
    if bias_1 is not None:
        attn = attn + bias_1
    if bias_2 is not None:
        attn = attn + bias_2
    attn = torch.softmax(attn, dim=-1)
    return torch.matmul(attn, v)
