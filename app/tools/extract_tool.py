import re
from typing import Dict, List
from app.pydantic_models import ExtractedIntelligence

_UPI = re.compile(r"\b[a-z0-9.\-_]{2,}@[a-z0-9]{2,}\b", re.I)
_URL = re.compile(r"\bhttps?://[^\s]+|\bwww\.[^\s]+", re.I)
_PHONE = re.compile(r"\b(?:\+?\d{1,3}[\s\-]?)?(?:\d[\s\-]?){9,12}\b")
_ACCT = re.compile(r"\b\d{9,18}\b")  # loose on purpose

def extract_entities(text: str) -> Dict[str, List[str]]:
    return {
        "upiIds": _UPI.findall(text),
        "phishingLinks": _URL.findall(text),
        "phoneNumbers": [p.strip() for p in _PHONE.findall(text)],
        "bankAccounts": _ACCT.findall(text),
    }

def merge_unique(
    existing: ExtractedIntelligence,
    new_bits: dict
) -> ExtractedIntelligence:
    """
    Merge new extracted intel into the existing Pydantic model in-place.
    """
    field_map = {
        "upiIds": "upiIds",
        "bankAccounts": "bankAccounts",
        "phishingLinks": "phishingLinks",
        "phoneNumbers": "phoneNumbers",
        # suspiciousKeywords can be added later if needed
    }
    for field_name in field_map.values():
        existing_list = getattr(existing, field_name, [])
        seen = set(existing_list)

        for v in new_bits.get(field_name, []):
            if v not in seen:
                existing_list.append(v)
                seen.add(v)

        # setattr not strictly required because list is mutated,
        # but keeping it explicit is clearer
        setattr(existing, field_name, existing_list)
    return existing

