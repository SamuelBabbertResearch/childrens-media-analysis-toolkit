"""
analyzer/vocab_complexity.py — Vocabulary complexity, readability, and lexical diversity.

Measures the linguistic difficulty of a caption track, independent of speech speed (WPM).
Output is a relative complexity index for cross-show comparison — not a literal grade-level
claim, and not affiliated with any broadcast standard.

Pipeline
--------
CC file
  → extract_cc_text()        (shared with speech.py — strips timestamps/seq numbers)
  → _strip_non_speech()      (strips [MUSIC], (laughs), SPEAKER: labels)
  → spaCy en_core_web_sm:    sentence segmentation, POS tagging, lemmatization
       ┌──────────────────────────────────────────────┐
       │ full_text     → readability formulas (textstat)│
       │ content tokens→ vocab measures + MTLD         │
       │ (NOUN/VERB/ADJ/ADV, no PROPN, lemmatized)     │
       └──────────────────────────────────────────────┘
  → VocabResult dataclass + reproducibility manifest
"""

from __future__ import annotations

import importlib.metadata
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__version__ = "1.0.0"

_SPACY_MODEL = "en_core_web_sm"
_NORM_DIR    = Path(__file__).parent.parent / "data" / "norms"

# Zipf tier thresholds (Zipf scale: roughly log10(occurrences per billion words) + 3)
ZIPF_TIER1_GE = 4.5   # Tier 1 — everyday words
ZIPF_TIER2_GE = 3.0   # Tier 2 — academic / cross-domain
ZIPF_TIER3_LT = 3.0   # Tier 3 — rare / domain-specific

# POS tags that count as content words for vocabulary measures.
# PROPN (proper noun) is intentionally absent — invented names (SpongeBob,
# Bikini Bottom) are rare tokens that would falsely inflate Tier 3.
_CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}

# Non-speech patterns stripped before analysis
_BRACKET_RE = re.compile(r'\[.*?\]', re.DOTALL)   # [MUSIC], [APPLAUSE]
_PAREN_RE   = re.compile(r'\(.*?\)', re.DOTALL)   # (laughs), (gasps)
_SPEAKER_RE = re.compile(r'\b[A-Z][A-Z ]{1,20}:\s*')  # NARRATOR:  LITTLE BEAR:

# Minimum sizes below which formulas are unreliable
_MIN_WORDS_FOR_READABILITY = 30
_MIN_TOKENS_FOR_DIVERSITY  = 50


# ---------------------------------------------------------------------------
# Version helper
# ---------------------------------------------------------------------------

def _pkg_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


# ---------------------------------------------------------------------------
# Norm tables
# ---------------------------------------------------------------------------

@dataclass
class NormTables:
    aoa: dict[str, float]           # lemma → Age of Acquisition  (Kuperman et al.)
    concreteness: dict[str, float]  # lemma → Concreteness rating (Brysbaert et al.)
    aoa_path: str
    conc_path: str
    aoa_n: int                      # number of entries loaded
    conc_n: int


def load_norms(norm_dir: Path = _NORM_DIR) -> NormTables:
    """Load psycholinguistic norm files from norm_dir.

    Expected files and canonical column names (original publication names):
      kuperman_aoa.csv           — columns: Word, AoA_Rating_Mean
      brysbaert_concreteness.csv — columns: Word, Conc.M

    Raises FileNotFoundError with a clear message if either file is absent.
    """
    import pandas as pd

    aoa_path  = Path(norm_dir) / "kuperman_aoa.csv"
    conc_path = Path(norm_dir) / "brysbaert_concreteness.csv"

    if not aoa_path.exists():
        raise FileNotFoundError(
            f"Kuperman AoA norms not found: {aoa_path}\n"
            "Place kuperman_aoa.csv in data/norms/ relative to the project root.\n"
            "Expected columns: Word, AoA_Rating_Mean"
        )
    if not conc_path.exists():
        raise FileNotFoundError(
            f"Brysbaert concreteness norms not found: {conc_path}\n"
            "Place brysbaert_concreteness.csv in data/norms/ relative to the project root.\n"
            "Expected columns: Word, Conc.M"
        )

    aoa_df  = pd.read_csv(aoa_path)
    conc_df = pd.read_csv(conc_path)

    aoa = {
        str(row["Word"]).lower(): float(row["AoA_Rating_Mean"])
        for _, row in aoa_df.iterrows()
        if pd.notna(row.get("AoA_Rating_Mean"))
    }
    conc = {
        str(row["Word"]).lower(): float(row["Conc.M"])
        for _, row in conc_df.iterrows()
        if pd.notna(row.get("Conc.M"))
    }

    return NormTables(
        aoa=aoa, concreteness=conc,
        aoa_path=str(aoa_path), conc_path=str(conc_path),
        aoa_n=len(aoa), conc_n=len(conc),
    )


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def _strip_non_speech(text: str) -> str:
    """Remove bracketed/parenthetical stage directions and speaker labels."""
    text = _BRACKET_RE.sub(' ', text)
    text = _PAREN_RE.sub(' ', text)
    text = _SPEAKER_RE.sub(' ', text)
    return re.sub(r'  +', ' ', text).strip()


