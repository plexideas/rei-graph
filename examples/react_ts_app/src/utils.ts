import { User, ApiResponse } from "./types";

export async function fetchUser(id: string): Promise<ApiResponse<User>> {
  const res = await fetch(`/api/users/${id}`);
  const data = await res.json();
  return { data };
}

export function formatUserName(user: User): string {
  return user.name.trim();
}

export function validateEmail(email: string): boolean {
  return /^[^@]+@[^@]+\.[^@]+$/.test(email);
}
