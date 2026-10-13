export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
export function toApiError(body: unknown, fallback: string): ApiError {
  const error = (body as { error?: { code?: string; message?: string } })
    ?.error;
  return new ApiError(error?.code || "HTTP_ERROR", error?.message || fallback);
}
