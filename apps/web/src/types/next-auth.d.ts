import type { DefaultSession } from "next-auth";

/**
 * Extend NextAuth's types so the FastAPI access token and the user's
 * subscription tier are available on the session and JWT.
 */
declare module "next-auth" {
  interface Session {
    accessToken?: string;
    user: {
      id: string;
      tier?: string;
      mustChangePassword?: boolean;
    } & DefaultSession["user"];
  }

  interface User {
    tier?: string;
    accessToken?: string;
    mustChangePassword?: boolean;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id?: string;
    tier?: string;
    accessToken?: string;
    mustChangePassword?: boolean;
  }
}