# ---------------------------------------------------------------------------
# spaCy pipeline (lazily loaded, cached at module level)
# ---------------------------------------------------------------------------

_nlp: Any = None


def _get_nlp() -> Any:
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load(_SPACY_MODEL, disable=["ner"])
        except OSError:
            raise RuntimeError(
                f"spaCy model '{_SPACY_MODEL}' not found.\n"
                f"Run:  python -m spacy download {_SPACY_MODEL}"
            )
    return _nlp


def _process(text: str) -> tuple[str, list[str]]:
    """Run spaCy on text; return (sentence-rejoined full text, content token list).

    Content tokens are lemmatized, lowercase, from NOUN/VERB/ADJ/ADV only.
    PROPN is excluded — see module docstring for rationale.
    """
    nlp = _get_nlp()
    doc = nlp(text)
    full_text     = " ".join(sent.text.strip() for sent in doc.sents)
    content_tokens = [
        tok.lemma_.lower()
        for tok in doc
        if tok.pos_ in _CONTENT_POS
        and not tok.is_punct
        and not tok.is_space
        and len(tok.lemma_) > 1
    ]
    return full_text, content_tokens


# ---------------------------------------------------------------------------
# Metric groups
# ---------------------------------------------------------------------------

def compute_readability(full_text: str) -> dict[str, Any]:
    """Run six textstat readability formulas on the cleaned full text.

    Returns None values when text is too short to be reliable.
    These formulas were validated on written prose; treat results as a relative
    complexity index across shows, not a literal grade-level prediction.
    """
    import textstat

    word_count = len(full_text.split())
    if word_count < _MIN_WORDS_FOR_READABILITY:
        return {
            "flesch_reading_ease":          None,
            "flesch_kincaid_grade":         None,
            "spache_readability":           None,
            "dale_chall_readability_score": None,
            "coleman_liau_index":           None,
            "automated_readability_index":  None,
            "readability_note": (
                f"text too short ({word_count} words; "
                f"minimum {_MIN_WORDS_FOR_READABILITY})"
            ),
        }

    return {
        "flesch_reading_ease":          round(textstat.flesch_reading_ease(full_text), 2),
        "flesch_kincaid_grade":         round(textstat.flesch_kincaid_grade(full_text), 2),
        "spache_readability":           round(textstat.spache_readability(full_text), 2),
        "dale_chall_readability_score": round(textstat.dale_chall_readability_score(full_text), 2),
        "coleman_liau_index":           round(textstat.coleman_liau_index(full_text), 2),
        "automated_readability_index":  round(textstat.automated_readability_index(full_text), 2),
        "readability_note": None,
    }


