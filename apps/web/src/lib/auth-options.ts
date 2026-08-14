import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

/**
 * NextAuth configuration.
 *
 * Auth is delegated to FastAPI: the Credentials provider posts to
 * `/api/v1/auth/login`, and the FastAPI-issued JWT (`access_token`) is
 * carried in the NextAuth session so the browser can send it as a
 * Bearer token to the API. FastAPI validates that token with SECRET_KEY.
 */

// Server-side calls talk to the backend directly (not the browser proxy).
const API_URL =
  process.env.API_BASE_URL ?? "https://hamzabhatti-rag-chatbot.hf.space";

export const authOptions: NextAuthOptions = {
  session: {
    strategy: "jwt",
    // Keep in step with the FastAPI token lifetime (see ACCESS_TOKEN_EXPIRE_MINUTES).
    maxAge: 7 * 24 * 60 * 60,
  },
  secret: process.env.NEXTAUTH_SECRET,
  pages: {
    signIn: "/login",
  },
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;

        // FastAPI /auth/login uses the OAuth2 password form (username=email).
        const body = new URLSearchParams({
          username: credentials.email,
          password: credentials.password,
        });

        const res = await fetch(`${API_URL}/api/v1/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body,
        });

        if (!res.ok) return null;
        const data = await res.json();

        return {
          id: data.user.id,
          email: data.user.email,
          name: data.user.full_name ?? data.user.email,
          tier: data.user.plan,
          accessToken: data.access_token,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // On sign-in, persist the FastAPI token and tier onto the NextAuth JWT.
      if (user) {
        token.id = user.id;
        token.accessToken = (user as { accessToken?: string }).accessToken;
        token.tier = (user as { tier?: string }).tier;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      if (session.user) {
        session.user.id = token.id as string;
        session.user.tier = token.tier as string | undefined;
      }
      return session;
    },
  },
};
