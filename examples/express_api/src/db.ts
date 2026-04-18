import { User, Post, ApiError } from "./types";

const users: Map<string, User> = new Map();
const posts: Map<string, Post> = new Map();

export function findUserById(id: string): User | undefined {
  return users.get(id);
}

export function findUserByEmail(email: string): User | undefined {
  for (const user of users.values()) {
    if (user.email === email) return user;
  }
  return undefined;
}

export function createUser(data: Omit<User, "id" | "createdAt">): User {
  const user: User = {
    ...data,
    id: crypto.randomUUID(),
    createdAt: new Date(),
  };
  users.set(user.id, user);
  return user;
}

export function findPostsByAuthor(authorId: string): Post[] {
  return Array.from(posts.values()).filter((p) => p.authorId === authorId);
}

export function createPost(data: Omit<Post, "id">): Post {
  const post: Post = { ...data, id: crypto.randomUUID() };
  posts.set(post.id, post);
  return post;
}

export function makeError(
  code: string,
  message: string,
  status: number,
): ApiError {
  return { code, message, status };
}
