# Compatibility

Native plugin tested: **J.A.C.K. 1.1.3773 Freeware, Windows x64, API 10**.
Required executable SHA-256:

```text
1dcd13dbc6ded7181ae47b611a11f6c08c8e2da85af14f03c4ca9bc705bfdac8
```

The plugin also checks the API level and exact 1464-byte function table. These
checks are intentional: an unofficial SDK does not establish binary
compatibility across editions, architectures or versions.

Dependencies:

- [JackSDK](https://github.com/SanyaSho/JackSDK), reference root revision
  `1a9525968f46b54419d718c447cecb7012959673`.
- [JackSDK_SDK](https://github.com/SanyaSho/JackSDK_SDK), build headers pinned to
  `b7141e36e785b15ee658fbb0a3b34dee5b1e3dfe`, compiled with `JACK_API_VERSION=10`.
- nlohmann/json 3.12.0 with a checked header SHA-256.

This project uses the unofficial SDK's exposed function table and structures.
It does not patch JACK, inject into an unrelated process, assume private Qt
functions exist, or locate executable functions using guessed offsets.

MAP parsing is independent of the native ABI. JMF/RMF file inspection optionally
uses a separately obtained MESS tool; native live inspection does not require
that converter. Heuristic MAP bounds use plane-defining points and are not a
guarantee of exact convex extents or engine coordinate limits.

To support another editor build, contribute a separately guarded adapter with
ABI checks and disposable-host tests. Removing the fingerprint guard alone is
not support. macOS/Linux native sessions and Steam builds remain unvalidated.
