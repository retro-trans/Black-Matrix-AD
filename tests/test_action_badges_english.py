import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools/hd_ui'), str(ROOT/'tools')]
import action_badges_english as fix


class ActionBadgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.after, cls.report = fix.prepare()
        cls.before = fix.b.READER.read_file(fix.b.track(fix.SOURCE, 2), 'CHAR.DAT')[0]
        cls.old = fix.pvr_atlas.decode(cls.before, fix.TEXTURE)
        cls.new = fix.pvr_atlas.decode(cls.after, fix.TEXTURE)

    def test_authenticated_both_disc_source_and_expected_native_output(self):
        self.assertEqual(fix.b.sha(self.before), fix.CHAR_SHA)
        self.assertEqual(fix.b.sha(self.after), '71747341a17c0468dc6c8e560bcb0b814bba9c86ab8d48af344f34f4c72297dc')
        self.assertEqual(self.report['changed_char_bytes'], 5981)
        self.assertEqual(len(self.before), len(self.after))
        self.assertEqual(self.report['changed_descriptors'], 14)
        self.assertEqual(self.report['reviewed_descriptors'], 169)

    def test_exact_pixel_scope_and_all_other_descriptors(self):
        old, new = np.asarray(self.old), np.asarray(self.new)
        allowed = np.zeros(old.shape[:2], dtype=bool)
        for x, y, xx, yy in fix.RECTS.values():
            allowed[y:yy, x:xx] = True
        changed = np.any(old != new, axis=2)
        self.assertTrue(np.any(changed))
        self.assertFalse(np.any(changed & ~allowed))
        rows = fix.native.pack.descriptors(self.before, fix.TEXTURE)
        targets = set(fix.LABELS) | set(fix.SPLIT)
        self.assertEqual(len(rows), 169)
        self.assertEqual(len(targets), 14)
        for i, rect in rows.items():
            if i not in targets:
                self.assertEqual(self.old.crop(rect).tobytes(), self.new.crop(rect).tobytes(), i)
        for i in (93, 94, 99, 160, 161, 163, 164, 165, 166, 167, 168):
            self.assertNotIn(i, targets)

    def test_stance_tiles_reassemble_exactly(self):
        rows = fix.native.pack.descriptors(self.after, fix.TEXTURE)
        composite = np.concatenate([np.asarray(self.new.crop(rows[i])) for i in fix.SPLIT], axis=1)
        np.testing.assert_array_equal(composite, np.asarray(self.new.crop(fix.RECTS[104])))
        self.assertEqual(composite.shape, (16, 48, 4))

    def test_actual_generated_alpha_native_palette_and_no_opaque_box(self):
        tiles, coverage = fix.artwork(self.before)
        self.assertEqual(len(coverage), 12)
        for i, intended in tiles.items():
            actual = np.asarray(self.new.crop(fix.RECTS[i]))
            np.testing.assert_array_equal(actual[:, :, 3], np.asarray(intended)[:, :, 3])
            self.assertEqual(set(actual[:, :, 3].ravel()), {0, 255})
            old = np.asarray(self.old.crop(fix.RECTS[i]))
            peak = max((tuple(int(c) for c in p[:3]) for p in old[old[:, :, 3] > 0]), key=sum)
            colours = {tuple(p[:3]) for p in actual[actual[:, :, 3] > 0]}
            self.assertEqual(colours, {peak, (0, 0, 0)}, fix.LABELS[i])
            self.assertFalse(np.any(actual[:3, :, 3]))
            self.assertLess(np.count_nonzero(actual[:, :, 3]), actual.shape[0]*actual.shape[1]//2)

    def test_review_provenance_and_prepared_asset_are_current(self):
        review = json.loads((fix.ASSETS/'labels.en.json').read_text())
        self.assertEqual(review['asset_sha256'], fix.b.sha(fix.ASSET.read_bytes()))
        self.assertEqual({r['sprite']: r['text'] for r in review['rows']}, fix.LABELS)
        for key in ('accuracy_rows_examined', 'editorial_packed_labels_examined', 'main_final_proof_rows'):
            self.assertEqual(review['review'][key], 12)
        self.assertFalse(review['conversion']['old_font_masks_used'])
        self.assertFalse(review['conversion']['per_word_scaling'])
        self.assertEqual((fix.PREPARED/'CHAR.DAT').read_bytes(), self.after)
        self.assertEqual(json.loads((fix.PREPARED/'verification.json').read_text()), self.report)

    def test_reject_unknown_source_repeat_patch_and_asset(self):
        for raw, disc in ((self.after, 2), (self.before, 3), (self.before[:-1]+b'X', 2)):
            with self.assertRaises(ValueError):
                fix.patch(raw, disc)
        with patch.object(fix, 'ASSET_SHA', '0'*64):
            with self.assertRaises(ValueError):
                fix.masks()

    def test_safe_launcher_only_mocked(self):
        with patch.object(fix.b.domina.zero, 'launch') as launch:
            for disc in (1, 2):
                fix.launch(disc)
                self.assertEqual(launch.call_args.args, (disc,))
                self.assertEqual(launch.call_args.kwargs['build'], fix.OUT)
                self.assertEqual(launch.call_args.kwargs['status'], fix.STATUS)
                self.assertEqual(launch.call_args.kwargs['settings']['rend.Resolution'], '1440')

    def test_complete_delivery_when_built(self):
        if not (fix.OUT/'manifest.json').exists():
            self.skipTest('New disc pair has not been built yet')
        raw = (fix.OUT/'manifest.json').read_bytes()
        raw.decode('ascii')
        manifest = json.loads(raw.decode('gbk'))
        self.assertEqual(manifest['build_version'], '0.1.13')
        self.assertEqual(manifest['status'], fix.STATUS)
        self.assertEqual(manifest['action_badges'], self.report)
        self.assertFalse(manifest['action_badges']['gameplay_verified'])
        self.assertNotEqual(manifest['disc_executable_sha256']['1'], manifest['disc_executable_sha256']['2'])
        for disc, name in ((1, '1ST_READ.disc1.BIN'), (2, '1ST_READ.BIN')):
            source = (fix.SOURCE/name).read_bytes()
            self.assertEqual((fix.OUT/name).read_bytes(), source)
            self.assertEqual(fix.b.READER.read_file(fix.b.track(fix.OUT, disc), '1ST_READ.BIN')[0], source)
            self.assertEqual(fix.b.READER.read_file(fix.b.track(fix.OUT, disc), 'CHAR.DAT')[0], self.after)
        self.assertEqual((fix.OUT/'action-badges-assets/generated-lettering.png').read_bytes(), fix.ASSET.read_bytes())
        fix.b.domina.zero.combined.verify_files(fix.OUT, manifest['files'])
        fix.b.domina.zero.combined.cue_checks(fix.OUT)


if __name__ == '__main__':
    unittest.main()
