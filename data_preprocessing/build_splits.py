"""
Build train/val/test splits from the FAME-MT corpus.

Run it with::

    python -m data_preprocessing.build_splits
    python -m data_preprocessing.build_splits --max-rows-per-file 20000

What this replaces
------------------
Three near-identical copies of this logic used to live in
``data_preprocessing/__init__.py``, ``src/preprocessing/preprocess.py`` and
``src/preprocessing/__init__.py``. They shared four defects:

*Label corruption.* All three read slang terms via ``slang_dict.keys()``, which
on the real nested dictionary yields *language codes* — then matched them as
substrings. "en" inside "s**en**d" and "pl" inside "**pl**ease" tagged most of
the corpus informal, which is why the old test split came out 2172 informal to
794 formal on a corpus that is balanced by construction.

*Slang overrode ground truth.* Even with matching fixed, rewriting a
filename-derived ``formal`` label to ``informal`` because a token looked slangy
throws away the only reliable signal in the dataset. Slang is now recorded as a
*feature column*, and the override is opt-in behind ``--slang-overrides-label``.

*Memory.* ``pd.concat`` over every file materialised the whole ~4 GB corpus
before splitting. Rows are now streamed and assigned to a split by a stable
hash of their content, so peak memory is one chunk.

*Round-tripping.* Fields containing tabs or newlines corrupted the output TSV,
which the reader then papered over with ``on_bad_lines="skip"``. Fields are
sanitised on write and the output carries a header.

*Ordering.* Rows used to be written in corpus order, so the head of train.tsv
was entirely one language pair and one class. Anything that reads a prefix of
the file — ``--max-rows``, a quick sanity run, a notebook — got a single-class
sample and could not train at all. Rows now pass through a bounded shuffle
buffer on the way out, which keeps the stream constant-memory while making any
prefix of the output representative.
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import os
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from utils.helpers import DATA_DIR, PROJECT_ROOT, load_slang_dictionary
from utils.slang_detection import detect_slang, flatten_slang_dictionary

RAW_DATASET_DIR = DATA_DIR / "dataset"
SPLITS_DIR = DATA_DIR / "splits"
NEUTRAL_FILE = DATA_DIR / "neutral_samples_for_NMT_fine_tuning.tsv"

COLUMNS = ("source_text", "target_text", "formality_label", "src_lang", "tgt_lang", "has_slang")

LABELS = ("formal", "informal", "neutral")

#: data/dataset/all2de/cs-de.formal.tsv -> ("cs", "de", "formal")
_FILENAME_RE = re.compile(
    r"(?P<src>[a-z]{2})-(?P<tgt>[a-z]{2})\.(?P<label>formal|informal)\.tsv$",
    re.IGNORECASE,
)

_WHITESPACE = re.compile(r"[\t\r\n]+")


class ShuffleBuffer:
    """
    Bounded shuffle on the way to disk.

    Holds up to ``size`` rows, shuffles each block and flushes it. Memory stays
    constant, and any prefix of the resulting file is a fair mix of languages
    and classes — which a straight streaming write is not. Seeded, so repeated
    runs produce identical files.
    """

    def __init__(self, writer, size: int = 200_000, seed: int = 42):
        self._writer = writer
        self._size = max(1, size)
        self._rng = random.Random(seed)
        self._rows: List[list] = []

    def write(self, row: list) -> None:
        self._rows.append(row)
        if len(self._rows) >= self._size:
            self.flush()

    def flush(self) -> None:
        if not self._rows:
            return
        self._rng.shuffle(self._rows)
        self._writer.writerows(self._rows)
        self._rows.clear()


@dataclass
class Stats:
    files: int = 0
    rows_read: int = 0
    rows_kept: int = 0
    rows_dropped: int = 0
    per_split: Dict[str, Counter] = field(default_factory=dict)

    def record(self, split: str, label: str) -> None:
        self.per_split.setdefault(split, Counter())[label] += 1

    def report(self) -> None:
        print()
        print(f"Files read      : {self.files}")
        print(f"Rows read       : {self.rows_read:,}")
        print(f"Rows kept       : {self.rows_kept:,}")
        print(f"Rows dropped    : {self.rows_dropped:,}  (blank or malformed)")
        print()
        for split in ("train", "val", "test"):
            counts = self.per_split.get(split, Counter())
            total = sum(counts.values())
            print(f"{split:<6} {total:>12,}")
            for label in LABELS:
                n = counts.get(label, 0)
                pct = (100.0 * n / total) if total else 0.0
                print(f"       {label:<10} {n:>12,}  {pct:5.1f}%")
        print()
        self._warn_on_imbalance()

    def _warn_on_imbalance(self) -> None:
        train = self.per_split.get("train", Counter())
        total = sum(train.values())
        if not total:
            return
        for label in LABELS:
            share = train.get(label, 0) / total
            if share == 0:
                print(
                    f"WARNING: the '{label}' class has no training rows. "
                    f"Train a {len([l for l in LABELS if train.get(l)])}-class model, "
                    f"not a {len(LABELS)}-class one, or the unused logit will only add noise."
                )
            elif share < 0.02:
                print(
                    f"WARNING: '{label}' is {share:.2%} of training rows. "
                    "Expect the classifier to ignore it unless you weight the loss."
                )


def parse_filename(path: str) -> Optional[Tuple[str, str, str]]:
    """Pull (src_lang, tgt_lang, label) out of a dataset filename."""
    m = _FILENAME_RE.search(os.path.basename(path))
    if not m:
        return None
    return m.group("src").lower(), m.group("tgt").lower(), m.group("label").lower()


def sanitise(value: str) -> str:
    """
    Flatten embedded tabs and newlines so a field cannot break the TSV.

    Without this, a single multi-line source sentence shifts every following
    column and the reader has to skip the row.
    """
    return _WHITESPACE.sub(" ", value).strip()


def assign_split(key: str, train_pct: int = 80, val_pct: int = 10) -> str:
    """
    Deterministically place a row in a split from a stable hash of its text.

    Hashing rather than shuffling is what lets this stream: no need to hold the
    corpus in memory to shuffle it, and re-running gives byte-identical splits.
    Python's built-in hash() is salted per process and would not.
    """
    digest = hashlib.md5(key.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % 100
    if bucket < train_pct:
        return "train"
    if bucket < train_pct + val_pct:
        return "val"
    return "test"


def iter_rows(
    path: Path,
    src_lang: str,
    tgt_lang: str,
    label: str,
    stats: Stats,
    max_rows: Optional[int] = None,
) -> Iterator[Tuple[str, str, str, str, str]]:
    """Stream (source, target, label, src_lang, tgt_lang) out of one TSV."""
    kept = 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        for line in fh:
            stats.rows_read += 1
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                stats.rows_dropped += 1
                continue
            source, target = sanitise(parts[0]), sanitise(parts[1])
            if not source or not target:
                stats.rows_dropped += 1
                continue
            yield source, target, label, src_lang, tgt_lang
            kept += 1
            if max_rows is not None and kept >= max_rows:
                return


def iter_neutral(stats: Stats) -> Iterator[Tuple[str, str, str, str, str]]:
    """The hand-written neutral samples, if the file is present."""
    if not NEUTRAL_FILE.exists():
        return
    # A bare `return` in a generator yields nothing, which is what we want when
    # the optional file is absent.
    with NEUTRAL_FILE.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        for line in fh:
            stats.rows_read += 1
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                stats.rows_dropped += 1
                continue
            source, target = sanitise(parts[0]), sanitise(parts[1])
            if not source or not target:
                stats.rows_dropped += 1
                continue
            yield source, target, "neutral", "", ""


def build(
    max_rows_per_file: Optional[int] = None,
    slang_overrides_label: bool = False,
    train_pct: int = 80,
    val_pct: int = 10,
    shuffle_buffer: int = 200_000,
) -> Stats:
    files = sorted(glob.glob(str(RAW_DATASET_DIR / "**" / "*.tsv"), recursive=True))
    if not files:
        raise FileNotFoundError(
            f"No dataset TSVs found under {RAW_DATASET_DIR}. "
            "Expected files like data/dataset/all2de/cs-de.formal.tsv"
        )

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    stats = Stats()
    slang_dict = load_slang_dictionary()
    # Pre-resolve the per-language term sets once rather than per row.
    slang_cache: Dict[str, dict] = {}

    handles = {}
    writers = {}
    buffers = {}
    try:
        for split in ("train", "val", "test"):
            path = SPLITS_DIR / f"{split}.tsv"
            handles[split] = path.open("w", encoding="utf-8", newline="")
            writers[split] = csv.writer(
                handles[split], delimiter="\t", lineterminator="\n",
                quoting=csv.QUOTE_MINIMAL,
            )
            writers[split].writerow(COLUMNS)
            buffers[split] = ShuffleBuffer(writers[split], size=shuffle_buffer)

        def emit(source, target, label, src_lang, tgt_lang):
            if src_lang not in slang_cache:
                slang_cache[src_lang] = flatten_slang_dictionary(
                    slang_dict, src_lang or None
                )
            terms = slang_cache[src_lang]
            has_slang = bool(terms) and bool(detect_slang(source, slang_dict, src_lang or None))

            final_label = label
            if has_slang and slang_overrides_label and label == "formal":
                final_label = "informal"

            split = assign_split(source + "\x00" + target, train_pct, val_pct)
            buffers[split].write(
                [source, target, final_label, src_lang, tgt_lang, int(has_slang)]
            )
            stats.record(split, final_label)
            stats.rows_kept += 1

        # Read every file concurrently, round-robin, rather than one after
        # another. The shuffle buffer only mixes what is inside it, so reading
        # sequentially still leaves the output ordered by language pair — the
        # first 4000 rows came from 3 pairs out of 224. Interleaving makes the
        # stream globally mixed, so any prefix is representative of the whole
        # corpus in both class and language.
        readers = []
        for path_str in files:
            meta = parse_filename(path_str)
            if meta is None:
                continue
            src_lang, tgt_lang, label = meta
            stats.files += 1
            print(f"  {os.path.relpath(path_str, PROJECT_ROOT)}  [{src_lang}->{tgt_lang} {label}]",
                  flush=True)
            readers.append(
                iter_rows(Path(path_str), src_lang, tgt_lang, label,
                          stats, max_rows_per_file)
            )
        readers.append(iter_neutral(stats))

        print(f"\nInterleaving {len(readers)} sources...", flush=True)
        while readers:
            live = []
            for reader in readers:
                try:
                    emit(*next(reader))
                except StopIteration:
                    continue
                live.append(reader)
            readers = live

    finally:
        for buffer in buffers.values():
            buffer.flush()
        for fh in handles.values():
            fh.close()

    return stats


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "--max-rows-per-file", type=int, default=None,
        help="Cap rows taken from each source file. Useful for a fast smoke run "
             "over a 4 GB corpus.",
    )
    parser.add_argument(
        "--slang-overrides-label", action="store_true",
        help="Relabel a 'formal' row as 'informal' when slang is detected in it. "
             "Off by default: the filename label is ground truth, and overriding "
             "it is what corrupted the previous splits.",
    )
    parser.add_argument("--train-pct", type=int, default=80)
    parser.add_argument("--val-pct", type=int, default=10)
    parser.add_argument(
        "--shuffle-buffer", type=int, default=200_000,
        help="Rows held in memory and shuffled before each flush. Larger mixes "
             "better; smaller uses less memory. 0 disables shuffling.",
    )
    args = parser.parse_args(argv)

    if not 0 < args.train_pct < 100 or not 0 <= args.val_pct < 100:
        parser.error("--train-pct and --val-pct must describe a valid split")
    if args.train_pct + args.val_pct >= 100:
        parser.error("--train-pct + --val-pct must leave room for a test split")

    print(f"Reading  : {RAW_DATASET_DIR}")
    print(f"Writing  : {SPLITS_DIR}")
    print()
    stats = build(
        max_rows_per_file=args.max_rows_per_file,
        slang_overrides_label=args.slang_overrides_label,
        train_pct=args.train_pct,
        val_pct=args.val_pct,
        shuffle_buffer=args.shuffle_buffer or 1,
    )
    stats.report()
    print("Preprocessing complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
