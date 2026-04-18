import React from "react";
import { LoginForm, UserProfile, NavBar } from "./components";

export function App() {
  return React.createElement(
    "div",
    null,
    React.createElement(NavBar, { title: "My App" }),
    React.createElement("h1", null, "My App"),
    React.createElement(LoginForm, null),
    React.createElement(UserProfile, { userId: "1" }),
  );
}
