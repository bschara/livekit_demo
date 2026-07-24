# LiveKit Live-Broadcast POC

**Live instance:** [https://app-145.241.219.123.sslip.io/](https://app-145.241.219.123.sslip.io/)

A proof of concept: one broadcaster streams live camera/mic to any number of
simultaneous viewers, built on a self-hosted [LiveKit](https://livekit.io) SFU,
a Django REST API for token issuance, and a small React frontend. Viewers
aren't just passive — anyone watching can turn on their own camera/mic to
interact with the broadcaster, who sees and hears them (and so does everyone
else watching), the way a co-host or a caller-in would.

## Architecture

```
Broadcaster browser ──WebRTC──▶  LiveKit SFU (Docker)  ◀──WebRTC── Viewer browser #1
                                        ▲  ▲                        ◀──WebRTC── Viewer browser #2
                                        │  │                        ◀──WebRTC── Viewer browser #N
                      issues room grants│  │ REST: mint token / list rooms
                                        │  │
                                  Django REST API (DRF)
                                        ▲
                                        │ HTTP
                                  React (Vite) frontend
                            (Home / Broadcast / Watch pages)
```

- **LiveKit is an SFU (Selective Forwarding Unit), not a mesh.** The broadcaster
  uploads their camera/mic stream once; LiveKit fans it out to every subscriber
  server-side. The broadcaster's upload bandwidth stays flat no matter how many
  people are watching — that's the core scalability property that makes this
  approach viable beyond a handful of viewers, unlike naive peer-to-peer WebRTC
  where the broadcaster's upload cost grows linearly with viewer count.
- **Django never touches media.** Its only job is minting short-lived, scoped
  LiveKit access tokens (JWTs) — everyone gets `canPublish` and `canSubscribe`,
  since viewers can opt into camera/mic — and optionally listing active rooms
  so the UI can show "live now" without guessing. "Broadcaster" vs "viewer" is
  really just an identity prefix (`broadcaster-…`) the frontend uses to tell
  who's the host, not a hard permission split. Once a client has a token it
  talks to LiveKit directly over WebSocket/WebRTC; the Django API is
  completely out of the media path and could be scaled or replaced
  independently of it.
- **React + `livekit-client`** handle the actual Room connection, camera/mic
  publishing, and remote track rendering. The Watch page defaults to
  subscribe-only but has "Turn on camera"/"Turn on mic" buttons; any tracks a
  viewer publishes show up as "guest" tiles on both the broadcaster's page and
  every other viewer's page, via a shared `useRemoteTracks` hook (see
  `frontend/src/lib/useRemoteTracks.js`).

## Repo layout

```
livekit-demo/
  docker-compose.yml   # livekit-server, redis, egress, minio, minio-init
  livekit.yaml          # LiveKit server config (port, RTC port range, API keys)
  backend/               # Django REST API
    config/               # settings, urls
    streaming/             # POST /api/token/, GET /api/rooms/, recordings, webhook
  frontend/              # Vite + React app
    src/pages/             # HomePage, BroadcastPage, WatchPage, RecordingsPage
    src/lib/api.js          # talks to the Django API
```

## Running it locally

**1. LiveKit server (+ Redis, Egress, MinIO)**
```bash
docker compose up -d
```
Runs LiveKit in a container, config from `livekit.yaml` (signaling on `:7880`,
RTC media on `:7881` TCP / `50000-50100` UDP). If you edit `livekit.yaml`, run
`docker compose restart livekit` — LiveKit only reads its config at startup, so
just leaving the container "up" won't pick up file changes.

This also brings up three more services needed for recording (see
"Recording broadcasts" below): **Redis** (LiveKit's Egress process only
talks to the core server over Redis, even single-node), **Egress**
(`livekit/egress`, records rooms — runs with the same host networking as
`livekit` since it joins rooms like any other WebRTC client), and **MinIO**
(self-hosted S3-compatible storage for the recorded files, with a
`minio-init` one-shot container that creates the `recordings` bucket
automatically). None of this is required just to broadcast/watch live —
only for the recording feature.

**2. Django API**
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # LIVEKIT_API_KEY/SECRET here must match livekit.yaml
python manage.py migrate
python manage.py runserver
```

**3. React frontend**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:5173`, enter a name, click **Go live** in one tab and
**Watch stream** in as many others as you like — every viewer subscribes to
the same broadcaster through the LiveKit SFU.

## Deployment

The live instance linked at the top runs on a single VPS, not a laptop/tunnel:

- **Docker Compose** brings up the same `livekit`/`redis`/`egress`/`minio`
  stack as local dev. `livekit` and `egress` run with `network_mode: host` so
  RTC ports bind directly to the VPS's network stack (see the docker-proxy/RAM
  note above) — `use_external_ip: true` in `livekit.yaml` so LiveKit
  advertises the VPS's real public IP as its ICE candidate.
