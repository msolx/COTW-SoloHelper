# Published release provenance — v1.1.0

Checked on 2026-10-28 against the actual **standalone GitHub Release**, not the earlier Toolkit distribution.

| Item | Identity |
| --- | --- |
| Release | [v1.1.0](https://github.com/msolx/COTW-SoloHelper/releases/tag/v1.1.0) |
| ZIP | `COTW_SoloHelper_v1.1.0.zip` (37482480 bytes) |
| ZIP SHA-256 | `a7d8d92ffdd2f592ddab815bfbecb7e49ee6d91cbe245ba50daf5b97048d466b` |
| EXE SHA-256 | `0f3c1a9326f1a82d15e1c8545d00020cf1c27ff23b21592d8710ab6ed3b4f8d8` |
| Runtime source | [v1.1.0](https://github.com/msolx/COTW-SoloHelper/tree/v1.1.0) |
| Source commit | `9263691beb8ed730ee87104433f754bf7ac1c2a4` |

## What was checked

1. The locally retained release ZIP exists and matches the GitHub asset's reported SHA-256 and byte size. A new download was not needed; the digest establishes which file was examined.
2. ZIP CRC passed. The EXE was extracted from that ZIP and hashed separately.
3. All **31 embedded application modules** match the runtime source at the release tag by bytecode, names, flags, exception tables and recursive constants. Source paths/line tables are ignored. Per-module results are in [SOURCE_COMPARISON.json](SOURCE_COMPARISON.json).

This is a static source/binary comparison, not a byte-identical rebuild or antivirus certification. The EXE was not executed and real-game features were not retested during this documentation review.

## Tests and their scope

The earlier separated-source run executed **102 tests: 98 passed, 4 skipped**, with zero failures/errors. The skipped cases require original game resources that are not distributed. A source build also succeeded. These results belong to source validation, not a claim that this standalone release ZIP passed every GUI or game feature test.

The earlier Toolkit EXE was `a2e840f6a08446b692b030d684de68c3882841bf85a1324730a8a61bae933034`. It is a different binary and is **not** the EXE shipped in the standalone Release. Its recorded results were not reassigned to the standalone file. The comparison above was repeated using the actual standalone ZIP. See [historical validation](VALIDATION_v1.1.0.md).

## Documentation and attribution update

The published release tags, ZIPs and EXEs are unchanged. The current documentation snapshot is tagged `docs-2026-10-28`; it updates comments and the project's own LICENSE/PE attribution to **msolx**, with the author's confirmation. Third-party notices are preserved.

The published EXEs still contain their original version metadata; the source metadata correction applies to future builds. Rebuilding current main is not the way to reproduce the recorded EXE metadata: use the runtime release tag above. The documentation snapshot is not a new binary release.

Local diagnostics, email drafts, game resources and private development history are not included in this source repository. See [technical details](TECHNICAL.md) for actual memory/file operations and compatibility limits.
