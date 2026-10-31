/** Proxies /api to the FastAPI server so the app works from a phone on the same Wi-Fi. */
const server = process.env.SERVER_URL || "http://localhost:8000";
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${server}/api/:path*` }];
  },
};
export default nextConfig;
