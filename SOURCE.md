# Runtime source

This deployment vendors the browser runtime from the GPL-licensed project:

- `arthurboss/claw-web` — https://github.com/arthurboss/claw-web
- based on `pjasicek/OpenClaw` — https://github.com/pjasicek/OpenClaw

The deployment workflow pins the exact runtime and source revisions in `.github/workflows/deploy-pages.yml`.

No original Captain Claw game archive (`CLAW.REZ`) is stored in this repository or deployed by GitHub Pages. It is supplied locally by the player and retained by the browser in IndexedDB.
