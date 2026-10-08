"""Compute SPECTER2 embeddings for the papers.

Reads config.PAPERS_PATH, writes config.EMBEDDINGS_PATH as a
[n_papers, 768] float16 array (CLS pooled, title + abstract). float16 halves the
file size; cosine similarity is unaffected at that precision. Runs on CPU in
roughly 15-30 minutes for ~6000 papers, or in a couple of minutes on a GPU.
"""
import json

import numpy as np
import torch
from adapters import AutoAdapterModel
from transformers import AutoTokenizer

import config

BATCH_SIZE = 32
MAX_LENGTH = 512


def main():
    with open(config.PAPERS_PATH) as f:
        papers = json.load(f)
    n_papers = len(papers)
    print(f"Loaded {n_papers} papers from {config.PAPERS_PATH}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_fp16 = device.type == "cuda"
    print(f"Using device={device}, fp16={use_fp16}")

    tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base")
    model = AutoAdapterModel.from_pretrained("allenai/specter2_base")
    model.load_adapter("allenai/specter2", source="hf", load_as="proximity", set_active=True)
    model.to(device)
    model.eval()
    if use_fp16:
        model.half()

    texts = [p["title"] + tokenizer.sep_token + p["abstract"] for p in papers]

    chunks = []
    with torch.no_grad():
        for start in range(0, n_papers, BATCH_SIZE):
            inputs = tokenizer(
                texts[start : start + BATCH_SIZE],
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
                return_tensors="pt",
            ).to(device)
            cls = model(**inputs).last_hidden_state[:, 0, :]
            chunks.append(cls.float().cpu().numpy())
            done = min(start + BATCH_SIZE, n_papers)
            if done % (BATCH_SIZE * 10) == 0 or done == n_papers:
                print(f"  embedded {done}/{n_papers}")

    embeddings = np.concatenate(chunks, axis=0)
    assert embeddings.shape == (n_papers, 768), f"unexpected shape {embeddings.shape}"
    assert np.isfinite(embeddings).all(), "embeddings contain NaN or inf"

    np.save(config.EMBEDDINGS_PATH, embeddings.astype(np.float16))
    print(f"Wrote {embeddings.shape} embeddings to {config.EMBEDDINGS_PATH}")


if __name__ == "__main__":
    main()
