/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow importing the shared workspace package as source.
  transpilePackages: ["@rankpilot/shared"],
  async rewrites() {
    // Proxy API calls to the FastAPI backend during local dev.
    const apiUrl =
      process.env.API_BASE_URL ?? "https://hamzabhatti-rag-chatbot.hf.space";
    return [
      {
        source: "/api/backend/:path*",
        destination: `${apiUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
