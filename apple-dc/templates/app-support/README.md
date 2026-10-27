# App support

The notebook the apple-dc plugin reads before it builds, signs or ships any app, and writes to afterwards. Private:
it names this Mac's signing setup and every app. No secret ever goes in here (no passwords, no .p8 or .p12 files,
no private keys); say where a secret lives instead.

| File | Holds |
| --- | --- |
| `apps.md` | One section per app: stack, bundle ID, repo, where releases go, notary profile, Sparkle key account, last version shipped |
| `machine.md` | Each Mac: Xcode, certificates, notary profiles (and whether they still work), Sparkle keys, what a new Mac needs |
| `lessons.md` | Dated one-liners: what went wrong or what worked, and which app taught it. Newest first |

Lessons that are generic and name nothing private get promoted into the plugin's skills (the `app-support` skill's
"promote lessons"), and are marked `(promoted)` here.