- **MinIO** stores recordings, reachable through its own subdomain in nginx
  so presigned playback URLs load over HTTPS without a mixed-content block
  (see `deploy/nginx.conf.example`).
- **Django** runs under gunicorn as a systemd service
  (`deploy/livekit-backend.service`), not `manage.py runserver`.
- **nginx** reverse-proxies three (sub)domains onto that stack — the built
  frontend + Django API, LiveKit's WebSocket signaling, and MinIO — each
  getting its own certbot-issued TLS cert (`deploy/nginx.conf.example` has
  the full setup, including sslip.io as a no-DNS-needed option). RTC media
  itself (`7881/tcp`, `50000-50100/udp`) isn't proxied through nginx at all —
  it needs to be reachable directly, so those ports are opened on the VPS's
  firewall/security group separately.

## Recording broadcasts

The broadcaster's page has a **Start recording**/**Stop recording** button.
It records the full room composite — the broadcaster plus any interacting
guest tiles, i.e. exactly what a viewer sees — via LiveKit's
`RoomCompositeEgress`, uploaded to the self-hosted MinIO bucket brought up by
`docker compose`. Recordings show up on the **Recordings** page (linked from
the home page) once processing finishes, each playable inline.

Recording is deliberately manual (not automatic on broadcaster join) — you
decide what's worth keeping. If a broadcaster disconnects without clicking
**Stop recording**, a `room_finished` LiveKit webhook stops it automatically
so nothing records indefinitely; either way, the recording only flips to
"ready" on the Recordings page once LiveKit's `egress_ended` webhook confirms
the upload actually finished (this happens a few seconds after you click
Stop, not instantly).

## Assumptions & known limitations

- **No real auth — deliberately, not an oversight.** `livekit.yaml` ships with
  a single hardcoded API key/secret pair and Django's `/api/token/` endpoint
  will mint a token for anyone who calls it with any name — there's no login
  system. This POC is scoped to proving the broadcast/multi-viewer mechanics
  (LiveKit SFU, token issuance, recording), demoed live to a known, trusted
  audience — adding a full auth layer wouldn't have demonstrated anything
  extra about real-time communication and would have spent time better used
  elsewhere. The first thing to add before this went further would be tying
  token issuance to real Django user accounts/sessions, so `canPublish` /
  identity aren't self-asserted by whoever calls the API.
