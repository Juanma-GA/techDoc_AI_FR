"""Fallback NLP rules — deterministic regex patterns for when LLM is disabled (HR4/HR7).

corpus-agent uses LLM-first rules (via checklist). doc-reviewer combines:
  - Built-in catalogs (ASD-STE100, MAT10000, ATA 100): deterministic ✓
  - Custom regex/term rules: deterministic ✓
  - Unit conversions: deterministic ✓
  - Checklist NLP rules (llm_nl): LLM-dependent ✗

This module provides fallback coverage for checklist NLP rules when LLM is OFF:
~10 simple regex patterns covering ~50% of common writing issues (passive voice,
intensifiers, multiple punctuation, ALL CAPS, etc). When LLM is disabled, these
patterns are applied, returning partial results with llm_used=false (HR7 transparency).

AACF Compliance:
  - HR4: Fallback is explicit, logged, and deterministic.
  - HR7: Results are returned with llm_used=false (transparent to UI).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class FallbackMatch:
    """A single regex match for a writing issue."""
    pattern_name: str
    line_number: int
    column: int
    matched_text: str
    suggestion: str


class FallbackNLPRules:
    """Deterministic regex-based fallback for NLP rule detection."""

    @staticmethod
    def detect_passive_voice(text: str, page: int = 1) -> list[FallbackMatch]:
        """Detect passive voice constructions: "was written", "is done", etc.
        
        Pattern: past participle ending in -ed, typically preceded by "is/was/are/were/be".
        Limitation: simple heuristic, not 100% accurate (e.g., 'used' as adjective).
        """
        results = []
        pattern = r'\b(?:is|was|are|were|be|being)\s+([a-z]+ed)\b'
        for line_num, line in enumerate(text.split('\n'), start=1):
            for match in re.finditer(pattern, line, re.IGNORECASE):
                col = match.start()
                verb = match.group(1)
                results.append(FallbackMatch(
                    pattern_name="passive_voice",
                    line_number=page * 1000 + line_num,  # Fake "page" encoding
                    column=col,
                    matched_text=match.group(0),
                    suggestion=f"Rewrite in active voice (avoid: '{verb}')"
                ))
        return results

    @staticmethod
    def detect_intensifiers(text: str, page: int = 1) -> list[FallbackMatch]:
        """Detect intensifier words: very, extremely, really, quite, rather, etc.
        
        Technical writing prefers precise quantification over subjective intensifiers.
        """
        results = []
        intensifiers = ['very', 'extremely', 'really', 'quite', 'rather', 'somewhat',
                       'quite', 'fairly', 'pretty', 'so', 'much', 'highly']
        pattern = r'\b(' + '|'.join(intensifiers) + r')\b'
        for line_num, line in enumerate(text.split('\n'), start=1):
            for match in re.finditer(pattern, line, re.IGNORECASE):
                col = match.start()
                intensifier = match.group(1)
                results.append(FallbackMatch(
                    pattern_name="intensifier",
                    line_number=page * 1000 + line_num,
                    column=col,
                    matched_text=intensifier,
                    suggestion="Use precise quantification instead (e.g., '50%', 'twice as')"
                ))
        return results

    @staticmethod
    def detect_multiple_punctuation(text: str, page: int = 1) -> list[FallbackMatch]:
        """Detect multiple punctuation marks in a row: !!, ..., ?!?, etc.
        
        Informal style; technical docs use single punctuation.
        """
        results = []
        pattern = r'[.!?]{2,}'
        for line_num, line in enumerate(text.split('\n'), start=1):
            for match in re.finditer(pattern, line):
                col = match.start()
                results.append(FallbackMatch(
                    pattern_name="multiple_punctuation",
                    line_number=page * 1000 + line_num,
                    column=col,
                    matched_text=match.group(0),
                    suggestion="Use single punctuation mark"
                ))
        return results

    @staticmethod
    def detect_all_caps_words(text: str, page: int = 1) -> list[FallbackMatch]:
        """Detect sequences of ALL CAPS (not acronyms).
        
        Pattern: 3+ uppercase letters in a row (excludes common acronyms like 'PDF', 'URL').
        """
        results = []
        # Allow 1-2 char acronyms (OK: "A", "AB"), flag 3+ (CAPS)
        pattern = r'\b[A-Z]{3,}\b'
        common_acronyms = {'PDF', 'URL', 'API', 'XML', 'HTML', 'JSON', 'CSV', 'USA',
                          'UK', 'DGTP', 'ASD', 'STE', 'ATA', 'ISO', 'S1000D'}
        for line_num, line in enumerate(text.split('\n'), start=1):
            for match in re.finditer(pattern, line):
                word = match.group(0)
                if word not in common_acronyms:
                    col = match.start()
                    results.append(FallbackMatch(
                        pattern_name="all_caps_word",
                        line_number=page * 1000 + line_num,
                        column=col,
                        matched_text=word,
                        suggestion=f"Use title case ('{word.capitalize()}')"
                    ))
        return results

    @staticmethod
    def detect_weak_words(text: str, page: int = 1) -> list[FallbackMatch]:
        """Detect weak/filler words: things, stuff, basically, essentially, etc."""
        results = []
        weak_words = ['things', 'stuff', 'basically', 'essentially', 'actually', 'literally',
                     'sort of', 'kind of', 'perhaps', 'maybe']
        pattern = r'\b(' + '|'.join(weak_words) + r')\b'
        for line_num, line in enumerate(text.split('\n'), start=1):
            for match in re.finditer(pattern, line, re.IGNORECASE):
                col = match.start()
                weak = match.group(1)
                results.append(FallbackMatch(
                    pattern_name="weak_word",
                    line_number=page * 1000 + line_num,
                    column=col,
                    matched_text=weak,
                    suggestion=f"Replace '{weak.lower()}' with precise wording"
                ))
        return results

    @staticmethod
    def detect_contractions(text: str, page: int = 1) -> list[FallbackMatch]:
        """Detect contractions: don't, can't, won't, etc.
        
        Technical writing typically avoids contractions.
        """
        results = []
        contractions = ["don't", "doesn't", "didn't", "can't", "couldn't", "won't",
                       "wouldn't", "isn't", "aren't", "wasn't", "weren't", "haven't",
                       "hasn't", "hadn't", "shouldn't", "couldn't", "mightn't", "mustn't"]
        pattern = r'\b(' + '|'.join(re.escape(c) for c in contractions) + r')\b'
        for line_num, line in enumerate(text.split('\n'), start=1):
            for match in re.finditer(pattern, line, re.IGNORECASE):
                col = match.start()
                contraction = match.group(1)
                expanded = contraction.replace("'", " ").replace("nt", "not")
                results.append(FallbackMatch(
                    pattern_name="contraction",
                    line_number=page * 1000 + line_num,
                    column=col,
                    matched_text=contraction,
                    suggestion=f"Expand: '{contraction}' → '{expanded.lower()}'"
                ))
        return results

    @staticmethod
    def detect_vague_quantifiers(text: str, page: int = 1) -> list[FallbackMatch]:
        """Detect vague quantifiers: many, few, some, several, etc.
        
        Technical writing prefers precise numbers or percentages.
        """
        results = []
        vague_qs = ['many', 'few', 'several', 'some', 'numerous', 'countless',
                   'a lot', 'lots of', 'plenty']
        pattern = r'\b(' + '|'.join(re.escape(q) for q in vague_qs) + r')\b'
        for line_num, line in enumerate(text.split('\n'), start=1):
            for match in re.finditer(pattern, line, re.IGNORECASE):
                col = match.start()
                quantifier = match.group(1)
                results.append(FallbackMatch(
                    pattern_name="vague_quantifier",
                    line_number=page * 1000 + line_num,
                    column=col,
                    matched_text=quantifier,
                    suggestion="Use precise number or percentage (e.g., '5 items', '75%')"
                ))
        return results

    @staticmethod
    def analyze_all(text: str, page: int = 1) -> list[dict[str, Any]]:
        """Run all fallback patterns and return flattened result list.
        
        Returns: list of dicts compatible with Suggestion schema.
        """
        all_matches: list[FallbackMatch] = []
        all_matches.extend(FallbackNLPRules.detect_passive_voice(text, page))
        all_matches.extend(FallbackNLPRules.detect_intensifiers(text, page))
        all_matches.extend(FallbackNLPRules.detect_multiple_punctuation(text, page))
        all_matches.extend(FallbackNLPRules.detect_all_caps_words(text, page))
        all_matches.extend(FallbackNLPRules.detect_weak_words(text, page))
        all_matches.extend(FallbackNLPRules.detect_contractions(text, page))
        all_matches.extend(FallbackNLPRules.detect_vague_quantifiers(text, page))

        return [
            {
                "pattern": m.pattern_name,
                "line": m.line_number,
                "column": m.column,
                "text": m.matched_text,
                "suggestion": m.suggestion,
            }
            for m in all_matches
        ]
