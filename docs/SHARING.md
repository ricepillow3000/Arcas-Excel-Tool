# Sharing Arcas: why one file, not Docker or Kubernetes

John's question (2026-11-02, AH-95): an app that runs on my PC but not on a friend's is solved by **containerization**:
pack the app in a box (a Docker image) and hand the same box to anyone. When many people use it, **Kubernetes**
manages the boxes: it restarts the ones that crash, starts more when users pile in, and spreads the traffic. "If there
is a different way that is free, just as effective, go that route."

## The short answer
The box already exists, it is free, and it fits this app better than Docker does: **`Arcas.exe`**, one
file that carries Python, every package (each pinned to an exact version) and the pane. CI proves it on a fresh
Windows PC before every release. Kubernetes has nothing to manage here, because no server takes the crowd: each
person's own PC runs its own engine beside its own Excel.

```
Docker's promise                     What Arcas does instead (free)
"same box on every PC"          ->   one .exe with Python + pinned packages inside (packaging/AnomalyHunter.spec)
"prove it runs elsewhere"       ->   CI installs it on a fresh Windows PC with no Python, scans, fixes, undoes,
                                     uninstalls, before it becomes the download link (build-exe.yml, new-user)
Kubernetes' promise                  Here
"restart what crashes"          ->   the engine starts at every logon; the pane says so if it is down and Try again
                                     reconnects; a double-click on the exe repairs the install
"scale up for more users"       ->   nothing to scale: every user brings their own CPU (one engine per PC)
"load balancing"                ->   the one shared piece, the AI relay, runs on Cloudflare Workers' free plan,
                                     which spreads load across Cloudflare's network by itself
```

## Why Docker would not fit this app
| Docker would need | Here |
|---|---|
| Docker Desktop on the friend's PC: a large extra install, WSL 2 or Hyper-V on Windows, and a paid licence for companies with 250+ staff or $10M+ revenue ([licence](https://docs.docker.com/subscription/desktop-license/)) | Nothing to install first: the exe needs no Python, no admin rights, no internet at install (`build-exe.yml` hides Python and still passes) |
| A way out of the box into the friend's Excel | An Office add-in is registered in the user's own Windows (`HKCU\...\Office\16.0\WEF\TrustedCatalogs`) and loads only over HTTPS that Windows trusts. A container can do neither: the exe trusts a certificate limited to 127.0.0.1 in the user's own store (`app.install`) |
| Port publishing and a running daemon | The engine listens on 127.0.0.1:5055 and refuses any other host (`server.own_panel_only`) |

## Why Kubernetes would not fit
Kubernetes runs a service many people share. Building one would mean a central engine that receives everyone's
spreadsheets, which breaks the app's first promise, "a scan runs on your PC and sends nothing to the internet"
(PRIVACY.md), and its security rules (an engine reachable from outside the PC needs accounts, rate limits and an
admin, which CLAUDE.md forbids). It would also cost money every month. `docs/SYSTEMS-MAP.md` already rules it out
until the app becomes a hosted multi-user service.

## What is left to make a friend's install as smooth as possible, free
| Gap | Today | Free way to close it | Who |
|---|---|---|---|
| Windows' "unknown publisher" warning | The exe is not code-signed: a friend clicks More info > Run anyway; some company PCs block unsigned apps | **No free way is left.** The [SignPath Foundation](https://signpath.org/) program declined Arcas on 2026-11-03: it needs public visibility (stars, forks, outside write-ups), not better code, and invited a reapply once the project is better known. The cheap paid options are Certum's Open Source Code Signing in the cloud (about $58, for a public non-commercial project, identity checked against ID documents) and Microsoft's Azure Artifact Signing ($9.99 a month, individuals in the USA and Canada). Neither gives instant SmartScreen quiet: signing removes "unknown publisher", and the file's reputation then builds over downloads under one unchanged signing identity | **John** buys a certificate (his card and his ID: no one else can pass identity validation); then one ticket wires the signing step into `build-exe.yml`. A `winget` listing (below) is the free lane that skips the download warning for the people who use it |
| One-line install | A download link | [winget](https://github.com/microsoft/winget-pkgs): a free listing so a friend can install it with one `winget install` command (the package's id is chosen at submission); a pull request to Microsoft's list per release | **John** (a pull request from his GitHub account). Since SignPath declined (above), this is the only free way to spare a friend the warning: a `winget install` is not a browser download, so SmartScreen's download box never appears |
| Updates | Download again and double-click; settings stay | A pane note "a newer version is out" would need the engine to ask GitHub, a new call off the PC that the privacy pages must name | **John** decides whether that call is worth it |
| Mac | Not supported (the installer uses Windows-only pieces) | A Mac build is possible (free macOS CI runners for public repos) but needs a Mac installer, keychain trust and its own fresh-Mac test: a project of its own | **John** decides if Mac users matter enough |
| Excel on the web | Not supported | Not while the engine runs on the user's PC: every viewer would still need the engine installed and trusted, Excel on the web shows add-ins inside its own page, and the pane refuses to be framed (`frame-ancestors 'none'`, measured: desktop Excel shows it top-level) | Stays out by design |

## What a friend needs today (the honest list)
Windows 10 or 11 (64-bit), desktop Excel for Microsoft 365, about 75 MB of disk, a Windows account that is an
administrator on the PC, and the `C$` admin share left on (the installer registers the add-in through it, and Windows
opens that share to administrators only). No Python, no elevation prompt, no internet after the download. AI help
is optional and works with the friend's own free Google key or an invite code from John.
