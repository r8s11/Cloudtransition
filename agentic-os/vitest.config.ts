import { defineConfig } from "vitest/config";

// Force node: builtins (notably node:sqlite) to resolve as external Node modules
// instead of being processed by Vite's transform pipeline. vitest/vite-node
// can otherwise drop the `node:` prefix and try to fetch `sqlite` as a URL.
function externalNodeBuiltins() {
  return {
    name: "external-node-builtins",
    resolveId(id: string) {
      if (id === "node:sqlite" || id === "sqlite") {
        return { id: "node:sqlite", external: true };
      }
      if (id.startsWith("node:")) {
        return { id, external: true };
      }
      return null;
    },
  };
}

export default defineConfig({
  plugins: [externalNodeBuiltins()],
  resolve: {
    conditions: ["node", "import", "default"],
  },
  test: {
    globals: true,
    environment: "node",
    include: [
      "apps/**/*.test.ts",
      "packages/**/*.test.ts",
      "tests/**/*.test.ts",
      "skills/**/*.test.ts",
    ],
    typecheck: true,
    passWithNoTests: true,
    update: false,
  },
});
