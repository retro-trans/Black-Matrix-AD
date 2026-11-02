# Public-readiness sanitation — 2026-11-02

Pow explicitly requested public publication after sanitizing the existing
private repository history. The complete original history is backed up locally;
no original or complete translated game image was uploaded.

All retained revisions were audited. Original bilingual dialogue sources and a
scenario inventory containing original script excerpts were removed from all
branches and the release tag. Translation control keys, names and short UI
labels are retained intentionally. Binary history consists only of a licensed
font and generated English lettering, not game images or game archives.

## Source identity mapping

Issued DCP packages and their provenance files are unchanged. Their recorded
pre-sanitation source identities map as follows:

| Role | Original private commit | Sanitized commit |
| --- | --- | --- |
| Translation / v0.9.0 tag | `27c173b264a03268c234957debfd34a963b0cd6b` | `9ef9fa17922d3d8c646715cb49d35fb601ebd267` |
| DCP packaging snapshot | `5dc863b37cf03b5aee0701b63057bac1a37a68f8` | `cacd5f2be37c57dd94242cde2352768d190e022d` |

All three remote refs were replaced atomically with exact old-commit leases.
The original dirty development working tree and index were not reset or staged.
Do not merge or push an old unsanitized development branch into the cleaned
history: that would restore the removed source. Re-clone or deliberately port
reviewed changes into the cleaned history.

## Independent replacement, not a visibility flip

After the rewrite, authenticated GitHub API requests using the old translation
commit still returned the removed files. No forks or pull requests were found,
but rewriting reachable history alone did not remove GitHub's cached objects.
The user therefore explicitly approved renaming that repository as a private
backup and creating a fresh replacement under the original name. The backup
stays private. Only the sanitized main branch and sanitized v0.9.0 tag are
pushed into the independent replacement, which is not created as a fork.

Before public visibility, check that the removed paths, old commits and old
dialogue blobs are inaccessible through the replacement's GitHub API. After
publication, repeat the checks without authentication. Preserve the local
original-history backup and dirty development working tree; neither is uploaded.

[GitHub's history-removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
describes this cached-commit limitation. This replacement was separately
approved by the user; no original repository or release asset was deleted.

Issued DCPs and three historical build-receipt JSON files remain unchanged.
Their pre-sanitation IDs map to the sanitized snapshots above; the manifest's
`private` flag records its original creation state. A new publication receipt
records the public repository identity, source mapping and artifact hashes.
The public README/checksum files are refreshed for current patching instructions.

## Retro Trans compatibility

Both discs passed original CUE to GDI and original CUE to CUE/BIN apply,
rebuild and re-extraction checks with the local DCP-enabled Retro Trans 0.5.19
adapter and authenticated Universal Dreamcast Patcher 2.1.8 engine. This is
file-content, boot-invariant and audio validation, not a hardware/playthrough test.

The actual public Retro Trans 0.5.18 Windows executable's health check reports
only Automatic, Apply xdelta, Save conversion and Vita tabs. Its SHA-256 is
`3b9895023b052ed40a030ee79b342501bfb81f914f66e0736492ce2a6a4fa487`.
Use Retro Trans 0.5.19+ with its DCP tab, or Universal Dreamcast Patcher 2.1.8.
Pow has now published [Retro Trans 0.5.19 for Windows](https://github.com/retro-trans/retro-trans-tools/releases/tag/v0.5.19).
The actual public `Retro-Trans.exe` (64,277,366 bytes) was SHA-256 verified:
`837b928a7efc7d1dbf65807c452eb0396fe2e528c834dcbe9f1408800383a25c`.
Its isolated health check returned version 0.5.19, success, a DCP tab, bundled
engine and successful engine startup. This confirms the shipped app includes
the DCP runtime; it is not a claim that the four game round trips were repeated
with this public EXE. Use the versioned Windows ZIP for its runtime notices.
No app build or release was published by this sanitation operation.
