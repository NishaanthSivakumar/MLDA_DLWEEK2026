"""
Professor directory with topic-based matching.

Attempts to scrape NUS Statistics faculty page live;
falls back to a curated local JSON snapshot when the site
is unreachable or behind bot-protection.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup

_DIR = Path(__file__).resolve().parent
_FALLBACK_FILE = _DIR / "nus_stat_faculty.json"

_SCRAPE_URL = "https://www.stat.nus.edu.sg/our-people/faculty-members/"


# ------------------------------------------------------------------
# Keyword synonyms / expansion so "perceptron_algorithm" matches
# "machine learning", "neural networks", etc.
# ------------------------------------------------------------------
_TOPIC_SYNONYMS: dict[str, list[str]] = {
    "machine learning":       ["ml", "statistical learning", "learning theory", "classification", "regression",
                                "supervised learning", "unsupervised learning", "clustering", "ensemble"],
    "deep learning":          ["neural networks", "backpropagation", "gradient descent", "perceptron",
                                "convolutional", "recurrent", "transformer", "activation function"],
    "bayesian":               ["bayesian statistics", "bayesian inference", "bayesian methods",
                                "bayesian computation", "posterior", "prior", "mcmc", "markov chain monte carlo"],
    "optimisation":           ["optimization", "gradient descent", "convergence", "loss function",
                                "stochastic gradient", "sgd", "adam", "learning rate"],
    "probability":            ["probability theory", "random variable", "distribution", "expectation",
                                "variance", "law of large numbers", "central limit theorem"],
    "high-dimensional statistics": ["high dimensional", "curse of dimensionality", "variable selection",
                                     "penalised regression", "lasso", "ridge", "regularisation",
                                     "regularization", "sparsity"],
    "information theory":     ["entropy", "mutual information", "kl divergence", "coding theory"],
    "financial modelling":    ["financial econometrics", "risk management", "time series",
                                "volatility", "portfolio", "var", "garch", "financial modelling"],
    "computational statistics": ["monte carlo", "simulation", "bootstrap", "resampling",
                                  "numerical methods", "scalable computation"],
    "reinforcement learning": ["rl", "policy gradient", "q-learning", "markov decision process",
                                "reward", "exploration", "exploitation"],
    "regression":             ["linear regression", "logistic regression", "regression analysis",
                                "ols", "glm", "generalised linear"],
    "neural networks":        ["perceptron", "perceptron_algorithm", "mlp", "feedforward",
                                "backpropagation", "activation"],
    "semiparametric":         ["semiparametric methods", "dimension reduction", "nonparametric"],
    "survival analysis":      ["clinical trials", "biostatistics", "hazard", "kaplan meier"],
}


def _normalise(topic: str) -> str:
    """Lower-case, strip underscores / hyphens."""
    return re.sub(r"[_\-]+", " ", topic.strip().lower())


def _topic_to_keywords(topic: str) -> set[str]:
    """Expand a student topic tag into a broad set of matching keywords."""
    norm = _normalise(topic)
    kws = {norm}
    # Add individual words
    kws.update(norm.split())

    for canonical, synonyms in _TOPIC_SYNONYMS.items():
        all_terms = [canonical] + synonyms
        for term in all_terms:
            if term in norm or norm in term:
                kws.update(all_terms)
                kws.add(canonical)
                break
    return kws


# ------------------------------------------------------------------
# Data loading
# ------------------------------------------------------------------
def _load_fallback() -> list[dict]:
    with open(_FALLBACK_FILE, "r") as f:
        return json.load(f)


def _try_scrape() -> list[dict] | None:
    """Attempt a live scrape.  Return None on any failure."""
    try:
        resp = requests.get(
            _SCRAPE_URL,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        )
        if resp.status_code != 200 or len(resp.text) < 2000:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        # The NUS Stat page typically lists faculty in cards
        # with name in h3/h4 and research areas in a paragraph.
        # Adapt selectors as needed.
        profs: list[dict] = []
        for card in soup.select(".people-card, .team-member, .faculty-member, article"):
            name_tag = card.find(["h3", "h4", "h2"])
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            link_tag = card.find("a", href=True)
            url = link_tag["href"] if link_tag else ""
            # Look for research interests in a <p> or specific class
            areas_text = ""
            for p in card.find_all("p"):
                t = p.get_text(strip=True).lower()
                if "research" in t or "interest" in t:
                    areas_text = p.get_text(strip=True)
                    break
            areas = [a.strip() for a in areas_text.split(",") if a.strip()] if areas_text else []
            profs.append({"name": name, "title": "", "url": url, "research_areas": areas})

        return profs if profs else None
    except Exception:
        return None


def load_faculty() -> list[dict]:
    """Return list of faculty dicts.  Try live scrape, else use fallback JSON."""
    live = _try_scrape()
    if live:
        return live
    return _load_fallback()


# ------------------------------------------------------------------
# Matching logic
# ------------------------------------------------------------------
def _score_prof(prof: dict, student_keywords: set[str]) -> float:
    """Return a 0-1 relevance score between a professor and student keywords."""
    if not prof.get("research_areas"):
        return 0.0

    total = 0.0
    for area in prof["research_areas"]:
        area_norm = _normalise(area)
        area_words = set(area_norm.split())
        # Direct overlap
        overlap = student_keywords & area_words
        if overlap:
            total += len(overlap) / max(len(area_words), 1)
        # Fuzzy substring
        for kw in student_keywords:
            if kw in area_norm or area_norm in kw:
                total += 0.5
                break
            ratio = SequenceMatcher(None, kw, area_norm).ratio()
            if ratio > 0.65:
                total += ratio * 0.3

    # Normalise by number of research areas
    return min(1.0, total / max(len(prof["research_areas"]), 1))


def match_professors(
    strong_topics: list[dict],
    top_n: int = 5,
) -> list[dict]:
    """
    Given a student's strong topics, return professors whose research areas
    overlap, sorted by relevance.

    Each returned dict has keys:
        name, title, url, research_areas, match_score, matched_topics
    """
    if not strong_topics:
        return []

    # Build a combined keyword set from all strong topics
    all_keywords: set[str] = set()
    topic_names: list[str] = []
    for t in strong_topics:
        topic = t.get("topic", "")
        topic_names.append(topic)
        all_keywords |= _topic_to_keywords(topic)

    faculty = load_faculty()
    scored: list[dict] = []

    for prof in faculty:
        score = _score_prof(prof, all_keywords)
        if score < 0.05:
            continue

        # Determine which student topics matched
        matched = []
        for t_name in topic_names:
            t_kws = _topic_to_keywords(t_name)
            for area in prof["research_areas"]:
                area_norm = _normalise(area)
                if t_kws & set(area_norm.split()) or any(k in area_norm for k in t_kws):
                    matched.append(t_name)
                    break

        scored.append({
            **prof,
            "match_score": round(score, 3),
            "matched_topics": list(set(matched)),
        })

    scored.sort(key=lambda p: p["match_score"], reverse=True)
    return scored[:top_n]
