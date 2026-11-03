# Third-party notices

The MIT license in this repository covers its original companion/bridge code.
It does not relicense J.A.C.K., game assets, maps or dependencies.

## Unofficial JackSDK / JackSDK_SDK

Copyright 2026 SanyaSho. SDK headers are **LGPL-2.1-or-later**.
Pinned SDK commit: `b7141e36e785b15ee658fbb0a3b34dee5b1e3dfe`.
Sources: https://github.com/SanyaSho/JackSDK_SDK and
https://github.com/SanyaSho/JackSDK . The upstream primitive example informed
the box construction; those example files are MIT-licensed by their upstream.

`scripts/fetch-deps.ps1` downloads the corresponding source and license without
changing it. Distributors of a compiled plugin must include the LGPL license,
these notices and access to matching SDK and bridge source/rebuild instructions.
Do not remove users' ability to rebuild a modified plugin.

## nlohmann/json

Copyright Niels Lohmann and contributors. MIT.
Version 3.12.0. Source: https://github.com/nlohmann/json . The build downloads its
single header and LICENSE.MIT and verifies the header SHA-256.

## Python dependencies

MCP Python SDK (MIT), Pillow (HPND and component notices), PyAutoGUI (BSD).
Installed through pip; their distributions retain their own notices/licenses.
See requirements.txt and the installed packages for exact dependency versions.

## Not distributed

J.A.C.K. binaries/Qt libraries, Valve/GoldSrc game files, EXFIL PROTOCOL maps,
WADs, models, private project configuration, session tokens and user backups.
Users supply their own editor/game installations. J.A.C.K./Valve/OpenAI are
not affiliated with or endorsing this unofficial project.
