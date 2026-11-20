# Security policy

## Supported versions

Security fixes are made on the latest release.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private
vulnerability reporting ("Security" tab → "Report a vulnerability") on this repository. Please include:

- the affected version or commit;
- steps to reproduce;
- the impact you expect.

You should receive an acknowledgement within a few days.

## Deployment notes

MechDesign Agent is designed as a **local, single-user tool**.

- The server binds to `127.0.0.1` by default. It has **no authentication**, and it is not
  hardened for exposure to untrusted networks. If you bind it to `0.0.0.0` (for example in Docker),
  put it behind your own authentication or reverse proxy.
- `ANTHROPIC_API_KEY` is read only by the Python process, from the environment or a local `.env` file.
  It is never sent to the browser. `.env` is listed in `.gitignore`; never commit it.
- With an API key configured, `/api/interpret` and `/api/explain` call the Anthropic API, so anyone
  who can reach the server can spend your API quota.
- Grid size is capped (400 values per axis, 40 000 candidates) to bound CPU and memory per request.
