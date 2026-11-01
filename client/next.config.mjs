/** Proxies /api to the FastAPI server so the app works from a phone on the same Wi-Fi. */
const configuredServer = process.env.SERVER_URL || "http://localhost:8000";
const server = /^https?:\/\//i.test(configuredServer) ? configuredServer : `https://${configuredServer}`;
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${server}/api/:path*` }];
  },
};
export default nextConfig;
