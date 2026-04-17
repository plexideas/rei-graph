import React from "react";
import { useAuth } from "./hooks";
import { validateEmail } from "./utils";

export function LoginForm() {
  const { status, login } = useAuth();
  const [email, setEmail] = React.useState("");

  const handleSubmit = () => {
    if (validateEmail(email)) {
      login(email);
    }
  };

  return React.createElement(
    "form",
    { onSubmit: handleSubmit },
    React.createElement("input", { value: email, onChange: (e: any) => setEmail(e.target.value) }),
    React.createElement("button", { type: "submit" }, status === "loading" ? "..." : "Login")
  );
}

export function UserProfile({ userId }: { userId: string }) {
  const { user, status } = useAuth();

  if (status === "loading") return React.createElement("div", null, "Loading...");
  if (!user) return React.createElement("div", null, "No user");

  return React.createElement(
    "div",
    null,
    React.createElement("h1", null, user.name),
    React.createElement("p", null, user.email)
  );
}
