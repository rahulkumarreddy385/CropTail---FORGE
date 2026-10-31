"""L12 optional photo tag. A hint only, never a diagnosis. Returns (None, None) without a key."""
import base64

from ai import llm
from config.rules import VISION_TAGS

SYSTEM = (f"Look at this farm field photo and return JSON {{\"vision_tag\": one of {VISION_TAGS}, "
          "\"vision_confidence\": 0-1}. Describe only what is visible (standing water, flattened crop, "
          "chewed leaves, healthy green crop). Do not name diseases or treatments. If unsure use \"unclear\".")


def tag_photo(path: str, media_type: str) -> tuple[str | None, float | None]:
    if not llm.enabled() or media_type not in ("image/jpeg", "image/png"):
        return None, None
    try:
        data = base64.b64encode(open(path, "rb").read()).decode()
        out = llm.json_completion(SYSTEM, [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
            {"type": "text", "text": "Tag this photo."}], max_tokens=100)
        tag, conf = out.get("vision_tag"), float(out.get("vision_confidence") or 0)
        if tag not in VISION_TAGS or conf < 0.6:
            tag = "unclear"
        return tag, round(conf, 2)
    except Exception:
        return None, None
