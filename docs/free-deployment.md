# Free public deployment

This guide deploys the scripted mock demo. It does not use a model API key, private photos, or a paid plan. The owner must connect the repository and create any hosting or monitoring accounts. Do not put a key in the public service.

## Recommended host: Render

Render is the primary choice because this repository already contains `render.yaml` and `Dockerfile`. The free Render web service supports Docker-backed web apps and gives the service a public HTTPS address.

Start with the [Deploy to Render flow](https://render.com/deploy?repo=https://github.com/fahaamqureshi/BLINDSPOT_CI). Review the Blueprint before approving it.

1. Sign in to Render as the owner and connect the GitHub repository.
2. Choose the Blueprint from `render.yaml` on the `main` branch.
3. Approve the free web service. The Blueprint builds `Dockerfile`, starts its existing command, and checks `GET /health`.
4. Open the service URL. The expected default is `https://blindspot-ci.onrender.com`. If Render assigns another hostname, replace the value of `BLINDSPOT_ALLOWED_HOSTS` with that hostname and redeploy.
5. Test `/health`, `/`, `/app`, and `/guide`. `/demo` should redirect to `/`. Open `/app?run=a165cd6773cd433a&dataset=coco` to show the saved COCO example.

The exact public-demo environment is:

```text
BLINDSPOT_PROVIDER=mock
BLINDSPOT_HOST=0.0.0.0
BLINDSPOT_PORT=10000
BLINDSPOT_ALLOWED_HOSTS=blindspot-ci.onrender.com
```

If the service name changes, set `BLINDSPOT_ALLOWED_HOSTS` to the actual hostname. A comma-separated value is allowed when testing more than one hostname. Do not set `LIVE_API_ENABLED=true` and do not add `MODEL_API_KEY`.

Render free limits and behavior are documented in [Deploy for Free](https://render.com/docs/free). The relevant constraints are 750 free instance hours per workspace each calendar month, spin-down after 15 minutes without traffic, about one minute to wake up, and an ephemeral filesystem. Saved runs written by the public service can disappear after a restart, redeploy, or spin-down. This demo is therefore a read-only showcase of committed fixtures, not durable storage.

Render requires a web service to bind to `0.0.0.0`; its default expected port is 10000, as described in [Render web services](https://render.com/docs/web-services). This repository sets `BLINDSPOT_PORT=10000` in `render.yaml`. The Dockerfile keeps its local container default at port 8000, so a local Docker run should map `8000:8000` unless `BLINDSPOT_PORT` is overridden.

## Fallback host: Koyeb

Koyeb is the fallback because the curated list includes it for free hosting and Koyeb supports building a Dockerfile from a GitHub repository.

Use the [Koyeb deploy flow](https://app.koyeb.com/deploy?name=blindspot-ci&repository=github.com/fahaamqureshi/BLINDSPOT_CI) as the owner.

1. Sign in to Koyeb and choose the public GitHub repository or connect the owner’s GitHub account.
2. Select the `main` branch and choose the `Dockerfile` builder.
3. Select the free instance. Expose port `8000` as HTTP and route `/` to that port. Add an HTTP health check for `/health` on port 8000.
4. Set the environment variables below. Replace the allowlist value after Koyeb shows the generated `.koyeb.app` hostname.
5. Deploy, wait for the first build, then test `/health`, `/`, `/app`, and `/guide`. Check that `/demo` redirects to `/`.

```text
BLINDSPOT_PROVIDER=mock
BLINDSPOT_HOST=0.0.0.0
BLINDSPOT_PORT=8000
BLINDSPOT_ALLOWED_HOSTS=your-service-your-org-your-id.koyeb.app
```

Koyeb’s [free instance documentation](https://www.koyeb.com/docs/reference/instances) verifies one free instance per organization with 512 MB RAM, 0.1 vCPU, and 2 GB SSD. It is limited to Frankfurt or Washington, DC, cannot use volumes or custom scaling, and scales to zero after one hour without traffic. Koyeb’s [GitHub deployment documentation](https://www.koyeb.com/docs/build-and-deploy/deploy-with-git) verifies Dockerfile builds from a repository. Its [service exposure documentation](https://www.koyeb.com/docs/build-and-deploy/exposing-your-service) explains the HTTP port and route settings.

Koyeb may provide a `PORT` variable, but this project uses `BLINDSPOT_PORT`, so set the latter explicitly as shown. The Dockerfile default and the fallback settings both use port 8000. The free instance has no persistent volume, so treat local writes as temporary.

## CI and automatic redeploys

The existing GitHub Actions workflow runs ruff and pytest on pushes and pull requests. Keep the required checks passing before merging to `main`. After the owner connects `main`, Render auto-deploys pushes according to the Blueprint, while Koyeb can auto-deploy pushes to its tracked branch. The [CI and CD section of free-for-dev](https://github.com/ripienaar/free-for-dev#ci-and-cd) was used as a directory of free CI options; this project does not need another CI provider for the demo.

## Optional free uptime monitor

After the owner has deployed the service, add one HTTP monitor for `https://your-hostname/health` in [Better Stack Uptime](https://betterstack.com/uptime). The [free-for-dev Monitoring section](https://github.com/ripienaar/free-for-dev#monitoring) lists Better Stack. Better Stack’s official page currently states that the free plan includes ten monitors, ten heartbeats, one status page, and three-minute checks. Its [check-frequency documentation](https://betterstack.com/docs/uptime/check-frequency/) confirms that three minutes is the free-plan interval.

Use the owner’s email for alerts. Monitoring does not keep a Render or Koyeb service awake continuously, and an uptime check can still observe a cold-start delay. A monitor is optional and must not be configured by an agent without the owner’s account.

## Why these services

The requested sections of [ripienaar/free-for-dev](https://github.com/ripienaar/free-for-dev) were reviewed: PaaS, Web Hosting, CI and CD, Monitoring, and CDN and Protection. Render and Koyeb are listed as hosting options, Better Stack is listed for monitoring, and the CDN section is useful background for services such as Cloudflare. No CDN or proxy is required for this small demo because both selected hosts provide public HTTPS. The list is a directory, not a dependency, and no part of it is vendored here.

Free-tier claims can change. This guide uses the provider pages linked above as the current evidence. Check the official page again before deploying if the hackathon deadline or provider dashboard shows different terms.

## Attribution

The free-service directory consulted for this guide is [ripienaar/free-for-dev](https://github.com/ripienaar/free-for-dev). The directory is not part of the application and is not copied into the repository.
