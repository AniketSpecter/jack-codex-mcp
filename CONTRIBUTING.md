# Contributing

Issues, documentation fixes and focused pull requests are welcome. Start with a
small reproducible case on a generated disposable map. Read
[architecture](docs/ARCHITECTURE.md), [safety](docs/SAFETY.md), and
[testing](docs/TESTING.md) before native work.

1. Fork and clone the repository; create a branch.
2. Run setup/build and the automated tests.
3. Keep UI-thread and ownership checks intact. Never patch the editor, bypass
   fingerprint validation or copy undocumented call offsets from disassembly.
4. Add a meaningful regression test for changed protocol/geometry/recovery logic.
5. For a new host, include ABI/version evidence and disposable real-host results.
6. Describe behavior, test evidence, limitations and licensing in your PR.

Do not commit editor binaries, game assets, personal maps, local configs, endpoint
files, tokens, private paths or crash dumps containing private map data. Use
original synthetic fixtures. Changes to the SDK need separate upstream review;
dependencies here are pinned. By contributing you license your own changes under
this project's MIT license; preserve third-party license notices.

Unfinished capabilities must remain labeled experimental/proposed. Do not claim
that an exported DLL compiling proves it works in JACK.
