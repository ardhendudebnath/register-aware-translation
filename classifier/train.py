"""
Fine-tune a formality classifier on the prepared splits.

    python -m classifier.train
    python -m classifier.train --max-rows 200000 --epochs 2
    python -m classifier.train --model distilbert-base-multilingual-cased

Requires the optional training extras::

    pip install -r requirements-train.txt

What this fixes relative to the previous version
------------------------------------------------
*It was a script inside ``classifier/__init__.py``.* Importing the package ran
a CUDA probe and printed to stdout as a side effect — including when the Flask
app imported anything nearby.

*``tokenize`` read a ``global tokenizer`` that only existed after ``main()``
had run*, so the function was unusable except in the one order ``main`` called
it in.

*Every sample was padded to 512 tokens.* The corpus is short sentences; that is
roughly a 4x waste of compute. Padding is now dynamic, per batch, via
``DataCollatorWithPadding``, with a 128-token cap.

*``trainer.evaluate`` reported only loss*, which cannot tell you whether the
model learned anything. There is now a ``compute_metrics`` returning accuracy
and macro/per-class F1 — and blueprint 9 is emphatic that measurement is the
part that turns this from a demo into a product.

*The whole 1.8 GB TSV was loaded into pandas at once.* Rows are now read with a
row cap and an explicit dtype, and the label set is derived from what is
actually present rather than assumed to be three classes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from utils.helpers import PROJECT_ROOT

SPLITS_DIR = PROJECT_ROOT / "data" / "splits"
RESULTS_DIR = PROJECT_ROOT / "results"
LOGS_DIR = PROJECT_ROOT / "logs"
MODEL_DIR = PROJECT_ROOT / "models" / "formality-classifier"

DEFAULT_MODEL = "distilbert-base-multilingual-cased"


def _require(module: str, hint: str):
    try:
        return __import__(module)
    except ImportError:
        sys.exit(
            f"ERROR: '{module}' is not installed.\n"
            f"The training script needs the optional extras:\n    {hint}\n"
        )


def setup_gpu(force_cpu: bool = False):
    """
    Pick the device and configure it for the GPU that is actually present.

    Returns ``(device, info)`` where ``info`` carries the precision and batch
    size decisions, so the caller can report them rather than guessing.

    The important check here is the architecture one. A PyTorch wheel only
    contains compiled kernels for the architectures it was built for, and a GPU
    newer than the wheel raises "no kernel image is available for execution on
    the device" at the first forward pass — *after* ``torch.cuda.is_available()``
    has already returned True. That is a confusing failure to hit an hour into a
    run, so it is caught up front with the exact command that fixes it.
    """
    import torch

    info = {
        "device": "cpu",
        "name": "CPU",
        "capability": None,
        "precision": "fp32",
        "vram_gb": 0.0,
        "warnings": [],
    }

    if force_cpu or not torch.cuda.is_available():
        if not force_cpu and not torch.cuda.is_available():
            info["warnings"].append(
                "CUDA is not available to PyTorch. If this machine has an NVIDIA "
                "GPU, the CPU-only wheel is probably installed — reinstall with:\n"
                "    pip install torch --index-url https://download.pytorch.org/whl/cu128"
            )
        return "cpu", info

    index = torch.cuda.current_device()
    major, minor = torch.cuda.get_device_capability(index)
    props = torch.cuda.get_device_properties(index)

    info.update({
        "device": "cuda",
        "name": torch.cuda.get_device_name(index),
        "capability": f"{major}.{minor}",
        "vram_gb": round(props.total_memory / (1024 ** 3), 1),
    })

    # Does this wheel actually have kernels for this card?
    arch_list = torch.cuda.get_arch_list()
    target = f"sm_{major}{minor}"
    compiled = [a for a in arch_list if a.startswith("sm_")]
    highest = max((int(a[3:]) for a in compiled), default=0)
    if target not in arch_list and int(f"{major}{minor}") > highest:
        info["warnings"].append(
            f"This PyTorch build has no kernels for {target} ({info['name']}).\n"
            f"    built for : {', '.join(compiled)}\n"
            f"    needed    : {target}\n"
            f"Training will fail at the first forward pass. Fix with:\n"
            f"    pip install --force-reinstall torch "
            f"--index-url https://download.pytorch.org/whl/cu128"
        )

    # bf16 has the same range as fp32 and needs no loss scaling, so on anything
    # Ampere or newer it is a strictly better choice than fp16.
    if torch.cuda.is_bf16_supported():
        info["precision"] = "bf16"
    else:
        info["precision"] = "fp16"

    # TF32 costs a little mantissa on matmuls and buys a lot of throughput.
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True

    return "cuda", info


def suggest_batch_size(info: dict) -> int:
    """
    A batch size that fits the card, for a ~66M-parameter encoder at 128 tokens.
    Conservative on purpose — an OOM three hours in is worse than a slower run.
    """
    if info["device"] != "cuda":
        return 16
    vram = info["vram_gb"]
    if vram >= 40:
        return 128
    if vram >= 20:
        return 64
    if vram >= 10:
        return 32
    if vram >= 6:
        return 16
    return 8


def load_split(name: str, max_rows: Optional[int] = None):
    """
    Read one split. The builder writes a header, so columns are read by name
    rather than by position — adding a column upstream no longer silently
    shifts the label into the wrong field.
    """
    import pandas as pd

    path = SPLITS_DIR / f"{name}.tsv"
    if not path.exists():
        sys.exit(
            f"ERROR: {path} not found.\n"
            "Build the splits first:\n"
            "    python -m data_preprocessing.build_splits\n"
        )

    df = pd.read_csv(
        path,
        sep="\t",
        dtype=str,
        nrows=max_rows,
        keep_default_na=False,
        na_values=[""],
        encoding="utf-8",
        on_bad_lines="warn",
    )

    missing = {"source_text", "formality_label"} - set(df.columns)
    if missing:
        sys.exit(
            f"ERROR: {path} is missing column(s) {sorted(missing)}.\n"
            "It looks like it was written by the old preprocessing script. "
            "Rebuild it:\n    python -m data_preprocessing.build_splits\n"
        )

    df = df.dropna(subset=["source_text", "formality_label"])
    df = df[df["source_text"].str.strip().astype(bool)].reset_index(drop=True)
    return df


def build_label_map(train_df) -> Dict[str, int]:
    """
    Derive the label set from the data.

    The old script hard-coded three classes. The corpus contains only a handful
    of 'neutral' rows, so a third logit trains on noise and never fires. Classes
    that do not appear are dropped, and the mapping is saved next to the model
    so inference cannot disagree with training about what index means what.
    """
    present = sorted(train_df["formality_label"].unique())
    return {label: i for i, label in enumerate(present)}


def compute_metrics_fn(label_map: Dict[str, int]):
    import numpy as np
    from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

    inv = {v: k for k, v in label_map.items()}

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        out = {
            "accuracy": accuracy_score(labels, preds),
            "f1_macro": f1_score(labels, preds, average="macro", zero_division=0),
        }
        p, r, f, _ = precision_recall_fscore_support(
            labels, preds, labels=list(inv), average=None, zero_division=0
        )
        for idx, name in inv.items():
            out[f"f1_{name}"] = float(f[idx])
            out[f"precision_{name}"] = float(p[idx])
            out[f"recall_{name}"] = float(r[idx])
        return out

    return compute_metrics


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fine-tune the formality classifier")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="HF model id. The default is multilingual; the old "
                             "distilbert-base-uncased could not read the "
                             "non-Latin half of this corpus.")
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--max-rows", type=int, default=None,
                        help="Cap training rows. The full corpus is millions of "
                             "pairs; start small to verify the loop runs.")
    parser.add_argument("--output-dir", default=str(MODEL_DIR))
    parser.add_argument("--cpu", action="store_true",
                        help="Force CPU even when a GPU is present.")
    parser.add_argument("--grad-accum", type=int, default=1,
                        help="Gradient accumulation steps, to raise the effective "
                             "batch size without more VRAM.")
    parser.add_argument("--workers", type=int, default=None,
                        help="DataLoader workers. Defaults to 4 on GPU, 0 on CPU.")
    parser.add_argument("--allow-arch-mismatch", action="store_true",
                        help="Train anyway when the PyTorch build has no kernels "
                             "for this GPU. It will almost certainly fail.")
    args = parser.parse_args(argv)

    _require("torch", "pip install -r requirements-train.txt")
    _require("transformers", "pip install -r requirements-train.txt")
    _require("datasets", "pip install -r requirements-train.txt")

    import torch
    from datasets import Dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        Trainer,
        TrainingArguments,
    )

    device, gpu = setup_gpu(force_cpu=args.cpu)
    batch_size = args.batch_size or suggest_batch_size(gpu)
    workers = args.workers if args.workers is not None else (4 if device == "cuda" else 0)

    print(f"Device      : {device}")
    if device == "cuda":
        print(f"GPU         : {gpu['name']}")
        print(f"VRAM        : {gpu['vram_gb']} GB   compute {gpu['capability']}")
        print(f"Precision   : {gpu['precision']} (TF32 matmul on)")
    print(f"Model       : {args.model}")
    print(f"Batch size  : {batch_size}"
          + (f" x {args.grad_accum} accum = {batch_size * args.grad_accum} effective"
             if args.grad_accum > 1 else ""))

    for warning in gpu["warnings"]:
        print(f"\nWARNING: {warning}")
    fatal = any("no kernels" in w for w in gpu["warnings"])
    if fatal and not args.allow_arch_mismatch:
        print("\nRefusing to start — pass --allow-arch-mismatch to override.")
        return 1
    print()

    print("Loading splits...")
    train_df = load_split("train", args.max_rows)
    val_cap = max(1, args.max_rows // 8) if args.max_rows else None
    val_df = load_split("val", val_cap)
    test_df = load_split("test", val_cap)

    label_map = build_label_map(train_df)
    print(f"Labels      : {label_map}")
    if len(label_map) < 2:
        sys.exit("ERROR: need at least two classes to train a classifier.")

    for name, df in (("train", train_df), ("val", val_df), ("test", test_df)):
        counts = df["formality_label"].value_counts().to_dict()
        print(f"  {name:<5} {len(df):>10,}  {counts}")
    print()

    def prepare(df):
        df = df[df["formality_label"].isin(label_map)].copy()
        df["labels"] = df["formality_label"].map(label_map)
        return Dataset.from_pandas(
            df[["source_text", "labels"]].reset_index(drop=True),
            preserve_index=False,
        )

    train_ds, val_ds, test_ds = prepare(train_df), prepare(val_df), prepare(test_df)

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model,
        num_labels=len(label_map),
        id2label={v: k for k, v in label_map.items()},
        label2id=label_map,
    )

    def tokenize(batch):
        # No padding here — the collator pads each batch to its own longest
        # sequence, which is where the 4x saving comes from.
        return tokenizer(batch["source_text"], truncation=True,
                         max_length=args.max_length)

    print("Tokenising...")
    remove = ["source_text"]
    train_ds = train_ds.map(tokenize, batched=True, remove_columns=remove)
    val_ds = val_ds.map(tokenize, batched=True, remove_columns=remove)
    test_ds = test_ds.map(tokenize, batched=True, remove_columns=remove)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(RESULTS_DIR),
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        learning_rate=args.learning_rate,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,   # no optimiser state at eval
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        warmup_ratio=0.06,
        logging_dir=str(LOGS_DIR),
        logging_steps=50,
        save_total_limit=2,
        # bf16 where the card supports it: same exponent range as fp32, so no
        # loss scaling and no silent overflow to NaN partway through a long run.
        bf16=(device == "cuda" and gpu["precision"] == "bf16"),
        fp16=(device == "cuda" and gpu["precision"] == "fp16"),
        dataloader_num_workers=workers,
        dataloader_pin_memory=(device == "cuda"),
        group_by_length=True,     # pairs with dynamic padding to cut wasted compute
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=compute_metrics_fn(label_map),
    )

    print("Training...")
    trainer.train()

    print("Evaluating on the held-out test split...")
    metrics = trainer.evaluate(test_ds, metric_key_prefix="test")
    for key in sorted(metrics):
        print(f"  {key:<28} {metrics[key]}")

    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    (out_dir / "label_map.json").write_text(
        json.dumps(label_map, indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / "test_metrics.json").write_text(
        json.dumps(metrics, indent=2, default=float), encoding="utf-8"
    )
    print(f"\nSaved model to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
