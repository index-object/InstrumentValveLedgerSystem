from dataclasses import dataclass
from typing import Optional


@dataclass
class TypeConfig:
    key: str
    code: str
    name: str
    sheet_keywords: list[str]
    column_signatures: list[str]
    weight: int = 10


@dataclass
class ClassificationResult:
    type_key: str
    type_code: str
    type_name: str
    score: int
    matched_by: str


class SheetClassifier:
    EXACT_WEIGHT = 10
    KEYWORD_WEIGHT = 7
    SIGNATURE_WEIGHT = 5

    def __init__(self):
        self._configs: list[TypeConfig] = []

    def register(self, config: TypeConfig) -> None:
        self._configs.append(config)

    def register_from_dict(self, key: str, cfg: dict) -> None:
        self._configs.append(TypeConfig(
            key=key,
            code=cfg.get("code", key),
            name=cfg.get("name", ""),
            sheet_keywords=cfg.get("sheet_keywords", []),
            column_signatures=cfg.get("column_signatures", []),
        ))

    def classify(
        self,
        sheet_name: str,
        headers: Optional[list[str]] = None,
    ) -> Optional[ClassificationResult]:
        best: Optional[ClassificationResult] = None

        for tc in self._configs:
            score = 0
            matched_by = ""

            s = sheet_name.strip() if sheet_name else ""

            if s and s in tc.sheet_keywords:
                score = self.EXACT_WEIGHT
                matched_by = "exact"
            elif s and any(kw in s for kw in tc.sheet_keywords):
                score = self.KEYWORD_WEIGHT
                matched_by = "keyword"

            if headers and score < self.SIGNATURE_WEIGHT:
                sig_score = self._match_signatures(headers, tc.column_signatures)
                if sig_score > score:
                    score = sig_score
                    matched_by = "signature"

            if score > 0 and (best is None or score > best.score):
                best = ClassificationResult(
                    type_key=tc.key,
                    type_code=tc.code,
                    type_name=tc.name,
                    score=score,
                    matched_by=matched_by,
                )

        return best

    def _match_signatures(
        self, headers: list[str], signatures: list[str]
    ) -> int:
        if not signatures:
            return 0
        header_text = " ".join(str(h) for h in headers if h)
        for sig in signatures:
            if sig in header_text:
                return self.SIGNATURE_WEIGHT
        return 0
