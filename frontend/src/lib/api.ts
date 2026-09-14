export class ApiError extends Error {
  status: number
  code: string | null
  constructor(status: number, message: string, code: string | null = null) {
    super(message)
    this.status = status
    this.code = code
  }
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { signal })
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return apiRequest<T>(path, { method: "POST", body: JSON.stringify(body) })
}

export function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return apiRequest<T>(path, { method: "PATCH", body: JSON.stringify(body) })
}

export function apiDelete<T>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "DELETE" })
}

async function apiRequest<T>(path: string, options: RequestInit): Promise<T> {
  const token = localStorage.getItem("sharehub_token")
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", Accept: "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    cache: "no-store",
  })
  if (response.status === 401) {
    for (const key of ["sharehub_token", "sharehub_user", "sharehub_expires_at"]) localStorage.removeItem(key)
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const code = typeof data?.error?.code === "string" ? data.error.code : null
    const message = typeof data?.error?.message === "string"
      ? data.error.message
      : typeof data?.message === "string"
        ? data.message
        : response.status === 401 ? "로그인이 필요합니다." : "요청을 처리하지 못했습니다."
    throw new ApiError(response.status, message, code)
  }
  if (data === null) throw new ApiError(502, "서버 응답을 읽을 수 없습니다.")
  return data as T
}
