export interface User {
  id: string;
  name: string;
  email: string;
}

export type AuthStatus = "idle" | "loading" | "success" | "error";

export interface ApiResponse<T> {
  data: T;
  error?: string;
}
