"""Point d'entrée Vercel : la classe App sert les routes /api."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import App


class handler(App):
    """Nom exigé par l'analyse statique de Vercel (classe, pas un alias)."""
