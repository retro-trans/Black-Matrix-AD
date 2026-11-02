import hashlib
import json
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import prepare_dcp_release as release


class DcpReleaseTests(unittest.TestCase):
    def test_distribution_version_and_private_policy(self):
        self.assertEqual(release.VERSION, '0.9.0')
        self.assertEqual(release.UPSTREAM, '8b352f959bcc56ab39174c9e311b7ab7f0d522a2')
        text = (ROOT/'README.md').read_text(encoding='utf-8')
        self.assertIn('**DCP**', text)
        self.assertNotIn('Apply xdelta', text)
        self.assertNotIn('from-original.xdelta', text)
        self.assertIn('**pow**', text)
        self.assertIn('**private**', text)

    def test_frozen_engine_and_adapter_authenticate(self):
        proof = json.loads((release.BASE/'toolchain-proof.json').read_text())
        self.assertEqual(proof['plan']['upstream_commit'], release.UPSTREAM)
        for name, row in proof['files'].items():
            path = release.TOOLCHAIN/name
            self.assertEqual(path.stat().st_size, row['bytes'])
            self.assertEqual(release.sha(path), row['sha256'])
        self.assertTrue(release.adapter().engine().is_file())

    def test_two_genuine_filesystem_dcp_archives_and_existing_vga_header(self):
        for disc in (1, 2):
            work = release.BASE/f'disc{disc}'
            proof_file = work/'package-proof.json'
            if not proof_file.exists():
                self.skipTest('Both DCP packages not yet completed')
            proof = json.loads(proof_file.read_text())
            path = release.READY/proof['patch']
            self.assertEqual(release.sha(path), proof['sha256'])
            self.assertFalse(proof['verbatim_game_files'])
            self.assertTrue(proof['standard_custom_boot_header'])
            before = (work/'source-inspection/files/bootsector/IP.BIN').read_bytes()
            after = (work/'target-inspection/files/bootsector/IP.BIN').read_bytes()
            self.assertEqual(len(after), 32768)
            self.assertEqual([i for i,(a,b) in enumerate(zip(before, after)) if a != b], [0x3d])
            self.assertEqual((before[0x3d], after[0x3d]), (0x30, 0x31))
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                self.assertEqual(names, {n+'.xdelta' for n in proof['changed_files']} | {'bootsector/IP.BIN'})
                self.assertEqual(archive.read('bootsector/IP.BIN'), after)
                for name in names-{'bootsector/IP.BIN'}:
                    self.assertTrue(archive.read(name).startswith(b'\xd6\xc3\xc4'))
                self.assertEqual(json.loads(archive.comment), proof['metadata'])
            checked = release.adapter().inspect_patch(path)
            self.assertEqual(checked['metadata']['disc'], disc)
            self.assertEqual(checked['metadata']['version'], '0.9.0')
            self.assertEqual(checked['metadata']['source_version'], 'original')

    def test_all_four_rebuilt_routes_match_game_tree_boot_and_audio(self):
        for disc in (1, 2):
            work = release.BASE/f'disc{disc}'
            for format in ('gdi', 'cue-bin'):
                path = work/f'verified-{format}.json'
                if not path.exists():
                    self.skipTest('All four DCP routes not yet completed')
                proof = json.loads(path.read_text())
                package = json.loads((work/'package-proof.json').read_text())
                self.assertTrue(proof['release_metadata_verified'])
                self.assertTrue(proof['audio_tracks_preserved'])
                self.assertEqual(proof['verified_game_tree_sha256'], package['metadata']['target_tree_sha256'])
                self.assertEqual(proof['bootsector_invariant_sha256'], package['metadata']['bootsector_invariant_sha256'])
                self.assertEqual(proof['audio_content'], json.loads((work/'source-inspection/inspection.json').read_text())['audio_content'])
                for name, identity in proof['output_files'].items():
                    file = work/f'verified-{format}'/name
                    self.assertEqual(file.stat().st_size, identity['bytes'])
                    self.assertEqual(release.sha(file), identity['sha256'])

    def test_staged_distribution_is_dcp_only_with_separate_translation_and_packaging_commits(self):
        path = release.BASE/'approved-dcp-assets-local.json'
        if not path.exists():
            self.skipTest('DCP publication metadata not yet staged')
        assets = json.loads(path.read_text())
        self.assertEqual(len(assets), 7)
        self.assertEqual(sum(r['name'].endswith('.dcp') for r in assets), 2)
        self.assertFalse(any(r['name'].endswith(('.xdelta','.bin','.iso','.cue','.gdi','.zip')) for r in assets))
        self.assertFalse((release.READY/'BUILD-MANIFEST.json').exists())
        manifest = json.loads((release.READY/'DCP-MANIFEST-v0.9.0.json').read_text())
        self.assertEqual(manifest['format'], 'DCP')
        self.assertEqual(manifest['version'], '0.9.0')
        self.assertTrue(manifest['private'])
        self.assertFalse(manifest['translated_game_content_changed'])
        self.assertEqual(manifest['translation_source_commit'], '27c173b264a03268c234957debfd34a963b0cd6b')
        self.assertNotEqual(manifest['translation_source_commit'], manifest['packaging_source_commit'])
        self.assertEqual(len(manifest['patches']), 2)
        self.assertNotEqual(manifest['patches'][0]['metadata']['source_tree_sha256'], manifest['patches'][1]['metadata']['source_tree_sha256'])
        for row in assets:
            file = Path(row['path'])
            self.assertEqual(file.stat().st_size, row['bytes'])
            self.assertEqual(release.sha(file), row['sha256'])


if __name__ == '__main__':
    unittest.main()
