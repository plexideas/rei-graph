import React from "react";
import { useState } from "react";
import { validateEmail } from "./utils";

export interface LoginPayload {
  email: string;
  password: string;
}

export type AuthStatus = "idle" | "loading" | "success" | "error";

export function useAuth() {
  const [status, setStatus] = useState<AuthStatus>("idle");
  return { status, setStatus };
}

export function LoginForm() {
  const { status } = useAuth();
  return React.createElement("form", null, status);
}

export class AuthService {
  async login(payload: LoginPayload): Promise<boolean> {
    return true;
  }
}

const helper = (x: number) => x + 1;

export const formatEmail = (email: string): string => {
  return email.trim().toLowerCase();
};
