import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tools/hd_ui')]
import prepare_private_release as release


class PrivateReleaseTests(unittest.TestCase):
    def test_release_identity_is_not_internal_build_label(self):
        self.assertEqual(release.VERSION, '0.9.0')
        self.assertEqual(release.badge.VERSION, '0.1.13')
        self.assertEqual(release.REPO, 'retro-trans/Black-Matrix-AD')
        self.assertTrue(release.BASE.resolve().is_relative_to(ROOT/'build'))

    def test_source_snapshot_is_explicit_and_has_no_game_binaries(self):
        rows = release.sources()
        paths = {r['path'] for r in rows}
        self.assertIn('README.md', paths)
        self.assertIn('tools/hd_ui/action_badges_english.py', paths)
        self.assertIn('tools/prepare_private_release.py', paths)
        self.assertIn('assets/ui/battle-labels/action-badges-v1/generated-lettering.png', paths)
        self.assertFalse(any(p.startswith(('build/', 'output/', 'work/', 'script/')) for p in paths))
        self.assertFalse(any(Path(p).suffix.lower() in ('.bin', '.cue', '.dat', '.iso', '.zip', '.sav', '.vmu') for p in paths))
        self.assertEqual(len(rows), len(paths))
        for row in rows:
            self.assertEqual(release.sha(ROOT/row['path']), row['sha256'])
            self.assertEqual((ROOT/row['path']).stat().st_size, row['bytes'])

    def test_release_copy_does_not_overclaim_review_or_private_catalog(self):
        text = (ROOT/'README.md').read_text(encoding='utf-8')
        self.assertIn('v0.9.0', text)
        self.assertIn('private', text)
        self.assertIn('Normal/Latent', text)
        self.assertIn('not a complete', text)
        self.assertIn('Zero unlocked', text)
        self.assertIn('Domina first', text)
        self.assertIn('moderate Whisper', text)

    def test_built_patch_protocol_and_upload_allowlist(self):
        path = release.BASE/'approved-upload-assets-local.json'
        if not path.exists():
            self.skipTest('Patch release not built yet')
        manifest = json.loads((release.READY/'BUILD-MANIFEST.json').read_text())
        state = json.loads(release.STATE.read_text())
        self.assertEqual(manifest['version'], '0.9.0')
        self.assertEqual(manifest['source_commit'], state['source_commit'])
        self.assertEqual(len(manifest['patches']), 2)
        for row in manifest['patches']:
            self.assertEqual(row['source_version'], 'original')
            self.assertEqual(row['source_format'], 'bin')
            self.assertEqual(row['target_format'], 'bin')
            disc = 1 if row['edition'] == 'jp-disc1-track3-native' else 2
            self.assertEqual(row['target_sha256'], release.TARGETS[disc])
        assets = json.loads(path.read_text())
        self.assertEqual(len(assets), 9)
        self.assertEqual(sum(r['name'].endswith('.xdelta') for r in assets), 2)
        for row in assets:
            self.assertIn(Path(row['name']).suffix, ('.xdelta', '.json', '.txt'))
            self.assertEqual(release.sha(Path(row['path'])), row['sha256'])
            self.assertEqual(Path(row['path']).stat().st_size, row['bytes'])
        sys.path.insert(0, str(release.TOOLCHAIN))
        from retro_trans.release import validate_directory
        validate_directory(release.READY)


if __name__ == '__main__':
    unittest.main()
