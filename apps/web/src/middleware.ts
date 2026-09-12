import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";

/**
 * Protect the dashboard and gate the forced first-login password change.
 *
 * - Unauthenticated requests to matched routes are redirected to /login
 *   (via `authOptions.pages.signIn`).
 * - Admin-created accounts carry `mustChangePassword` until they set their
 *   own password: they are pinned to /set-password until they do, and users
 *   who don't need to change are bounced off /set-password.
 */
export default withAuth(
  function middleware(req) {
    const { token } = req.nextauth;
    const { pathname } = req.nextUrl;
    const mustChange = Boolean(token?.mustChangePassword);

    if (mustChange && pathname !== "/set-password") {
      return NextResponse.redirect(new URL("/set-password", req.url));
    }
    if (!mustChange && pathname === "/set-password") {
      return NextResponse.redirect(new URL("/dashboard", req.url));
    }
    return NextResponse.next();
  },
  {
    callbacks: {
      // Require a valid session on all matched routes.
      authorized: ({ token }) => !!token,
    },
  }
);

export const config = {
  matcher: ["/dashboard/:path*", "/set-password"],
};
