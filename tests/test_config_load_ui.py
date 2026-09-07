"""Check config/load sprite boundaries and save/town prompt control flow."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_script
import config_load_ui as ui
import cooking
import psi2
import pvr_atlas
import scriptpack
from test_field_battle_ui import assert_outside_unchanged


class ConfigLoadUITests(unittest.TestCase):
    def original(self, name):
        path = ui.ROOT / 'extracted' / name
        if not path.exists():
            self.skipTest('requires original ' + name)
        return path.read_bytes()

    def test_fixed_records_preserve_code_and_live_fields(self):
        before = self.original('1ST_READ.BIN')
        after = bytearray(before)
        ui.patch_executable(after)
        ranges = [(o, o+2*w) for o, (_, w) in ui.EXE_RECORDS.items()]
        ranges += [(0x88E74, 0x88E74+32), (0x88EB0, 0x88EB0+20)]
        assert_outside_unchanged(self, before, after, ranges)
        before = self.original('PARAMETA.DAT')
        after = bytearray(before)
        ui.patch_parameters(after)
        assert_outside_unchanged(self, before, after, [(ui.START_HELP, ui.START_HELP+114)])
        lines = cooking.strings(ui.UI)['start_help'].split('\\n')
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(len(line) <= 19 for line in lines))

    def assert_sprite_pixels(self, before, after, regions):
        ranges = []
        for texture, rect in regions:
            x0, y0, x1, y1 = rect
            for y in range(y0, y1):
                for x in range(x0, x1):
                    pos = texture+16+2*pvr_atlas.pixel_index(x, y)
                    ranges.append((pos, pos+2))
        assert_outside_unchanged(self, before, after, ranges)

    def test_load_help_sprites_preserve_controller_icons_and_uvs(self):
        before = self.original('SYSTEM.DAT')
        after = bytearray(before)
        ui.patch_system(after)
        regions = [(texture, ui.sprite_rect(before, pvx, index))
                   for pvx, texture, index, _, _ in ui.SYSTEM_SPRITES]
        regions.append((ui.MOVE_TEXTURE, ui.sprite_rect(before,
            ui.MOVE_PVX, ui.MOVE_SPRITE, expected_page=1)))
        regions.extend((0x21890, ui.sprite_rect(before, 0x21000, index))
                       for index, _ in ui.STATUS_SPRITES)
        self.assert_sprite_pixels(before, after, regions)
        self.assertNotEqual(before, after)

    def test_banner_preserves_gradient_and_all_other_assets(self):
        before = self.original('EVENT.DAT')
        after = bytearray(before)
        ui.patch_event(after)
        self.assert_sprite_pixels(before, after, [(ui.BANNER_TEXTURE,
            ui.sprite_rect(before, ui.BANNER_PVX, 0))])
        self.assertNotEqual(before, after)

    def test_save_and_town_prompts_preserve_branch_destinations(self):
        translations = build_script.load_en(str(ui.ROOT / 'script/en/system_save_town_prompts.en.tsv'))
        self.assertEqual(len(translations), 22)
        self.assertEqual(set(translations.values()), {'Leave town?', 'Save progress?'})
        checked = 0
        for _, start, program in psi2.groups(self.original('SCENARIO.DAT')):
            local = {o-start:t for o,t in translations.items() if start <= o < start+len(program)}
            if not local:
                continue
            patched, _, _, _ = scriptpack.repack_psi(program, local)
            before, after = psi2.walk(program), psi2.walk(patched)
            self.assertEqual(len(before.boundaries), len(after.boundaries))
            mapping = dict(zip(sorted(before.boundaries), sorted(after.boundaries)))
            self.assertEqual(len(before.targets), len(after.targets))
            for (_, old), (_, new) in zip(before.targets, after.targets):
                self.assertEqual(mapping[old+16], new+16)
            checked += len(local)
        self.assertEqual(checked, len(translations))


if __name__ == '__main__':
    unittest.main()
