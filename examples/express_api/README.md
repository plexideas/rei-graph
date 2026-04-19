# express-api

Demo Express/TypeScript API used as a scan target for rei-graph.

## Structure

```
src/
  app.ts          — Express app entry, mounts /api/users router
  routes.ts       — userRouter: GET /:id, POST /, GET /:id/posts
  middleware.ts   — requireAuth, requireRole middleware
  db.ts           — in-memory store: findUserById, createUser, findPostsByAuthor
  types.ts        — User, Post, UserRole, ApiError, PaginatedResponse
```

## Graph coverage

Running `rei scan .` from this directory extracts:

- **Module** nodes for each file
- **Function** nodes: `requireAuth`, `requireRole`, `findUserById`, `findUserByEmail`, `createUser`, `findPostsByAuthor`, `createPost`, `makeError`
- **Interface** nodes: `User`, `Post`, `ApiError`, `PaginatedResponse`
- **Type** nodes: `UserRole`
- **Relationships**: `IMPORTS`, `EXPOSES`, `CALLS`, `USES_TYPE`

## Scanning

```bash
# From repo root
rei scan examples/express_api

# Or from this directory
rei scan .
```
