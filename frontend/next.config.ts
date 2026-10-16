import type { NextConfig } from "next";

// Em dev, o Next repassa /api/v1/* ao backend: navegador e API ficam na mesma
// origem (cookie de refresh SameSite=Lax funciona e não há CORS).
// Em produção quem faz isso é o Caddy, na frente dos dois serviços.
const backendUrl = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone", // imagem de produção enxuta (node server.js)
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backendUrl}/api/v1/:path*` }];
  },
};

export default nextConfig;
