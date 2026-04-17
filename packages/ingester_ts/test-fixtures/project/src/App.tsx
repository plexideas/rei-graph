import { validateEmail } from "./utils";
import React from "react";

export function App() {
  const valid = validateEmail("test@example.com");
  return React.createElement("div", null, String(valid));
}