def compute_vocabulary(tokens: list[str], norms: NormTables) -> dict[str, Any]:
    """Compute Zipf frequency tiers, AoA, and concreteness for content tokens.

    Out-of-norm-list words are excluded from means; coverage is reported
    separately so low-coverage episodes are visible rather than hidden.
    """
    from wordfreq import zipf_frequency

    n = len(tokens)
    if n == 0:
        return {"vocabulary_note": "no content tokens extracted"}

    zipf_scores = [zipf_frequency(t, 'en') for t in tokens]
    mean_zipf   = sum(zipf_scores) / n

    tier1 = sum(1 for z in zipf_scores if z >= ZIPF_TIER1_GE)
    tier2 = sum(1 for z in zipf_scores if ZIPF_TIER2_GE <= z < ZIPF_TIER1_GE)
    tier3 = sum(1 for z in zipf_scores if z < ZIPF_TIER3_LT)

    # AoA — Kuperman norms, exclude OOL, report coverage
    aoa_hits      = [norms.aoa[t] for t in tokens if t in norms.aoa]
    aoa_mean      = sum(aoa_hits) / len(aoa_hits) if aoa_hits else None
    aoa_coverage  = len(aoa_hits) / n

    # Concreteness — Brysbaert norms, same pattern
    conc_hits      = [norms.concreteness[t] for t in tokens if t in norms.concreteness]
    conc_mean      = sum(conc_hits) / len(conc_hits) if conc_hits else None
    conc_coverage  = len(conc_hits) / n

    return {
        "content_token_count":         n,
        "mean_zipf":                   round(mean_zipf, 4),
        "pct_below_zipf_3":            round(tier3 / n, 4),
        "tier1_proportion":            round(tier1 / n, 4),
        "tier2_proportion":            round(tier2 / n, 4),
        "tier3_proportion":            round(tier3 / n, 4),
        "tier2_plus_tier3_proportion": round((tier2 + tier3) / n, 4),
        "aoa_mean":                    round(aoa_mean, 4) if aoa_mean is not None else None,
        "aoa_coverage":                round(aoa_coverage, 4),
        "concreteness_mean":           round(conc_mean, 4) if conc_mean is not None else None,
        "concreteness_coverage":       round(conc_coverage, 4),
        "vocabulary_note":             None,
    }


def compute_diversity(tokens: list[str]) -> dict[str, Any]:
    """Compute MTLD lexical diversity (length-robust; preferred over raw TTR)."""
    if len(tokens) < _MIN_TOKENS_FOR_DIVERSITY:
        return {
            "mtld": None,
            "diversity_note": (
                f"insufficient tokens for MTLD "
                f"({len(tokens)} < {_MIN_TOKENS_FOR_DIVERSITY} minimum)"
            ),
        }
    try:
        from lexical_diversity import lex_div as ld
        return {"mtld": round(ld.mtld(tokens), 4), "diversity_note": None}
    except Exception as exc:
        return {"mtld": None, "diversity_note": f"MTLD failed: {exc}"}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class VocabResult:
    episode_id: str
    cc_path: str
    status: str = "ok"   # "ok" | "failed" | "skipped"
    error: str = ""
    word_count: int = 0
    content_token_count: int = 0
    readability: dict = field(default_factory=dict)
    vocabulary:  dict = field(default_factory=dict)
    diversity:   dict = field(default_factory=dict)
    manifest:    dict = field(default_factory=dict)

    def to_flat_row(self) -> dict[str, Any]:
        """Flatten all metric groups into one CSV-ready dict."""
        row: dict[str, Any] = {
            "episode_id":          self.episode_id,
            "cc_path":             self.cc_path,
            "status":              self.status,
            "word_count":          self.word_count,
            "content_token_count": self.content_token_count,
        }
        row.update({f"read_{k}":  v for k, v in self.readability.items()})
        row.update({f"vocab_{k}": v for k, v in self.vocabulary.items()})
        row.update({f"div_{k}":   v for k, v in self.diversity.items()})
        return row


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------

