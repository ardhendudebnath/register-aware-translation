# Putting Setu online

The blueprint's next step is to show this to twenty people and watch their
faces at the moment they see one sentence in four registers. That needs a URL.

This file is what stands between the repository and one, and the first section
is the part that is not about hosting.

---

## Read this before the app has a public URL

Two features are device-local by design. There is no login here, so on your
laptop "device-local" is enforced by the fact that only you can reach
localhost. The moment the app has a public address, nothing enforces it.

**Relationship memory** stores who you are deferential to — about as sensitive
as a contact list gets. `GET /api/relationships` hands back the whole list to
whoever asks, so on a shared server the first visitor's *"Rahul's father —
আপনি"* is readable by the second.

**The phrasebook** is a durable record of every sentence anybody typed, in a
file on a machine they do not own.

So a shared deployment sets one variable:

```bash
SETU_SHARED=1
```

which closes the relationship endpoints with a 403 that explains itself, hides
the panel in the UI, and makes the phrasebook ephemeral — still a cache, still
fast, lost with the process. Translation, conversation mode, the register pad
and learner mode all work unchanged.

**It is not authentication and does not pretend to be.** It is the difference
between a demo that cannot leak those two things and one that does. If you ever
want relationship memory on a real deployment, it needs accounts, and that is a
different project.

---

## The smallest thing that works

```bash
docker build -t setu .
docker run -p 5000:5000 -e SETU_SHARED=1 setu
```

Then open <http://localhost:5000>. That is the whole application: Python, about
thirty megabytes of pure-Python packages, no model weights. Speech in and out
are the browser's own APIs, so there is nothing to pay for and nothing to
install.

### What it costs to run

Almost nothing, and the reasons are structural rather than frugal:

| | |
|---|---|
| The register layer | pure string processing, ~1 ms, no network, no model |
| Speech in / out | the visitor's browser, not your server |
| Translation | a keyless public endpoint, cached per phrase |
| Memory | a few hundred MB; it loads no weights unless you install the optional extras |

A single small instance is enough for twenty people looking at it in the same
afternoon. If you later install `requirements-speech.txt`, that changes
completely — Whisper wants a gigabyte or more — and you should size for the
model rather than the app.

---

## Somewhere to put it

Any host that can run a container and give you a TLS certificate will do. What
matters is in the table, not the brand.

| What to check | Why it matters here |
|---|---|
| **HTTPS** | The microphone does not work without it. Browsers refuse `getUserMedia` on plain HTTP from anything but localhost, so an http:// demo is a typing demo. |
| **WebSockets** | Speculative translation — the greyed-out preview while you are still speaking — runs over socket.io. Without them it falls back to polling and the preview arrives late. |
| **One process** | Conversations live in memory. Two instances behind a load balancer will lose half of them. Scale up before scaling out. |
| **A writable `data/`** | Only if you are *not* running shared. Otherwise nothing is written and you can mount nothing. |

A single container with `SETU_SHARED=1`, HTTPS terminated by the host, and no
volume at all is the configuration this was built for.

### Environment

| Variable | Default | Meaning |
|---|---|---|
| `SETU_SHARED` | off | More than one person can reach this. See above. |
| `SETU_HOST` | `127.0.0.1` | Bind address. The Dockerfile sets `0.0.0.0`. |
| `SETU_PORT` | `5000` | Port. Some hosts inject their own; pass it through. |
| `SETU_ALLOW_NETWORK` | `1` | `0` forbids outbound calls. The register layer still works; translation falls back to the cache. |
| `SETU_DEBUG` | off | Never on a public URL. |
| `SETU_MT_TIMEOUT` | `6` | Seconds before the MT endpoint is abandoned. |

---

## Before you send anyone the link

- [ ] `SETU_SHARED=1` is set, and `/api/relationships` returns 403.
- [ ] The URL is `https://`, and the microphone button works on a phone.
- [ ] `/api/health` returns `"status": "ok"` and reports the backends you expect.
- [ ] `SETU_DEBUG` is off.
- [ ] You have tried one sentence in each of the three or four languages you
      will be asked about, because the first question anyone asks is "what
      about mine?".

## What to watch for once it is up

The blueprint is blunt that a week of real use will produce a different list
from any document, including itself. The two worth watching:

**The MT endpoint is undocumented and rate-limited.** It can start refusing
under a crowd. The app degrades to "here's what I heard" rather than failing,
but the translations stop being translations. If that happens, a Sarvam or
Bhashini key is the fix, and that means a paid account.

Shared mode therefore limits the paths that reach it: forty finished
translations a minute per address, and three hundred speculative partials,
which is generous for a person and useless to a script wanting a corpus
translated. Local work — re-levelling, detection, the register pad — is never
limited, because none of it leaves the machine. It is not a security control:
the forwarded header it counts by is forgeable by anyone talking to the server
directly. It stops accidents and casual abuse, which is what a demo shown to
twenty people actually faces.

**Register mistakes are the actual signal.** Every time the app gets the
register wrong for somebody, that is a row for a gold set, which is the asset
this project is really building. Write them down.
