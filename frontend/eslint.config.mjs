import { createRequire } from "module";

const require = createRequire(import.meta.url);

// eslint-config-next@16 exports flat config arrays directly
const nextCoreWebVitals = require("eslint-config-next/core-web-vitals");
const nextTypescript = require("eslint-config-next/typescript");

const eslintConfig = [
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    rules: {
      // Allow unused vars prefixed with underscore
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // Allow explicit any during migration - tighten later
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
  {
    ignores: [
      ".next/",
      "node_modules/",
      "playwright-report/",
      "test-results/",
    ],
  },
];

export default eslintConfig;
