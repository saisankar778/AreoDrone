/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_VARIANT?: 'user' | 'vendor' | 'admin';
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
