import re, ast

data = open('app.py', encoding='utf-8').read()

# Arc Dark → Rose Pine
replacements = [
    # Accent: coral → dusty rose
    ('#ff6b6b', '#eb6f92'),
    ('#ff8e8e', '#f083a0'),
    ('#e05555', '#c45777'),
    # Backgrounds: charcoal → deep purple
    ('#1a1a1a', '#191724'),
    ('#242424', '#1f1d2e'),
    ('#2e2e2e', '#26233a'),
    ('#141414', '#120f1d'),
    ('#1e1e1e', '#191724'),
    ('#333333', '#26233a'),
    ('#2a2a2a', '#211e2e'),
    # With alpha
    ('#242424dd', '#1f1d2edd'),
    ('#141414dd', '#120f1ddd'),
    # Text / sub
    ('#888888', '#6e6a86'),
    ('#f5f5f5', '#e0def4'),
    # Light
    ('#fafafa', '#faf4ed'),
    ('#efefef', '#f2e9e1'),
    ('#e0e0e0', '#ddd6c8'),
    ('#666666', '#797593'),
    ('#e8e8e8', '#ede8e0'),
    ('#111111', '#575279'),
    ('#fff0f0', '#f4ede8'),
    ('#fff5f5', '#f4ede8'),
    ('#f0f0f0', '#f2e9e1'),
    ('#f5f5f5', '#e0def4'),
]

for old, new in replacements:
    count = data.count(old)
    if count:
        data = data.replace(old, new)
        print(f'  {old} -> {new}  ({count}x)')

open('app.py', 'w', encoding='utf-8').write(data)
print('\nColors replaced!')

# Fix THEMES dict
data = open('app.py', encoding='utf-8').read()
old_themes = re.search(r'THEMES = \{.*?\n\}', data, re.DOTALL).group(0)

new_themes = '''THEMES = {
    "dark": {
        # ── Rose Pine — Warm Dark Purple ──────────
        "bg":          "#191724",
        "card":        "#1f1d2e",
        "input_bg":    "#26233a",
        "text":        "#e0def4",
        "sub":         "#6e6a86",
        "accent":      "#eb6f92",
        "border":      "#26233a",
        "user_bg":     "#211e2e",
        "user_border": "#f083a0",
        "btn_bg":      "#26233a",
        "btn_text":    "#e0def4",
        "toolbar_bg":  "#120f1d",
        "welcome_bg":  "#191724",
        "grad1":       "#191724",
        "grad2":       "#1f1d2e",
        "grad3":       "#120f1d",
    },
    "light": {
        # ── Rose Pine Dawn ─────────────────────────
        "bg":          "#faf4ed",
        "card":        "#fffaf3",
        "input_bg":    "#f2e9e1",
        "text":        "#575279",
        "sub":         "#797593",
        "accent":      "#b4637a",
        "border":      "#ddd6c8",
        "user_bg":     "#f4ede8",
        "user_border": "#d7827a",
        "btn_bg":      "#f2e9e1",
        "btn_text":    "#575279",
        "toolbar_bg":  "#ede8e0",
        "welcome_bg":  "#f4ede8",
        "grad1":       "#faf4ed",
        "grad2":       "#f4ede8",
        "grad3":       "#ede8e0",
    },
}'''

data = data.replace(old_themes, new_themes)
open('app.py', 'w', encoding='utf-8').write(data)
print('THEMES updated!')

try:
    ast.parse(open('app.py', encoding='utf-8').read())
    print('Syntax OK ✓')
except SyntaxError as e:
    print(f'SYNTAX ERROR line {e.lineno}: {e.msg}')
