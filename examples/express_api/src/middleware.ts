import { Request, Response, NextFunction } from "express";
import { User } from "./types";
import { findUserById, makeError } from "./db";

export function requireAuth(req: Request, res: Response, next: NextFunction): void {
  const token = req.headers.authorization?.split(" ")[1];
  if (!token) {
    res.status(401).json(makeError("UNAUTHORIZED", "Missing token", 401));
    return;
  }
  // In production: verify JWT — here we treat the token as a user id
  const user = findUserById(token);
  if (!user) {
    res.status(401).json(makeError("INVALID_TOKEN", "Token invalid or expired", 401));
    return;
  }
  (req as any).user = user;
  next();
}

export function requireRole(role: User["role"]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const user: User = (req as any).user;
    if (user.role !== role && user.role !== "admin") {
      res.status(403).json(makeError("FORBIDDEN", "Insufficient permissions", 403));
      return;
    }
    next();
  };
}
