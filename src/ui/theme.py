"""
Global design-system theme for the app (shadcn-style semantic tokens).

The QSS template lives in assets/styles/base.qss and references {token}
placeholders. This module renders it per theme and is the single source of
truth for colors — no hex literals should live anywhere else.
"""
import os
import re

from resource_utils import get_resource_path

# ── Semantic tokens (shadcn-style) ──────────────────────────────────────────
LIGHT = {
    # Core
    "background": "#FAFAFA",
    "foreground": "#09090B",
    "card": "#FFFFFF",
    "popover": "#FFFFFF",
    "primary": "#000000",
    "primary_foreground": "#FFFFFF",
    "muted": "#F4F4F5",
    "muted_alt": "#F4F4F5",
    "muted_alt2": "#F4F4F5",
    "muted_foreground": "#71717A",
    "muted_fg_static": "#71717A",
    "muted_icon": "#71717A",
    "subtle_foreground": "#52525B",
    "subtle_icon": "#52525B",
    "subtle_border": "#52525B",
    "border": "#E4E4E7",
    "border_strong": "#D4D4D8",
    "border_inverse": "#27272A",
    "border_inverse2": "#3F3F46",
    "border_muted": "#27272A",
    "input": "#E4E4E7",
    "ring": "#71717A",
    "static_gray": "#09090B",
    "foreground_inverse": "#09090B",
    "foreground_high": "#18181B",
    "foreground_faint": "#09090B",
    # Surfaces beyond the base scale
    "surface_alt": "#FFFFFF",
    "surface_alt_fa": "#FAFAFA",
    "surface_subtle": "#FAFAFA",
    "surface_deep": "#FAFAFA",
    "surface_card_text": "#FAFAFA",
    "surface_fg_inv": "#09090B",
    # Success
    "success": "#10B981",
    "success_fg": "#059669",
    "success_surface": "#D1FAE5",
    "success_border": "#A7F3D0",
    # Warning
    "warning": "#D97706",
    "warning_surface": "#FEF3C7",
    "warning_border": "#FDE68A",
    "warning_surface_alt": "#FEE2E2",
    # Destructive
    "destructive_solid": "#DC2626",
    "destructive_const": "#EF4444",
    "destructive_fg": "#DC2626",
    "destructive_fg2": "#EF4444",
    "destructive_pressed": "#DC2626",
    "destructive_surface": "#FEE2E2",
    "destructive_surface_pressed": "#FEE2E2",
    "destructive_border": "#FCA5A5",
    "destructive_border2": "#FECACA",
    "destructive_hover": "#FEF2F2",
    # Scrollbars
    "scrollbar": "#A1A1AA",
    "scrollbar_hover": "#A1A1AA",
    "scrollbar_pressed": "#A1A1AA",
    # Destructive ring/track (rgba)
    "destructive_ring": "rgba(220, 38, 38, 0.35)",
    "destructive_ring_hover": "rgba(220, 38, 38, 0.08)",
    "destructive_ring_active": "rgba(220, 38, 38, 0.16)",
    # Theme-dependent icons
    "icon_chevron": "chevron_down_black.png",
    "icon_checkbox": "check_white.png",
    # Accent (brand blue) + soft selection fills
    "accent": "#3B82F6",
    "accent_soft": "rgba(59, 130, 246, 0.12)",
    "accent_soft_hover": "rgba(59, 130, 246, 0.08)",
    "selected_text": "#1D4ED8",
}

DARK = {
    # Core
    "background": "#000000",
    "foreground": "#EDEDED",
    "card": "#09090B",
    "popover": "#18181B",
    "primary": "#FFFFFF",
    "primary_foreground": "#000000",
    "muted": "#18181B",
    "muted_alt": "#27272A",
    "muted_alt2": "#121215",
    "muted_foreground": "#A1A1AA",
    "muted_fg_static": "#71717A",
    "muted_icon": "#52525B",
    "subtle_foreground": "#A1A1AA",
    "subtle_icon": "#71717A",
    "subtle_border": "#D4D4D8",
    "border": "#27272A",
    "border_strong": "#3F3F46",
    "border_inverse": "#E4E4E7",
    "border_inverse2": "#D4D4D8",
    "border_muted": "#D4D4D8",
    "input": "#27272A",
    "ring": "#A1A1AA",
    "static_gray": "#09090B",
    "foreground_inverse": "#FFFFFF",
    "foreground_high": "#E4E4E7",
    "foreground_faint": "#D4D4D8",
    # Surfaces beyond the base scale
    "surface_alt": "#121214",
    "surface_alt_fa": "#121214",
    "surface_subtle": "#18181B",
    "surface_deep": "#0C0C0E",
    "surface_card_text": "#09090B",
    "surface_fg_inv": "#FAFAFA",
    # Success
    "success": "#10B981",
    "success_fg": "#10B981",
    "success_surface": "#022C22",
    "success_border": "#065F46",
    # Warning
    "warning": "#F59E0B",
    "warning_surface": "#1C1917",
    "warning_border": "#78350F",
    "warning_surface_alt": "#1C1917",
    # Destructive
    "destructive_solid": "#EF4444",
    "destructive_const": "#EF4444",
    "destructive_fg": "#F87171",
    "destructive_fg2": "#FFFFFF",
    "destructive_pressed": "#991B1B",
    "destructive_surface": "#3F1414",
    "destructive_surface_pressed": "#991B1B",
    "destructive_border": "#7F1D1D",
    "destructive_border2": "#7F1D1D",
    "destructive_hover": "#7F1D1D",
    # Scrollbars
    "scrollbar": "#52525B",
    "scrollbar_hover": "#3F3F46",
    "scrollbar_pressed": "#71717A",
    # Destructive ring/track (rgba)
    "destructive_ring": "rgba(239, 68, 68, 0.4)",
    "destructive_ring_hover": "rgba(239, 68, 68, 0.12)",
    "destructive_ring_active": "rgba(239, 68, 68, 0.22)",
    # Theme-dependent icons
    "icon_chevron": "chevron_down_white.png",
    "icon_checkbox": "check_black.png",
    # Accent (brand blue) + soft selection fills
    "accent": "#3B82F6",
    "accent_soft": "rgba(59, 130, 246, 0.22)",
    "accent_soft_hover": "rgba(59, 130, 246, 0.12)",
    "selected_text": "#FFFFFF",
}

_cache = {}


def get_tokens(is_dark: bool) -> dict:
    return dict(DARK if is_dark else LIGHT)


def render_qss(is_dark: bool) -> str:
    """Render the global stylesheet with semantic tokens substituted."""
    if is_dark in _cache:
        return _cache[is_dark]
    path = get_resource_path(os.path.join("assets", "styles", "base.qss"))
    with open(path, "r", encoding="utf-8") as f:
        tpl = f.read()
    tokens = get_tokens(is_dark)

    def _sub(match):
        name = match.group(1)
        value = tokens.get(name)
        if value is None:
            raise KeyError(f"Unknown theme token: {name}")
        return value

    out = re.sub(r"\{([a-z_][a-z0-9_]*)\}", _sub, tpl)
    _cache[is_dark] = out
    return out


def clear_cache():
    _cache.clear()
