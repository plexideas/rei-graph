import { Router, Request, Response } from "express";
import { findUserById, createUser, findPostsByAuthor } from "./db";
import { requireAuth, requireRole } from "./middleware";
import { PaginatedResponse, User } from "./types";

export const userRouter = Router();

userRouter.get("/:id", requireAuth, (req: Request, res: Response) => {
  const user = findUserById(req.params.id);
  if (!user) {
    res.status(404).json({ code: "NOT_FOUND", message: "User not found", status: 404 });
    return;
  }
  res.json(user);
});

userRouter.post("/", requireAuth, requireRole("admin"), (req: Request, res: Response) => {
  const { name, email, role } = req.body;
  const user = createUser({ name, email, role });
  res.status(201).json(user);
});

userRouter.get("/:id/posts", requireAuth, (req: Request, res: Response) => {
  const posts = findPostsByAuthor(req.params.id);
  const response: PaginatedResponse<(typeof posts)[0]> = {
    data: posts,
    total: posts.length,
    page: 1,
    pageSize: 20,
  };
  res.json(response);
});
