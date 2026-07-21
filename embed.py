"""Compute SPECTER2 embeddings for CVPR 2026 papers.

Reads data/cvpr_2026_papers.json, writes data/cvpr_2026_specter2.npy
as a [len(papers), 768] float32 array (CLS pooled, title + abstract).
"""
import json

import numpy as np
import torch
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

PAPERS_PATH = "data/cvpr_2026_papers.json"
OUTPUT_PATH = "data/cvpr_2026_specter2.npy"
BATCH_SIZE = 32
MAX_LENGTH = 512


def main():
    with open(PAPERS_PATH, "r") as f:
        papers = json.load(f)
    n_papers = len(papers)
    print(f"Loaded {n_papers} papers from {PAPERS_PATH}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_fp16 = device.type == "cuda"
    print(f"Using device={device}, fp16={use_fp16}")

    tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base")
    model = AutoAdapterModel.from_pretrained("allenai/specter2_base")
    model.load_adapter(
        "allenai/specter2", source="hf", load_as="proximity", set_active=True
    )
    model.to(device)
    model.eval()
    if use_fp16:
        model.half()

    texts = [
        p["title"] + tokenizer.sep_token + p["abstract"] for p in papers
    ]

    all_embeddings = []
    with torch.no_grad():
        for start in range(0, n_papers, BATCH_SIZE):
            batch_texts = texts[start : start + BATCH_SIZE]
            inputs = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
                return_tensors="pt",
            ).to(device)
            outputs = model(**inputs)
            cls = outputs.last_hidden_state[:, 0, :]
            all_embeddings.append(cls.float().cpu().numpy())
            done = min(start + BATCH_SIZE, n_papers)
            if done % (BATCH_SIZE * 10) == 0 or done == n_papers:
                print(f"  embedded {done}/{n_papers}")

    embeddings = np.concatenate(all_embeddings, axis=0).astype(np.float32)

    assert embeddings.shape == (n_papers, 768), (
        f"expected shape ({n_papers}, 768), got {embeddings.shape}"
    )
    assert not np.isnan(embeddings).any(), "embeddings contain NaN"

    np.save(OUTPUT_PATH, embeddings)
    print(f"Wrote {embeddings.shape} embeddings to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
