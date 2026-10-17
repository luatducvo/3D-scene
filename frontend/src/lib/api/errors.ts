export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
/** The one decoder for API error bodies `{"error": {"code", "message"}}`, whatever the transport. */
export function toApiError(body: unknown, status: number): ApiError {
  const error = (body as { error?: { code?: string; message?: string } } | null)
    ?.error;
  return new ApiError(
    error?.code || "HTTP_ERROR",
    error?.message || `HTTP ${status}`,
  );
}
