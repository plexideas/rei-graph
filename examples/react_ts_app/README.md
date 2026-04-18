# react-ts-app

Demo React/TypeScript application used as a scan target for dev-graph-kit.

## Structure

```
src/
  App.tsx         — root component, imports LoginForm, UserProfile, NavBar
  components.tsx  — NavBar, LoginForm, UserProfile components
  hooks.ts        — useAuth, useForm hooks
  types.ts        — User, AuthStatus, ApiResponse interfaces/types
  utils.ts        — fetchUser, formatUserName, validateEmail utilities
```

## Graph coverage

Running `dgk scan .` from this directory extracts:

- **Module** nodes for each file
- **Component** nodes: `App`, `NavBar`, `LoginForm`, `UserProfile`
- **Hook** nodes: `useAuth`, `useForm`
- **Function** nodes: `fetchUser`, `formatUserName`, `validateEmail`
- **Interface** nodes: `User`, `ApiResponse`
- **Type** nodes: `AuthStatus`
- **Relationships**: `IMPORTS`, `EXPOSES`, `CALLS`, `USES_TYPE`

## Scanning

```bash
# From repo root
dgk scan examples/react_ts_app

# Or from this directory
dgk scan .
```
