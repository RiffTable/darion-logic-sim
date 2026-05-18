from PySide6.QtGui import QColor, QFont


class LightTheme:
    text           = QColor("#1f2c39")
    hl_text_bg     = QColor("#3677e0")
    primary_bg     = QColor("#cfd5db")
    secondary_bg   = QColor("#e1e6ec")
    bg_grid        = QColor("#e1e6ec")
    tooltip_text   = QColor("#f8fafc")
    tooltip_bg     = QColor("#263542")
    button         = QColor("#bcc3cb")
    
    comp_active    = QColor("#2fc51b")
    comp_body      = QColor("#d2d9e0")

    # Per-gate colour palette (body, outline, label)
    # Hues: AND=blue  NAND=violet  OR=teal  NOR=green  XOR=amber  XNOR=rose  NOT=gold
    gate_colors: dict[str, tuple["QColor", "QColor", "QColor"]] = {
        #         body (near #d2d9e0)  outline (near #6f7d8c)  label (near #1f2c39)
        "AND" : (QColor("#ccd5e2"),   QColor("#607888"),       QColor("#1a2840")),
        "NAND": (QColor("#d0cede"),   QColor("#706880"),       QColor("#20183c")),
        "OR"  : (QColor("#c8dbd4"),   QColor("#5e7a78"),       QColor("#10282e")),
        "NOR" : (QColor("#ccd8ce"),   QColor("#687a6a"),       QColor("#18281a")),
        "XOR" : (QColor("#dcd8d0"),   QColor("#80766a"),       QColor("#281e10")),
        "XNOR": (QColor("#dbd0d5"),   QColor("#7e6870"),       QColor("#271018")),
        "NOT" : (QColor("#dddbd0"),   QColor("#797a68"),       QColor("#252010")),
    }
    gate_sel_outline = QColor("#1e90ff")  # universal selection highlight
    # Fallback for unlisted gates
    gate_body      = QColor("#bfcfde")
    gate_outline   = QColor("#3d6b9a")
    gate_label     = QColor("#0d2137")

    # Input / Output palette
    input_body        = QColor("#cdd6e0")  # neutral blue-gray
    input_outline     = QColor("#4a6880")  # medium slate
    input_label       = QColor("#192838")  # near-black
    input_active      = QColor("#3a9e60")  # calm green (HIGH state)
    input_sel_outline = QColor("#1e90ff")
    output_outline    = QColor("#4a5e70")
    output_label      = QColor("#192838")

    signal_high    = QColor("#00FF87")
    signal_low     = QColor("#5f6468")
    signal_error   = QColor("#FF1E1E")
    signal_unknown = QColor("#00D4FF")
    
    pin_high       = QColor("#00FF00")
    pin_low        = QColor("#FF6B00")
    pin_hover      = QColor("#45676b")
    pin_hoverproxy = QColor("#FFDD57")
    
    LED_on         = QColor("#FFEE00")
    LED_off        = QColor("#d2d9e0")   # Original
    
    outline        = QColor("#6f7d8c")
    sidebar_toggle = QColor("#bac1ca")


class DarkTheme:
    text           = QColor("#d8dee6")
    hl_text_bg     = QColor("#2f65ca")
    primary_bg     = QColor("#03070c")
    secondary_bg   = QColor("#121c26")
    bg_grid        = QColor("#121c26")
    tooltip_text   = QColor("#ff0000")
    tooltip_bg     = QColor("#ffffff")
    button         = QColor("#1e2a36")
    
    comp_active    = QColor("#31ce1c")
    comp_body      = QColor("#17222d")

    # Per-gate colour palette (body, outline, label)
    gate_colors: dict[str, tuple["QColor", "QColor", "QColor"]] = {
        #         body (near #17222d)  outline (near #314152)  label (near #d8dee6)
        "AND" : (QColor("#142230"),   QColor("#384f68"),       QColor("#aac0d0")),
        "NAND": (QColor("#181e2e"),   QColor("#464268"),       QColor("#b0a8cc")),
        "OR"  : (QColor("#132224"),   QColor("#375660"),       QColor("#9ec0b4")),
        "NOR" : (QColor("#15221c"),   QColor("#405a4a"),       QColor("#a8c0a0")),
        "XOR" : (QColor("#1e2018"),   QColor("#574e3a"),       QColor("#c0b898")),
        "XNOR": (QColor("#1e1c22"),   QColor("#564048"),       QColor("#c0a8b0")),
        "NOT" : (QColor("#1e2016"),   QColor("#555040"),       QColor("#c0c098")),
    }
    gate_sel_outline = QColor("#4db8ff")  # universal selection highlight
    # Fallback for unlisted gates
    gate_body      = QColor("#0f1e2e")
    gate_outline   = QColor("#3a6fa8")
    gate_label     = QColor("#a8c8e8")

    # Input / Output palette
    input_body        = QColor("#182430")  # dark blue-gray
    input_outline     = QColor("#3a5068")  # medium slate
    input_label       = QColor("#a8bece")  # light gray-blue
    input_active      = QColor("#287848")  # muted green (HIGH state)
    input_sel_outline = QColor("#4db8ff")
    output_outline    = QColor("#384858")
    output_label      = QColor("#a0b8c8")

    signal_high    = QColor("#00FF87")
    signal_low     = QColor("#5f6468")
    signal_error   = QColor("#00D4FF")
    signal_unknown = QColor("#00D4FF")
    
    pin_high       = QColor("#00FF00")
    pin_low        = QColor("#FF6B00")
    pin_hover      = QColor("#6b8c9c")
    pin_hoverproxy = QColor("#ededed")

    LED_on         = QColor("#f1c40f")
    LED_off        = QColor("#17222d")
    
    outline        = QColor("#314152")
    sidebar_toggle = QColor("#07101f")


class Font:
    default        = QFont("Segoe UI", 9, QFont.Weight.Bold)
    gate           = QFont("Segoe UI", 8, QFont.Weight.Bold)


# List of "magic numbers"
class Val:
    # Animation Speed (in milliseconds)
    AnimSpeedLED = 140
    AnimSpeedPin = 125
    AnimSpeedWire = 125

    AlertUnsaved = True