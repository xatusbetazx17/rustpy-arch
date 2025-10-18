# Workflows (Gitflow)

- `main`: production (always deployable)
- `develop`: integration (accumulates features for the next release)
- `feature/*`: new work branched from `develop`
- `release/*`: stabilization branch from `develop` to `main`
- `hotfix/*`: urgent patch from `main` merged back to both `main` and `develop`

See README for command examples.
