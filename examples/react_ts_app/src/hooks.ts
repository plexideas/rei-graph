import React, { useState, useEffect } from "react";
import { User, AuthStatus } from "./types";
import { fetchUser } from "./utils";

export function useAuth() {
  const [status, setStatus] = useState<AuthStatus>("idle");
  const [user, setUser] = useState<User | null>(null);

  const login = async (userId: string) => {
    setStatus("loading");
    try {
      const res = await fetchUser(userId);
      setUser(res.data);
      setStatus("success");
    } catch {
      setStatus("error");
    }
  };

  return { status, user, login };
}

export function useForm(initialValues: Record<string, string>) {
  const [values, setValues] = useState(initialValues);

  const handleChange = (field: string, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
  };

  return { values, handleChange };
}
