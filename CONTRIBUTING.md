# Contributing

Thanks for your interest in NovaOS!

## Development
- Use `feature/*` branches from `develop` for new work.
- Keep PRs small and focused. Include screenshots (or short videos) for UI changes.
- Run HTML through a formatter and keep inline scripts self-contained.

## Commit Messages
Follow Conventional Commits _when possible_:

```
feat(wm): add aero snap overlay
fix(browser): handle iframe error on cross-origin
chore: update Ace editor to 1.36.2
docs(README): add GitHub Pages section
```

## Running Locally
Use any static server, e.g.:

```
python -m http.server -d novaos 8080
```

## Code Style
- Vanilla JS and CSS preferred; keep dependencies light.
- Avoid global variables; use module patterns where feasible.

## Security
Please see SECURITY.md for responsible disclosure.