def _build_manifest(
    episode_id: str,
    cc_path: str,
    word_count: int,
    content_token_count: int,
    aoa_coverage: float | None,
    conc_coverage: float | None,
    norms: NormTables,
) -> dict:
    return {
        "module":       "vocab_complexity",
        "version":      __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "episode_id":   episode_id,
        "cc_path":      cc_path,
        "library_versions": {
            "wordfreq":          _pkg_version("wordfreq"),
            "textstat":          _pkg_version("textstat"),
            "spacy":             _pkg_version("spacy"),
            "spacy_model":       _SPACY_MODEL,
            "lexical_diversity": _pkg_version("lexical-diversity"),
        },
        "norm_files": {
            "kuperman_aoa":           norms.aoa_path,
            "brysbaert_concreteness": norms.conc_path,
            "kuperman_entries":       norms.aoa_n,
            "brysbaert_entries":      norms.conc_n,
        },
        "zipf_tier_thresholds": {
            "tier1_ge": ZIPF_TIER1_GE,
            "tier2_ge": ZIPF_TIER2_GE,
            "tier3_lt": ZIPF_TIER3_LT,
        },
        "preprocessing_steps": [
            "timestamps and SRT sequence numbers stripped",
            "bracketed cues stripped (e.g. [MUSIC], [APPLAUSE])",
            "parenthetical cues stripped (e.g. (laughs), (gasps))",
            "speaker labels stripped (ALL CAPS: pattern)",
            "text re-segmented into sentences via spaCy en_core_web_sm",
            "tokens lemmatized via spaCy",
            "proper nouns (PROPN) excluded from vocabulary measures",
            "content words: NOUN, VERB, ADJ, ADV only",
            "out-of-norm-list words excluded from means; coverage reported separately",
        ],
        "token_counts": {
            "total_words":           word_count,
            "content_tokens":        content_token_count,
            "aoa_coverage":          aoa_coverage,
            "concreteness_coverage": conc_coverage,
        },
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_caption_file(
    cc_path: Path,
    episode_id: str = "",
    norms: NormTables | None = None,
) -> VocabResult:
    """Analyze a single .srt or .vtt caption file.

    Args:
        cc_path:    Path to the caption file.
        episode_id: Label for this episode. Defaults to the file stem.
        norms:      Pre-loaded NormTables. Pass a shared instance across
                    batch runs to avoid re-reading the CSV files each time.
                    If None, loads from the default data/norms/ path.

    Returns:
        VocabResult with status "ok", "skipped" (empty track), or "failed".
    """
    cc_path    = Path(cc_path)
    episode_id = episode_id or cc_path.stem

    if not cc_path.exists():
        return VocabResult(
            episode_id=episode_id, cc_path=str(cc_path),
            status="failed", error=f"File not found: {cc_path}",
        )

    if norms is None:
        norms = load_norms()

    try:
        from .speech import extract_cc_text

        raw_text = extract_cc_text(cc_path)
        if not raw_text.strip():
            return VocabResult(
                episode_id=episode_id, cc_path=str(cc_path),
                status="skipped", error="Empty caption track after parsing",
            )

        clean_text = _strip_non_speech(raw_text)
        if not clean_text.strip():
            return VocabResult(
                episode_id=episode_id, cc_path=str(cc_path),
                status="skipped", error="No dialogue text after stripping non-speech content",
            )

        full_text, content_tokens = _process(clean_text)
        word_count = len(full_text.split())

        readability = compute_readability(full_text)
        vocabulary  = compute_vocabulary(content_tokens, norms)
        diversity   = compute_diversity(content_tokens)

        aoa_coverage  = vocabulary.get("aoa_coverage")
        conc_coverage = vocabulary.get("concreteness_coverage")

        manifest = _build_manifest(
            episode_id, str(cc_path),
            word_count, len(content_tokens),
            aoa_coverage, conc_coverage, norms,
        )

        return VocabResult(
            episode_id=episode_id,
            cc_path=str(cc_path),
            status="ok",
            word_count=word_count,
            content_token_count=len(content_tokens),
            readability=readability,
            vocabulary=vocabulary,
            diversity=diversity,
            manifest=manifest,
        )

    except Exception as exc:
        import traceback
        return VocabResult(
            episode_id=episode_id, cc_path=str(cc_path),
            status="failed",
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        )


def batch_analyze(
    cc_paths: list[Path],
    norms: NormTables | None = None,
    out_dir: Path | None = None,
) -> tuple[list[VocabResult], dict[str, Path]]:
    """Analyze a list of caption files; write a CSV row-file and a JSON manifest.

    Returns:
        (results, paths) where paths["csv"] and paths["manifest"] are the output files.
    """
    import pandas as pd

    if norms is None:
        norms = load_norms()

    results: list[VocabResult] = []
    for i, p in enumerate(cc_paths, 1):
        print(f"[vocab] {i}/{len(cc_paths)}  {p.name}", flush=True)
        results.append(analyze_caption_file(p, norms=norms))

    if out_dir is None:
        ts      = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        out_dir = Path(f"_vocab_{ts}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    csv_path = Path(out_dir) / "vocab_complexity.csv"
    pd.DataFrame([r.to_flat_row() for r in results]).to_csv(csv_path, index=False)

    ok_results = [r for r in results if r.status == "ok"]
    manifest = {
        "module":       "vocab_complexity",
        "version":      __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total":        len(results),
        "ok":           len(ok_results),
        "failed":       sum(1 for r in results if r.status == "failed"),
        "skipped":      sum(1 for r in results if r.status == "skipped"),
        "per_episode":  [r.manifest for r in results if r.manifest],
    }
    manifest_path = Path(out_dir) / "vocab_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return results, {"csv": csv_path, "manifest": manifest_path}
