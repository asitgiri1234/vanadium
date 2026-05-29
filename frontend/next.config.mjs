/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    // Thumbnails come from arbitrary CDNs (YouTube, Instagram, etc.).
    remotePatterns: [{ protocol: "https", hostname: "**" }],
  },
};

export default nextConfig;
