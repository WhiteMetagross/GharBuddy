/**
 * computeBackoffDelay — pure helper for exponential-backoff reconnection delays.
 *
 * @param {number} retryCount - Number of consecutive failed reconnection attempts (1-based).
 * @returns {number|"exhausted"} Delay in milliseconds, or "exhausted" when retryCount > 5.
 */
export function computeBackoffDelay(retryCount) {
  if (retryCount > 5) return "exhausted";
  return 1000 * Math.pow(2, retryCount - 1);
}
