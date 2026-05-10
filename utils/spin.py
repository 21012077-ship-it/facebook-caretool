import random
import re

SPIN_RE = re.compile(r"\{([^{}]+)\}")

def spin_text(text: str) -> str:
    def repl(match):
        options = [item.strip() for item in match.group(1).split("|") if item.strip()]
        return random.choice(options) if options else match.group(0)
    return SPIN_RE.sub(repl, text or "")
