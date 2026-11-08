/**
 * Data mode is selected explicitly — never as a silent fallback after a live API error.
 * Stage 1 ships only "synthetic_demo". Switch to "remote" once the backend exists.
 */
export type DataMode = "synthetic_demo" | "remote";
export const DATA_MODE: DataMode = "synthetic_demo";
export const API_BASE_URL = ""; // same-origin, e.g. /api/v1/...
