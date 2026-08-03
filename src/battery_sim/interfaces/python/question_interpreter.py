"""Conservative, evidence-preserving extraction from engineering questions.

This module deliberately does not try to be a general natural-language
understanding system. It only recognizes vocabulary that can be mapped to a
stable battery_sim contract and returns the exact source span for every match.
"""

from dataclasses import dataclass
import re
from typing import Any, Iterable

from battery_sim.core.cell import Cell
from battery_sim.core.result import Signal


@dataclass(frozen=True)
class Evidence:
    """One exact value extracted from a user question."""

    value: Any
    text: str
    start: int
    end: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "evidence": self.text,
            "span": [self.start, self.end],
            "method": "exact_vocabulary_match",
        }


@dataclass(frozen=True)
class QuestionInterpretation:
    """Structured fields supported by exact evidence in the question."""

    fields: dict[str, Evidence]

    def value(self, field_name: str) -> Any:
        evidence = self.fields.get(field_name)
        return evidence.value if evidence else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "conservative_exact_extraction",
            "fields": {
                name: evidence.to_dict()
                for name, evidence in self.fields.items()
            },
            "unsupported_inference": (
                "Text without an exact supported match is not converted into a simulation input."
            ),
        }


class QuestionInterpreter:
    """Recognize a small bilingual engineering vocabulary without guessing."""

    _MODEL_PATTERNS = (
        ("single_particle_electrolyte", re.compile(r"\bSPMe\b", re.IGNORECASE)),
        ("doyle_fuller_newman", re.compile(r"\bDFN\b", re.IGNORECASE)),
        ("single_particle", re.compile(r"\bSPM\b", re.IGNORECASE)),
    )
    _INVESTIGATION_PATTERNS = (
        (
            "cccv_charge",
            re.compile(r"\b(?:CC[- ]?CV|charge\s+CC[- ]?CV)\b", re.IGNORECASE),
        ),
        (
            "cc_discharge",
            re.compile(r"\b(?:discharge|décharge|decharge)\b", re.IGNORECASE),
        ),
        ("rest", re.compile(r"\b(?:rest|repos)\b", re.IGNORECASE)),
    )
    _TEMPERATURE_PATTERN = re.compile(
        r"(?:\b(?:at|à)\s+|\b(?:temperature|température)\s*(?:=|:|de|of|at|à)?\s*)"
        r"(?P<context_value>[+-]?\d+(?:[.,]\d+)?)\s*°?\s*C\b"
        r"|(?P<degree_value>[+-]?\d+(?:[.,]\d+)?)\s*°\s*C\b",
        re.IGNORECASE,
    )
    _SIGNAL_PATTERNS = (
        (Signal.ELECTROLYTE_CONCENTRATION, r"concentration\s+(?:de\s+l['’])?électrolyte|electrolyte\s+concentration"),
        (Signal.ELECTROLYTE_POTENTIAL, r"potentiel\s+(?:de\s+l['’])?électrolyte|electrolyte\s+potential"),
        (Signal.CELL_TEMPERATURE, r"température\s+(?:de\s+la\s+)?cellule|cell\s+temperature"),
        (Signal.VOLTAGE, r"\b(?:voltage|tension)\b"),
        (Signal.CURRENT, r"\b(?:current|courant)\b"),
        (Signal.POWER, r"\b(?:power|puissance)\b"),
        (Signal.SOC, r"\bSOC\b|état\s+de\s+charge|state\s+of\s+charge"),
        (Signal.TEMPERATURE, r"\b(?:temperature|température)\b"),
        (Signal.ENERGY, r"\b(?:energy|énergie)\b"),
        (Signal.HEAT_GENERATION, r"génération\s+de\s+chaleur|heat\s+generation"),
        (Signal.INTERNAL_RESISTANCE, r"résistance\s+interne|internal\s+resistance"),
        (Signal.SEI_THICKNESS, r"épaisseur\s+(?:de\s+la\s+)?SEI|SEI\s+thickness"),
    )

    def interpret(self, question: str) -> QuestionInterpretation:
        fields: dict[str, Evidence] = {}
        self._extract_preset(question, fields)
        self._extract_first(question, "model", self._MODEL_PATTERNS, fields)
        self._extract_first(
            question,
            "investigation_type",
            self._INVESTIGATION_PATTERNS,
            fields,
        )
        self._extract_temperature(question, fields)
        self._extract_signals(question, fields)
        return QuestionInterpretation(fields=fields)

    @staticmethod
    def _extract_preset(question: str, fields: dict[str, Evidence]) -> None:
        matches = []
        for preset_name in Cell.list_presets():
            match = re.search(re.escape(preset_name), question, re.IGNORECASE)
            if match:
                matches.append((match.start(), -len(match.group(0)), preset_name, match))
        if not matches:
            return
        _, _, preset_name, match = sorted(matches)[0]
        fields["preset_name"] = Evidence(
            value=preset_name,
            text=match.group(0),
            start=match.start(),
            end=match.end(),
        )

    @staticmethod
    def _extract_first(
        question: str,
        field_name: str,
        patterns: Iterable[tuple[Any, re.Pattern]],
        fields: dict[str, Evidence],
    ) -> None:
        matches = []
        for value, pattern in patterns:
            match = pattern.search(question)
            if match:
                matches.append((match.start(), value, match))
        if not matches:
            return
        _, value, match = sorted(matches, key=lambda item: item[0])[0]
        fields[field_name] = Evidence(
            value=value,
            text=match.group(0),
            start=match.start(),
            end=match.end(),
        )

    def _extract_temperature(self, question: str, fields: dict[str, Evidence]) -> None:
        match = self._TEMPERATURE_PATTERN.search(question)
        if not match:
            return
        raw_value = match.group("context_value") or match.group("degree_value")
        value = float(raw_value.replace(",", "."))
        fields["temperature_C"] = Evidence(
            value=value,
            text=match.group(0),
            start=match.start(),
            end=match.end(),
        )

    def _extract_signals(self, question: str, fields: dict[str, Evidence]) -> None:
        found: list[tuple[int, Signal, re.Match]] = []
        for signal, pattern_text in self._SIGNAL_PATTERNS:
            match = re.search(pattern_text, question, re.IGNORECASE)
            overlaps_existing = match and any(
                match.start() < existing.end() and existing.start() < match.end()
                for _, _, existing in found
            )
            if match and not overlaps_existing:
                found.append((match.start(), signal, match))
        if not found:
            return
        found.sort(key=lambda item: item[0])
        values = [signal.value for _, signal, _ in found]
        start = found[0][2].start()
        end = found[-1][2].end()
        fields["requested_signals"] = Evidence(
            value=values,
            text=question[start:end],
            start=start,
            end=end,
        )
