// Docker is the production target; local development can override with NEXT_PUBLIC_API_URL.
const backend=process.env.NEXT_PUBLIC_API_URL || "http://backend:8000";
const nextConfig = { output: "standalone" as const, async rewrites(){return [{source:"/backend/:path*",destination:`${backend}/:path*`}]}};
export default nextConfig;
