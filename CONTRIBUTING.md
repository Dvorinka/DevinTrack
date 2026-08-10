# Contributing to DevinTrack

## Development setup

```bash
# Clone
git clone https://github.com/Dvorinka/DevinTrack.git
cd DevinTrack

# Build frontend
cd dashboard/web
npm install
npm run build

# Start dashboard
cd ../..
python3 dashboard/server.py
```

For frontend development with hot reload:

```bash
cd dashboard/web
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:7841` (see `vite.config.ts`).

## Before submitting a PR

1. **Typecheck**: `cd dashboard/web && npx tsc --noEmit`
2. **Build**: `cd dashboard/web && npm run build`
3. **Python syntax**: `python3 -m py_compile dashboard/server.py dashboard/sync_remote.py deploy.py devin`
4. **Smoke test**: Start the server and verify `http://127.0.0.1:7841` loads

## Code style

- **Python**: stdlib only, no external dependencies. Follow existing style.
- **TypeScript/React**: functional components, hooks, no class components.
- **CSS**: Tailwind utility classes. No custom CSS unless necessary.
- **Comments**: use `jarvis: ceiling X, upgrade if Y` for deliberate shortcuts.

## Project structure

See [README.md](README.md) for the full project structure and architecture.

## License

By contributing, you agree that your contributions are licensed under the MIT License.
