import express from "express";
import { userRouter } from "./routes";

const app = express();
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

app.use("/api/users", userRouter);

const PORT = process.env.PORT ?? 3001;
app.listen(PORT, () => {
  console.log(`API listening on http://localhost:${PORT}`);
});

export { app };
