export { default } from "next-auth/middleware";

/**
 * Protect the dashboard. Unauthenticated requests are redirected to the
 * sign-in page configured in `authOptions.pages.signIn` (/login).
 */
export const config = {
  matcher: ["/dashboard/:path*"],
};
