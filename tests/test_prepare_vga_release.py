import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_vga_release as release


class StableVgaPackageTests(unittest.TestCase):
    def fixture(self, folder, kind='full', **changes):
        source = folder / 'candidate.dcp'
        metadata = dict(version=release.TEST_VERSION, target_version=release.TEST_VERSION,
                        source_version='original' if kind == 'full' else '0.9.0', disc=1,
                        game_id='black-matrix-ad-dreamcast', target_tree_sha256='a' * 64)
        metadata.update(changes)
        with zipfile.ZipFile(source, 'x') as z:
            z.writestr('bootsector/IP.BIN', b'\0' * 32768)
            z.writestr('1ST_READ.BIN.xdelta', bytes.fromhex('d6c3c4') + b'fixture delta')
            z.comment = json.dumps(metadata).encode()
        return source

    def test_stable_metadata_changes_but_every_payload_stays_exact(self):
        for kind in ('full', 'upgrade'):
            with tempfile.TemporaryDirectory() as d:
                folder = Path(d)
                source = self.fixture(folder, kind)
                target = folder / 'stable.dcp'
                row = release.promote(source, target, release.sha(source), kind, 1)
                with zipfile.ZipFile(source) as a, zipfile.ZipFile(target) as b:
                    old, new = json.loads(a.comment), json.loads(b.comment)
                    self.assertEqual(new, dict(old, version='0.9.1', target_version='0.9.1'))
                    self.assertEqual(set(a.namelist()), set(b.namelist()))
                    for n in a.namelist():
                        self.assertEqual(a.read(n), b.read(n))
                self.assertTrue(row['delta_payloads_unchanged'])
                self.assertEqual(row['sha256'], release.sha(target))

    def test_unknown_candidate_checksum_fails_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d); source = self.fixture(folder); target = folder / 'stable.dcp'
            with self.assertRaisesRegex(ValueError, 'authenticated'):
                release.promote(source, target, 'f' * 64, 'full', 1)
            self.assertFalse(target.exists())

    def test_wrong_disc_game_version_or_source_is_rejected(self):
        for changes in ({'disc': 2}, {'game_id': 'other'}, {'version': '0.9.0'},
                        {'target_version': '0.9.0'}, {'source_version': '0.9.0'}):
            with tempfile.TemporaryDirectory() as d:
                folder = Path(d); source = self.fixture(folder, **changes)
                with self.assertRaisesRegex(ValueError, 'identity'):
                    release.promote(source, folder / 'stable.dcp', release.sha(source), 'full', 1)

    def test_full_game_payload_and_unsafe_paths_are_rejected(self):
        for name in ('1ST_READ.BIN', '../bad.xdelta', 'disc.bin'):
            with tempfile.TemporaryDirectory() as d:
                folder = Path(d); source = self.fixture(folder)
                with zipfile.ZipFile(source, 'a') as z:
                    z.writestr(name, bytes.fromhex('d6c3c4'))
                with self.assertRaises(ValueError):
                    release.promote(source, folder / 'stable.dcp', release.sha(source), 'full', 1)

    def test_upgrade_cannot_include_any_additional_game_file(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d); source = self.fixture(folder, 'upgrade')
            with zipfile.ZipFile(source, 'a') as z:
                z.writestr('OTHER.BIN.xdelta', bytes.fromhex('d6c3c4'))
            with self.assertRaisesRegex(ValueError, 'unexpected'):
                release.promote(source, folder / 'stable.dcp', release.sha(source), 'upgrade', 1)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d); source = self.fixture(folder)
            with self.assertRaises(FileExistsError):
                release.promote(source, source, release.sha(source), 'full', 1)


if __name__ == '__main__':
    unittest.main()
