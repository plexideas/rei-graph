export function validateEmail(email: string): boolean {
  return email.includes("@");
}

export function formatName(name: string): string {
  return name.trim();
}
