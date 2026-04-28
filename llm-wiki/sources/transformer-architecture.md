# The Transformer Architecture

Source: "Attention Is All You Need", Vaswani et al. (2017) — summary

## Overview

The Transformer is a neural network architecture introduced in 2017 that replaced recurrent neural networks (RNNs) for sequence-to-sequence tasks. Its core innovation is the **self-attention mechanism**, which allows every position in the input to directly attend to every other position. This eliminates the sequential bottleneck of RNNs and enables massive parallelization during training.

## Key ideas

**Self-attention** computes three vectors from each input token: a Query (what am I looking for?), a Key (what do I contain?), and a Value (what do I output?). Attention scores are computed as dot products of queries with all keys, scaled and softmaxed to produce weights, then used to sum the values. This is called "Scaled Dot-Product Attention."

**Multi-head attention** runs self-attention multiple times in parallel with different learned projections, then concatenates the results. Different heads can attend to different aspects of relationships — syntax in one head, semantics in another.

**Positional encodings** are added to input embeddings to inject information about token position (since attention is inherently position-agnostic). The original paper uses fixed sinusoidal encodings; most modern variants use learned positional embeddings or rotary embeddings (RoPE).

**The encoder-decoder structure** (for translation): the encoder processes the input sequence into representations; the decoder attends to both its own previous outputs and the encoder's representations.

**Feed-forward layers** are applied after attention in each block — a simple two-layer MLP applied independently to each position.

**Layer normalization** and **residual connections** around each sub-layer enable stable training of deep networks.

## Why it mattered

Before Transformers, NLP was dominated by LSTMs and GRUs — recurrent models that processed tokens sequentially. This made parallelization hard and caused gradient vanishing over long sequences.

The Transformer's parallel training allowed models to scale dramatically — from millions to hundreds of billions of parameters — because GPU/TPU throughput could be fully utilized.

## Impact

The Transformer architecture became the foundation of nearly all large language models: BERT (encoder-only), GPT (decoder-only), T5 (encoder-decoder), and beyond. As of 2026, all frontier LLMs — GPT-4, Claude, Gemini, Llama — are transformer-based with various modifications (grouped query attention, flash attention, sliding window attention, mixture-of-experts, etc.).

## Key terms

- Self-attention / Scaled Dot-Product Attention
- Multi-head attention
- Positional encoding / RoPE
- Encoder-decoder architecture
- Feed-forward layers
- Layer normalization
- Residual connections
- Token, embedding, context window
