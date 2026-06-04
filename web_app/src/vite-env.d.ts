/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_TITLE: string
  readonly VITE_APP_VERSION?: string
  // OpenTelemetry: OTLP/HTTP traces collector endpoint. When unset, the browser
  // tracer registers NO exporter (no network POSTs) — see src/instrumentation.ts.
  readonly VITE_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT?: string
  readonly VITE_OTEL_EXPORTER_OTLP_ENDPOINT?: string
  // more env variables...
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