- **NAT traversal relies on STUN, not TURN — and STUN needs a real inbound
  path to work at all.**
  ([NAT](https://en.wikipedia.org/wiki/Network_address_translation), STUN,
  TURN, and ICE, briefly: most devices sit behind **NAT**, so two browsers
  can't just dial each other directly — neither has a stable public address.
  **STUN** fixes this cheaply: a peer asks a public STUN server "what address
  do you see me as?" and uses that reflected address (a "server-reflexive
  candidate") to receive traffic — but it only works if the network actually
  routes inbound traffic back to that address; STUN can report a reflection,
  it can't open a door that isn't there. **TURN** is the fallback for when it
  can't: both peers connect *outbound* to a TURN relay (which is always
  possible) and it forwards every packet between them, trading a bit of
  latency for guaranteed connectivity even through symmetric NATs or
  restrictive firewalls. **ICE** is the umbrella algorithm tying this
  together — each side gathers every candidate (local, STUN-reflexive, and
  TURN-relay if configured), exchanges them over the signaling channel
  (LiveKit's WebSocket here), tries every pair, and uses the first one that
  actually connects, preferring direct over relayed.) Hit this directly while
  testing: with `use_external_ip: true`, LiveKit advertised a STUN-discovered "external" IP
  that was outbound-reachable only (no inbound route back into the sandboxed
  host), so *every* ICE candidate pair failed and the browser never got past
  "connecting" — camera/mic were never even requested, since `room.connect()`
  fails before that point. The server logs made this obvious: `state: failed,
  requestsSent: 8, responsesReceived: 0` for every candidate pair. STUN only
  tells a peer what address the outside world sees for it; it does not by
  itself forward traffic in, so it's only useful when that discovered address
  is genuinely reachable (a real public IP, or one with the RTC ports
  forwarded). Local/same-machine testing now runs with `use_external_ip:
  false` so LiveKit advertises its own local address instead. For viewers on
  other networks, `use_external_ip` needs to go back to `true` *with* the RTC
  ports actually forwarded — otherwise it's the same failure again, just for
  everyone instead of just localhost. The most robust production fix is
  LiveKit's built-in TURN server on port 443/TCP, which relays media over the
  one port that's essentially always reachable, at the cost of media taking a
  relayed path instead of a direct one.
- **Widening the RTC UDP port range once crashed the VPS by exhausting RAM.**
  The port range was originally published via Docker's `-p` flag; widening it
  to `50000-60000` (~10,001 ports) spawned one `docker-proxy` subprocess per
  published port — roughly 10,000 processes on every container start,
  exhausting host memory/PIDs and crashing the instance. Docker's
  userland-proxy model creates a subprocess per published port, which is fine
  for a handful of ports but catastrophic for a 10,000-port UDP range. Fixed
  by switching the `livekit` (and `egress`) services to `network_mode: host`
  in `docker-compose.yml`, which binds directly to the host's network stack
  with no per-port proxy at all (see commit `1a50f1b`); the committed range
  is now narrower (`50000-50100`) for local dev, independent of that fix.
- **Any viewer can publish, with no moderation.** Turning on camera/mic is a
  client-side toggle with no approval step — anyone who joins the room can
  interact, and there's no mute-others or remove-participant control on the
  broadcaster's page. Reasonable for a small demo with a known, trusted
  audience; a real version of this would need the broadcaster to approve
  guests before they go live (e.g. only granting `canPublish` once the
  broadcaster accepts a request, via LiveKit's participant permission update
  API) and a way to mute/remove someone.
- **Single-room-by-default UX.** The frontend defaults everyone to a shared
  room name (`main-stream`) for simplicity in the demo; it's just a text
  field, so multiple concurrent broadcasts in different rooms already work,
  they're just not surfaced anywhere in the UI.
- **No persistence beyond recordings.** Django still holds no state about
  live streams themselves — "is a room live" is answered by asking LiveKit
  directly (`GET /api/rooms/`) — but recordings are the one exception, now
  tracked in a `Recording` model (see "Recording broadcasts" above).
- **Recording playback has no auth beyond a presigned URL's expiry.**
  Anyone with a recording's link can watch it until the URL expires (1 hour),
  same "no real auth" posture as the rest of this POC. There's also no
  storage retention/cleanup policy for MinIO — recordings accumulate
  indefinitely; a real version of this would need both a proper auth check
  on `GET /api/recordings/` and a retention policy for old files.

## Scaling beyond this POC

- **Single LiveKit node → cluster.** This setup runs one `livekit-server`
  container. LiveKit supports multi-node clustering behind Redis for horizontal
  scale — the SFU work (encoding/forwarding) is what actually needs to scale
  with concurrent viewers, and that's what clustering distributes.
- **WebRTC SFU has a practical viewer ceiling** (tens to low hundreds per
  publisher on a single node, more with clustering) because every viewer is a
  live, stateful connection. For audiences beyond that, the standard next step
  is **LiveKit Egress**: have the SFU also push the stream out to HLS/RTMP and
  serve viewers through a CDN instead of a direct WebRTC subscription — trades
  latency (seconds instead of sub-second) for near-unlimited viewer fan-out.
- **Django API is already stateless**, so it scales horizontally behind a load
  balancer independent of the LiveKit tier without any changes.
- **WSGI, not ASGI, and that's deliberate.** The Django API runs under WSGI
  (`gunicorn config.wsgi:application` — see `deploy/livekit-backend.service`)
  even though it calls an async-only client (`livekit-api`'s `LiveKitAPI`,
  built on `aiohttp`) via `asyncio.run()` inside each sync view. That's not an
  oversight: Django never sits in the media/signaling path (browsers talk to
  LiveKit directly over WebRTC), so the API only ever handles short REST
  calls — issuing JWTs, listing rooms, starting/stopping egress — not
  high-concurrency or long-lived connections. DRF's `APIView` also doesn't
  support `async def` handlers natively (`dispatch()` calls the handler
  without awaiting it), so async views would require dropping to plain
  Django views or adding a third-party layer like `adrf`. If this API ever
  needed to sustain heavy concurrent traffic to LiveKit's HTTP API, the move
  would be ASGI (uvicorn/daphne) + `adrf`, so each request's worker thread is
  freed during the LiveKit round-trip instead of blocking on it — but at this
  POC's traffic scale, that concurrency gain doesn't exist to capture, and
  the actual viewer-scaling story is LiveKit's SFU/clustering above, not
  Django's request-serving model.

## Enhancements if this became a real product

- Real authentication (Django-user-backed tokens instead of open self-serve).
- Recording every broadcast via LiveKit Egress for on-demand playback.
- Reconnection/backoff UX polish for flaky networks (LiveKit's client SDK
  exposes reconnect events that the UI currently doesn't surface).
- Moving off dev-mode LiveKit keys and adding TURN/TLS for guaranteed
  connectivity from any network, as noted above.
- Chat/reactions alongside the stream using LiveKit's data channel API, which
  the current token grants (`canPublishData`) already allow.
