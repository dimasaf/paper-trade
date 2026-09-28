export const healthComponentNames = [
  "application",
  "database",
  "redis",
  "worker",
] as const;

export const readyHealth = {
  status: "ready",
  checked_at: "2026-09-28T08:00:00Z",
  correlation_id: "browser-test",
  components: {
    application: { status: "ready", message: "API is serving requests" },
    database: { status: "ready", message: "PostgreSQL accepted a query" },
    redis: { status: "ready", message: "Redis responded to ping" },
    worker: { status: "ready", message: "ARQ heartbeat is current" },
  },
};
