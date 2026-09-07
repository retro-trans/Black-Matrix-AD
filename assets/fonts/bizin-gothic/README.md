# Bizin Gothic source font

Unmodified BizinGothic-Regular.ttf from yuru7/bizin-gothic v0.0.4:
https://github.com/yuru7/bizin-gothic/releases/tag/v0.0.4

SHA-256: `302c6467491bde54d87f77293922b90950a49960b85f436f174b46b357a5d835`

Copyright (c) 2022 Yuko Otawara. Reserved Font Name: Bizin Gothic.
See LICENSE.txt for the upstream SIL Open Font License 1.1. Keep this notice
and the license with redistributed font material. The bundled TTF is unchanged;
the game's converted glyph artwork is called the **BMAD Latin bitmap trial**,
not an upstream Bizin Gothic release, and carries the same OFL terms for that
font-derived artwork (not the original game data).

Default trial settings: 19px requested size, horizontal factor 1.5.
After viewing the natural-proportion version in game, the user requested fuller
letters without changing height. H is now 12x12px (previously 8x12px); Latin
letters reach 13px wide and punctuation reaches 20px. The 23px storage guard
is inactive for this profile. Vertical fitting retains the 16-row bitmap budget.
The alphabet/digits now occupy rows 0..15 collectively. Tall punctuation is
fitted separately at a smaller point size on the same baseline, so it no longer
forces every letter down to 17px. No glyph is cropped or stretched vertically.
The native 16-row texture storage is unchanged. A separate VWF layout hook
now uses 18px row spacing for expanded dialogue/narration grids.
Variable-width spacing remains ink width + 1px; spaces use the existing width.
Only Latin letters, digits and mapped punctuation are replaced. Original
Japanese glyphs and static help-screen/HUD fonts are unchanged.
