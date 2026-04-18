export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  createdAt: Date;
}

export type UserRole = "admin" | "editor" | "viewer";

export interface Post {
  id: string;
  title: string;
  body: string;
  authorId: string;
  tags: string[];
  publishedAt?: Date;
}

export interface ApiError {
  code: string;
  message: string;
  status: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
}
