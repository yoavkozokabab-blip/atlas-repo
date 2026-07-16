# Atlas reverse-engineering posture

Atlas is locally distributed software and cannot be made impossible to reverse
engineer. v1.0.5 prioritizes server-authoritative entitlements, no client
secrets, clean artifact inventories, and signing readiness over hostile
anti-debugging or obscurity.

| Option | Benefit | Risk/cost | Recommendation |
|---|---|---|---|
| Current PyInstaller | Fastest, proven packaging path | Python modules remain extractable | v1.0.5 baseline only with artifact audit |
| PyInstaller + compiled sensitive modules | Raises cost for selected deterministic engine code | Native build/toolchain complexity | Evaluate after stable core interface |
| Nuitka full build | Higher extraction resistance and possible performance gain | High packaging/debug/maintenance risk | Later experiment, not launch-critical |
| Rust/C++ graph extension | Strong boundary for performance-sensitive core | Highest engineering and cross-platform cost | Long-term only if profiling justifies it |

Never ship signing keys, entitlement secrets, test certificates, source maps,
fixture repositories, reports, or debug artifacts. Code signing and a verified
update manifest are higher-value controls than JavaScript/Python obfuscation.
