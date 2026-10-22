# Capitan Artiglio Web

Web launcher self-hosted for **Captain Claw / Capitan Artiglio** using the open-source Claw Web/OpenClaw WebAssembly engine.

## What this repository contains

- deployment automation for a self-hosted browser build;
- branding/configuration for this deployment;
- **no original Captain Claw game assets**.

On first launch the web app asks the player to provide `CLAW.REZ`. The file is stored locally in the browser via IndexedDB and is not committed to this repository.

## Runtime source and attribution

The browser engine is based on **arthurboss/claw-web**, itself based on **pjasicek/OpenClaw**. The deployment workflow vendors a pinned public build of that GPL-licensed engine onto this project's GitHub Pages hosting so gameplay does not redirect through a third-party site.

Captain Claw and its original game assets are property of their respective rights holders. This is an unofficial fan project and is not affiliated with or endorsed by the rights holders.

## Deployment

Pushes to `main` trigger `.github/workflows/deploy-pages.yml`. The workflow fetches the pinned upstream WebAssembly runtime, applies this project's branding, and deploys the resulting static site to GitHub Pages.

The game data (`CLAW.REZ`) is intentionally excluded from deployment.
