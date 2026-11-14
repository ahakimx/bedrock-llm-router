"""Keyword grading against the golden dataset.

Each expectation is a list of groups; every group must match, and a group matches when any of its
alternatives appears in the answer. Numbers are normalized so "Rp50.000", "Rp50,000" and "50000" match.
"""
import re


def normalize(text: str) -> str:
    t = text.lower().replace(" ", " ")
    # 50.000 / 50,000 / 1.000.000 -> 50000 / 1000000 (thousand separators only, not decimals like 20.00)
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"(\d)[.,](\d{3})(?!\d)", r"\1\2", t)
    return t.replace("rp ", "rp")


def grade(answer: str, expect: list) -> bool:
    a = normalize(answer)
    return all(any(normalize(alt) in a for alt in group) for group in expect)
