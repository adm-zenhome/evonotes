import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("vocabulary_engine")
logger.setLevel(logging.INFO)

CURRENT_DIR = Path(__file__).parent
DEFAULT_LEXICON_PATH = CURRENT_DIR / "data" / "acoustic_lexicon.json"

class AcousticVocabularyEngine:
    """Enterprise acoustic normalization, phonetic error correction and dynamic glossary generator."""

    def __init__(self, lexicon_path: Optional[Path] = None):
        self.lexicon_path = lexicon_path or DEFAULT_LEXICON_PATH
        self.entities: List[Dict[str, Any]] = []
        self._patterns_dict: Dict[str, str] = {}
        self._combined_regex: Optional[re.Pattern] = None
        self.load_lexicon()

    def load_lexicon(self) -> bool:
        """Loads and compiles regex patterns from the structured acoustic lexicon JSON."""
        if not self.lexicon_path.exists():
            logger.warning(f"Lexicon file not found at {self.lexicon_path}. Initializing default in-memory rules.")
            self._load_fallback_entities()
            return False

        try:
            with open(self.lexicon_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.entities = data.get("entities", [])
            self._compile_patterns()
            logger.info(f"Loaded {len(self.entities)} canonical entities ({len(self._patterns_dict)} compiled rules).")
            return True
        except Exception as e:
            logger.error(f"Failed to load acoustic lexicon: {e}. Falling back to default rules.")
            self._load_fallback_entities()
            return False

    def _load_fallback_entities(self):
        """Fallback list in case filesystem is not yet initialized."""
        self.entities = [
            {
                "canonical_name": "Aktie Now",
                "category": "partner",
                "aliases": ["Actian", "Aktienow", "Actie Now", "Actie", "Action Now"],
                "regex_patterns": [r"\bActi[ea]n?\s*Now\b", r"\bActi[ea]n\b", r"\bAktie\s*now\b", r"\bActie\b"],
                "context_hints": ["parceiro Zendesk"]
            },
            {
                "canonical_name": "Vonage",
                "category": "partner",
                "aliases": ["Naga", "Naja", "Vonnage"],
                "regex_patterns": [r"\bNaj[aá]\b", r"\bNaga\b", r"\bVonag[ei]\b"],
                "context_hints": ["telefonia", "ZCC"]
            },
            {
                "canonical_name": "BCR",
                "category": "client",
                "aliases": ["PCR", "B-C-R", "B C R"],
                "regex_patterns": [r"\bPCR\b", r"\bB\s*[-.]?\\s*C\s*[-.]?\\s*R\b"],
                "context_hints": ["cliente"]
            },
            {
                "canonical_name": "Mantiqueira",
                "category": "client",
                "aliases": ["Mandique", "Mantique"],
                "regex_patterns": [r"\bMandique\b", r"\bMantique\b"],
                "context_hints": ["cliente"]
            },
            {
                "canonical_name": "Blue3",
                "category": "partner",
                "aliases": ["Blue 3", "Blue Três"],
                "regex_patterns": [r"\bBlue\s*3\b", r"\bBlue\s*Tr[eê]s\b"],
                "context_hints": ["investimentos"]
            },
            {
                "canonical_name": "ZCC (Zendesk Contact Center)",
                "category": "product",
                "aliases": ["ZCC", "Zendesk Contact Center"],
                "regex_patterns": [r"\bZCC(?!\s*\(\s*Zendesk Contact Center\s*\))\b"],
                "context_hints": ["produto Zendesk"]
            }
        ]
        self._compile_patterns()

    def _compile_patterns(self):
        """Compiles all patterns into a single-pass regex to avoid cascading re-replacement bugs."""
        raw_rules = []

        for entity in self.entities:
            canonical = entity.get("canonical_name", "")
            if not canonical:
                continue

            patterns = list(entity.get("regex_patterns", []))
            aliases = entity.get("aliases", [])

            # Special case for ZCC to prevent self-matching inside "(Zendesk Contact Center)"
            if canonical == "ZCC (Zendesk Contact Center)":
                patterns = [p for p in patterns if p != r"\bZCC\b"]
                patterns.append(r"\bZCC(?!\s*\(\s*Zendesk Contact Center\s*\))\b")

            for alias in aliases:
                if alias.lower() != canonical.lower():
                    escaped_alias = re.escape(alias)
                    pattern_str = rf"\b{escaped_alias}\b"
                    if pattern_str not in patterns:
                        patterns.append(pattern_str)

            for p_str in patterns:
                raw_rules.append((p_str, canonical))

        # Sort rules by pattern length descending
        sorted_rules = sorted(raw_rules, key=lambda x: len(x[0]), reverse=True)

        self._patterns_dict = {}
        group_patterns = []
        for idx, (p_str, canonical) in enumerate(sorted_rules):
            group_name = f"grp_{idx}"
            self._patterns_dict[group_name] = canonical
            group_patterns.append(f"(?P<{group_name}>{p_str})")

        if group_patterns:
            self._combined_regex = re.compile("|".join(group_patterns), re.IGNORECASE)
        else:
            self._combined_regex = None

    def _replace_callback(self, match: re.Match) -> str:
        """Single pass lookup callback."""
        for group_name, matched_val in match.groupdict().items():
            if matched_val is not None and group_name in self._patterns_dict:
                return self._patterns_dict[group_name]
        return match.group(0)

    def normalize_text(self, text: str) -> str:
        """Deterministically normalizes acoustic STT mishearings in a single pass without cascading bugs."""
        if not text or not isinstance(text, str):
            return text or ""
        if not self._combined_regex:
            return text

        return self._combined_regex.sub(self._replace_callback, text)

    def build_prompt_glossary(self) -> str:
        """Generates structured directive block to be injected into the LLM system prompt."""
        if not self.entities:
            return ""

        lines = [
            "=== 🎙️ GLOSSÁRIO ACÚSTICO & NORMALIZAÇÃO DE ENTIDADES (PRIORIDADE ALTA) ===",
            "A transcrição de áudio contém possíveis distorções fonéticas do reconhecimento de voz.",
            "Você DEVE normalizar e mapear rigorosamente as entidades para os nomes canônicos abaixo:"
        ]

        for ent in self.entities:
            name = ent.get("canonical_name")
            category = ent.get("category", "").upper()
            aliases = ", ".join(f'"{a}"' for a in ent.get("aliases", []) if a.lower() != name.lower())
            hints = ", ".join(ent.get("context_hints", []))
            
            cat_str = f"[{category}] " if category else ""
            hint_str = f" (Contexto: {hints})" if hints else ""
            aliases_str = f" — Variações acústicas/STT: {aliases}" if aliases else ""
            
            lines.append(f"- {cat_str}**{name}**{hint_str}{aliases_str}")

        lines.append("NUNCA invente ou altere a grafia desses nomes e marcas.")
        lines.append("==========================================================================")
        return "\n".join(lines)

    def register_or_update_entity(self, canonical_name: str, aliases: List[str], category: str = "general", context_hints: Optional[List[str]] = None) -> bool:
        """Dynamically registers or enriches an entity and persists changes to disk."""
        found = False
        for ent in self.entities:
            if ent.get("canonical_name", "").lower() == canonical_name.lower():
                existing_aliases = set(ent.get("aliases", []))
                existing_aliases.update(aliases)
                ent["aliases"] = sorted(list(existing_aliases), key=len, reverse=True)
                if context_hints:
                    existing_hints = set(ent.get("context_hints", []))
                    existing_hints.update(context_hints)
                    ent["context_hints"] = list(existing_hints)
                found = True
                break

        if not found:
            new_ent = {
                "canonical_name": canonical_name,
                "category": category,
                "aliases": aliases,
                "regex_patterns": [rf"\b{re.escape(a)}\b" for a in aliases if a.lower() != canonical_name.lower()],
                "context_hints": context_hints or []
            }
            self.entities.append(new_ent)

        self._compile_patterns()
        
        # Save to disk
        try:
            self.lexicon_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.lexicon_path, "w", encoding="utf-8") as f:
                json.dump({"version": "1.0.0", "entities": self.entities}, f, indent=2, ensure_ascii=False)
            logger.info(f"Entity '{canonical_name}' registered/updated in {self.lexicon_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving updated lexicon: {e}")
            return False

default_vocab_engine = AcousticVocabularyEngine()

def normalize_text_vocabulary(text: str) -> str:
    """Convenience function backwards-compatible with old import signature."""
    return default_vocab_engine.normalize_text(text)
