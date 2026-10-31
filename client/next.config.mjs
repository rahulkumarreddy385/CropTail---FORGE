/** Proxies /api to the FastAPI backend so the app works from a phone on the same Wi-Fi. */
const backend = process.env.BACKEND_URL || "http://localhost:8000";
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
export default nextConfig;
