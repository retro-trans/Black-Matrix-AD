"""Shared native-grid and script-wrapping limits. Keep both build sides in sync."""
EXPAND_TEXT_GRIDS = True
STOCK_SPOKEN_COLS = 17
STOCK_NARRATION_COLS = 19
SPOKEN_COLS = 33 if EXPAND_TEXT_GRIDS else STOCK_SPOKEN_COLS
# st14 (NARR) also writes into spoken windows: the opcode is NOT a reliable
# window-width selector. Both allocated widths must agree with both wrappers.
NARRATION_COLS = 33 if EXPAND_TEXT_GRIDS else STOCK_NARRATION_COLS
ROW_PIXELS = 17 * 28
TEXT_ROW_PITCH = 18  # 16px glyphs plus two pixels of leading
TRANSITION_CELLS = 100
assert SPOKEN_COLS * 3 <= TRANSITION_CELLS
assert NARRATION_COLS * 2 <= TRANSITION_CELLS
