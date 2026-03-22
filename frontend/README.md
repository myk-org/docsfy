# docsfy Frontend

React + TypeScript SPA for the docsfy documentation generator.

## Stack

- **React 19** with React Router for SPA navigation
- **Vite** for dev server and production builds
- **Tailwind CSS v4** for styling
- **shadcn/ui** component library
- **sonner** for toast notifications
- **@tanstack/react-virtual** for virtualized project tree

## Development

```bash
# Install dependencies
npm install

# Start dev server (port 5173, proxies API to :8000)
npm run dev

# Production build
npm run build

# Lint
npm run lint
```

## Project Structure

```text
src/
  components/
    admin/          # Admin-only panels (UsersPanel, AccessPanel)
    layout/         # Layout shell (header, sidebar, footer)
    shared/         # Reusable components (Combobox, ProjectTree, etc.)
    ui/             # shadcn/ui primitives (Button, Input, etc.)
  lib/              # Utilities (api client, websocket, constants, theme)
  pages/            # Route-level pages (LoginPage, DashboardPage)
  types/            # TypeScript type definitions
```

## Environment

The frontend communicates with the FastAPI backend at the same origin.
In development, Vite proxies `/api`, `/docs`, and `/health` requests to `localhost:8000`.
