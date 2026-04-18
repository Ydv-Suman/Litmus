import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8000",
  timeout: 10000,
});

export function authHeaders(token: string) {
  return {
    Authorization: `Bearer ${token}`,
  };
}

