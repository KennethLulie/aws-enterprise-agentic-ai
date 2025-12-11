import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Generate a static export for deployment to static hosting / CloudFront.
  output: "export",
  // Disable Next.js image optimization because static export cannot use the image pipeline.
  images: { unoptimized: true },
  // Append trailing slashes to routes to match static hosting expectations.
  trailingSlash: true,
};

export default nextConfig;
