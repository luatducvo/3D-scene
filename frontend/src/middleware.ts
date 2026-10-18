import { NextResponse, type NextRequest } from "next/server";

/** Preserve old deep links while rendering only the English experience. */
export function middleware(request: NextRequest) {
  const url = request.nextUrl.clone();
  url.pathname = url.pathname.replace(/^\/vi(?=\/|$)/, "/en");
  return NextResponse.redirect(url);
}
export const config = { matcher: ["/vi/:path*"] };
