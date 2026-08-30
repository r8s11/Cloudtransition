import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["apps/**/*.test.ts", "packages/**/*.test.ts", "tests/**/*.test.ts", "skills/**/*.test.ts"],
    typecheck: true,
    passWithNoTests: true,
    update: false,
  },
});
