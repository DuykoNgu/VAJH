// Gọi backend LUSIA. Kiểu dữ liệu sinh từ OpenAPI: `npm run gen:api` (cần backend đang chạy).
import type { components } from "./api-types";

export type Me = components["schemas"]["Me"];

// NEXT_PUBLIC_* được gắn cứng lúc build (next build) - phải viết đúng tên, không tra động
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Danh tính dev (tới giai đoạn 12): người dùng được chọn lưu ở localStorage, gửi qua header.
// Giai đoạn 12 (authentication): bỏ header này, chuyển sang cookie (credentials: "include").
const DEV_USER_KEY = "lusia.devUser";

export function getDevUser(): string | null {
  try {
    return localStorage.getItem(DEV_USER_KEY);
  } catch {
    return null; // SSR, chế độ riêng tư hoặc bị chặn storage
  }
}

export function setDevUser(username: string | null): void {
  try {
    if (username) localStorage.setItem(DEV_USER_KEY, username);
    else localStorage.removeItem(DEV_USER_KEY);
  } catch {
    // không lưu được thì dùng người dùng mặc định của backend
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(`API ${status}`);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const devUser = getDevUser();
  if (devUser) headers.set("X-Dev-User", devUser);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  const body = res.headers.get("content-type")?.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

export const getMe = () => api<Me>("/me");
