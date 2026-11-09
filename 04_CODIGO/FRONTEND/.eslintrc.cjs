// Configuración mínima de ESLint 8 para el script "lint" (eslint . --ext js,jsx).
// Reglas recomendadas de JavaScript, uso de variables en JSX y reglas de hooks de React.
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  settings: { react: { version: '18.3' } },
  plugins: ['react', 'react-hooks'],
  extends: ['eslint:recommended', 'plugin:react-hooks/recommended'],
  rules: {
    'react/jsx-uses-vars': 'error',
    'react/jsx-uses-react': 'error',
  },
  ignorePatterns: ['dist', 'node_modules'],
  overrides: [
    {
      // Archivos de configuración que se ejecutan en Node
      files: ['*.config.js', '.eslintrc.cjs'],
      env: { node: true },
    },
  ],
};
