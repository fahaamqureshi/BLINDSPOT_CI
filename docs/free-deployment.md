# Free public deployment

This guide deploys the scripted mock demo. It does not use a model API key, private photos, or a paid plan. The owner must connect the repository and create any hosting or monitoring accounts. Do not put a key in the public service.

## Primary host: Northflank

Northflank is the primary choice. It is listed in the PaaS section of [ripienaar/free-for-dev](https://github.com/ripienaar/free-for-dev), builds a Dockerfile from a connected Git repository, gives a public HTTPS endpoint, and has a free Sandbox that does not require a card. It is a better fit than a sleeping free instance for a short demo because the official pricing page says the free Sandbox is always on.

Use the owner-operated Northflank dashboard. Do not select a paid plan, Pay as you go, or bring your own cloud option.

1. Create or select the Developer Sandbox. The official pricing page currently lists two services, two jobs, one database, and up to 20 USD per month of Northflank Cloud resources at no charge. It also says no card is needed and that the free Sandbox does not sleep.
2. Create a combined service from the public GitHub repository `github.com/fahaamqureshi/BLINDSPOT_CI`, using the `main` branch and the root `Dockerfile`.
3. In Configure, Networking, expose port `8000` as a public HTTP port. Name the port `web`. Northflank exposes public HTTP ports on HTTPS port 443 and routes them to the container port.
4. Add a health check for `GET /health` on port `8000`.
5. Set these runtime environment variables:

```text
BLINDSPOT_PROVIDER=mock
BLINDSPOT_HOST=0.0.0.0
BLINDSPOT_PORT=8000
BLINDSPOT_ALLOWED_HOSTS=web--blindspot-ci--random-string.code.run
```

Replace the last value with the exact generated public hostname shown by Northflank. The hostname normally follows `[port-name]--[service-name]--[random-string].code.run`; the exact cluster suffix can vary. Set the hostname without `https://`. The application matches hosts exactly, so do not use a wildcard. If the service or port name changes, update `BLINDSPOT_ALLOWED_HOSTS` and redeploy. Northflank also exposes the generated hostnames in its `NF_HOSTS` runtime variable, but using the displayed exact value is the clearest setup.

6. Deploy and test `/health`, `/`, `/app`, and `/guide`. `/demo` should redirect to `/`. Open `/app?run=a165cd6773cd433a&dataset=coco` to show the saved COCO example.

Do not set `LIVE_API_ENABLED=true` and do not add `MODEL_API_KEY`. The Dockerfile already uses port 8000 and starts `python -m blindspot_ci.cli serve`. The application writes new run artifacts and cache files to the container filesystem. No volume is configured, so those new files are temporary. The committed fixtures and saved example are the durable part of this demo.

Northflank sources checked on 2026-11-03:

1. [Northflank pricing](https://northflank.com/pricing) verifies the free Sandbox, no card requirement, two services, two jobs, one database, up to 20 USD per month of free Northflank Cloud resources, and always-on behavior.
2. [Build and deploy your code](https://northflank.com/docs/v1/application/getting-started/build-and-deploy-your-code) verifies Git repository builds, Dockerfile selection, public ports, and health checks.
3. [Configure ports](https://northflank.com/docs/v1/application/network/configure-ports) verifies the generated `code.run` hostname pattern and routing from public HTTPS to the configured container port.
4. [Inject secrets](https://northflank.com/docs/v1/application/secure/inject-secrets) documents the `NF_HOSTS` value.

Verified free facts are the limits and features stated above. The exact CPU, memory, bandwidth, and per-service quota assigned to a particular free Sandbox are not stated on the pricing page and are therefore unverified here. Keep this small mock service inside the displayed free resource allowance. If Northflank asks for an upgrade, stop instead of selecting paid usage.

## Fallback host: Koyeb

Koyeb is the fallback because it is also listed by [ripienaar/free-for-dev](https://github.com/ripienaar/free-for-dev) and supports building a Dockerfile from a GitHub repository.

Use the [Koyeb deploy flow](https://app.koyeb.com/deploy?name=blindspot-ci&repository=github.com/fahaamqureshi/BLINDSPOT_CI) as the owner.

1. Choose the public GitHub repository or connect the owner's GitHub account.
2. Select the `main` branch and choose the Dockerfile builder.
3. Select the Free Instance. Expose port `8000` as HTTP and route `/` to that port. Add an HTTP health check for `/health` on port 8000.
4. Set the environment variables below. Replace the allowlist value after Koyeb shows the generated `.koyeb.app` hostname.
5. Deploy, wait for the first build, then test `/health`, `/`, `/app`, and `/guide`. Check that `/demo` redirects to `/`.

```text
BLINDSPOT_PROVIDER=mock
BLINDSPOT_HOST=0.0.0.0
BLINDSPOT_PORT=8000
BLINDSPOT_ALLOWED_HOSTS=your-service-your-org-your-id.koyeb.app
```

Koyeb's [Free Instance documentation](https://www.koyeb.com/docs/reference/instances) verifies one Free Instance per organization with 512 MB RAM, 0.1 vCPU, and 2 GB SSD. It can run only in Frankfurt or Washington, DC, cannot use volumes or custom scaling, and scales to zero after one hour without traffic. The [Koyeb pricing FAQ](https://www.koyeb.com/docs/faqs/pricing) says the free web service is never charged, but it also says an account must always have a valid payment method. That card requirement makes Koyeb a fallback rather than the primary owner path here. [Git deployment documentation](https://www.koyeb.com/docs/build-and-deploy/deploy-with-git) verifies repository builds, and [service exposure documentation](https://www.koyeb.com/docs/build-and-deploy/exposing-your-service) explains HTTP port and route settings.

The Koyeb Free Instance has no persistent volume. Treat artifacts and cache files as temporary. A cold start follows the one-hour idle period.

## Cloudflare verdict

Cloudflare cannot host this application unchanged. The repository is a Python Docker server whose entry point is `python -m blindspot_ci.cli serve`. It uses FastAPI and Uvicorn, serves several HTML pages, exposes `/api/examples` and `/api/runs/<run-id>`, and writes artifacts and cache files to a local filesystem.

Cloudflare Pages can host static HTML, CSS, JavaScript, and other static assets. Pages Functions add server-side routes, but they run in the Cloudflare Workers runtime and are written as JavaScript or TypeScript handlers. Pages does not run this repository's Dockerfile, CPython process, Uvicorn server, or filesystem-backed FastAPI application. A Pages port would require a rewrite of the application and its API routes.

Cloudflare Workers run JavaScript, TypeScript, WebAssembly, and Python Workers. Python Workers are Python compiled to WebAssembly through Pyodide inside a V8 isolate, not a general Python container. Cloudflare documents that Python packages must be pure Python or have PyEmscripten wheels, `threading` and `multiprocessing` are not functional, and the filesystem is ephemeral in memory and not shared between isolates. The Workers Free plan currently limits each isolate to 128 MB memory, each request to 10 ms CPU time, and the account to 100,000 requests per day. Although Cloudflare documents a FastAPI package example for Python Workers, adapting this application would still require a Worker entry point, compatible dependencies, and a storage redesign. It cannot run the existing Docker command unchanged.

The official evidence is [Pages static HTML](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/), [Pages Functions](https://developers.cloudflare.com/pages/functions/), [Pages Functions TypeScript](https://developers.cloudflare.com/pages/functions/typescript/), [Pages Functions pricing](https://developers.cloudflare.com/pages/functions/pricing/), [Python Workers](https://developers.cloudflare.com/workers/languages/python/how-python-workers-work/), [Python Worker packages](https://developers.cloudflare.com/workers/languages/python/packages/), [Python Worker standard library](https://developers.cloudflare.com/workers/languages/python/stdlib/), and [Workers limits](https://developers.cloudflare.com/workers/platform/limits/).

Cloudflare can still help in two free ways:

1. A Quick Tunnel can temporarily publish a running local server. It does not host the process. The owner must keep the laptop and the application running.
2. Cloudflare DNS and proxying can sit in front of a separately hosted Northflank or Koyeb origin when the owner has a domain. The other host still runs the Docker server. Cloudflare Tunnel can also publish a separately hosted origin through an outbound `cloudflared` connection. A named Tunnel needs an account and a domain; Cloudflare documents that publishing an application does not require a paid Access plan, but Access policies and account setup are owner actions. The Zero Trust Free plan is not charged, but its official onboarding still asks for payment details, so it is not a no-card path.

### Temporary demo-day Quick Tunnel

The owner runs these steps. The agent does not install `cloudflared`, create a Cloudflare account, create a Tunnel, or open a tunnel.

1. Install `cloudflared` using the owner's normal Windows package method.
2. In PowerShell terminal one, start the mock server:

```powershell
$env:BLINDSPOT_PROVIDER = "mock"
$env:BLINDSPOT_HOST = "0.0.0.0"
$env:BLINDSPOT_PORT = "8000"
$env:BLINDSPOT_ALLOWED_HOSTS = "localhost,127.0.0.1"
python -m blindspot_ci.cli serve
```

3. In PowerShell terminal two, run the official Quick Tunnel command and override the origin Host header so the application's exact local allowlist still accepts the request:

```powershell
cloudflared tunnel --url http://localhost:8000 --http-host-header localhost
```

4. Open the random `https://something.trycloudflare.com` URL printed by `cloudflared`, then check `/health`, `/`, `/app`, and `/guide`. `/demo` should redirect to `/`.
5. Keep both terminals and the laptop online for the whole demo. Stop `cloudflared` with Ctrl+C when finished.

Quick Tunnels need no Cloudflare account or domain, but the URL is random and temporary. Anyone with the URL can access it. Cloudflare documents no uptime guarantee, a maximum of 200 in-flight requests, no Server-Sent Events support, and a URL that stops working when the process stops. This is a temporary demo option, not a public deployment or production service. See [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [Tunnel fundamentals](https://developers.cloudflare.com/tunnel/concepts/), and [Tunnel origin parameters](https://developers.cloudflare.com/tunnel/reference/origin-parameters/).

## Host comparison

| Host | Dockerfile from Git | Free terms verified on 2026-11-03 | Sleep and storage | Card or paid-plan requirement | Decision |
| --- | --- | --- | --- | --- | --- |
| Northflank | Yes, connected Git repository | Verified: Free Sandbox, two services, two jobs, one database, up to 20 USD per month of Northflank Cloud resources | Verified always on; no free volume selected, so app writes are temporary | Verified no card needed; do not select paid usage or BYOC | Primary |
| Koyeb | Yes, Git repository and Dockerfile builder | Verified: one Free Instance per organization, 512 MB RAM, 0.1 vCPU, 2 GB SSD | Verified Frankfurt or Washington, DC; sleeps after one hour; no volume | Verified free service is not charged, but a valid payment method is required | Fallback |
| Hugging Face Spaces Docker | Yes, a Space Git repository can contain a Dockerfile | Verified hardware is 2 vCPU, 16 GB RAM, and 50 GB non-persistent disk, but Docker Spaces require PRO, Team, or Enterprise to create | Verified free CPU Basic sleeps after 48 hours; disk is lost on restart | Verified paid plan required for Docker Spaces | Rejected as not fully free |
| Cloudflare Pages or Workers | No unchanged Docker server | Verified static Pages and JavaScript or TypeScript Functions; Workers Free has 100,000 requests per day, 128 MB memory, and 10 ms CPU per request | Worker filesystem is ephemeral; application rewrite required | Verified Cloudflare account or domain requirements depend on product | Not a host for this code |
| Cloudflare Quick Tunnel | No, it forwards to another running origin | Verified free temporary `trycloudflare.com` URL | Laptop and local process must stay on; no durable storage | Verified no account or domain for Quick Tunnel | Temporary demo only |

Hugging Face evidence is [Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview), [Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker), and [Spaces hardware and sleep](https://huggingface.co/docs/hub/spaces-gpus). The current documentation says Docker Spaces run on compute and require a paid plan to create, so the otherwise attractive free CPU hardware does not meet the fully-free requirement.

## CI and automatic redeploys

The existing GitHub Actions workflow runs ruff and pytest on pushes and pull requests. Keep the required checks passing before merging to `main`. After the owner connects `main`, Northflank can auto-deploy pushes to its tracked branch. Koyeb can also auto-deploy pushes to its tracked branch. The [CI and CD section of free-for-dev](https://github.com/ripienaar/free-for-dev#ci-and-cd) was used as a directory of free CI options; this project does not need another CI provider for the demo.

## Optional free uptime monitor

After the owner has deployed the service, add one HTTP monitor for `https://your-hostname/health` in [Better Stack Uptime](https://betterstack.com/uptime). The [free-for-dev Monitoring section](https://github.com/ripienaar/free-for-dev#monitoring) lists Better Stack. Better Stack's [check-frequency documentation](https://betterstack.com/docs/uptime/check-frequency/) documents the free-plan interval.

Use the owner's email for alerts. Monitoring does not keep a Northflank or Koyeb service awake continuously, and an uptime check can still observe a cold start on Koyeb. A monitor is optional and must not be configured by an agent without the owner's account.

## Why these services

The requested sections of [ripienaar/free-for-dev](https://github.com/ripienaar/free-for-dev) were reviewed: PaaS, Web Hosting, Monitoring, and CDN and Protection. Northflank is the primary because it combines Dockerfile builds from Git, public HTTPS, no card, and always-on free Sandbox behavior. Koyeb remains a useful fallback with clearly documented small limits. Hugging Face Docker Spaces was compared and rejected because current official documentation requires a paid plan. Cloudflare is useful as a temporary tunnel or as DNS and proxying in front of a real origin, but it is not the origin host for this Python Docker application.

Free-tier claims can change. This guide marks provider facts as verified against the linked pages on 2026-11-03. Check the official page again before deploying if the hackathon deadline or provider dashboard shows different terms.

## Attribution

The free-service directory consulted for this guide is [ripienaar/free-for-dev](https://github.com/ripienaar/free-for-dev). The directory is not part of the application and is not copied into the repository.
