/**
 * Server-side redaction for beta feedback.
 *
 * The desktop already runs `install_support._redact_support_text` before
 * sending. This is the independent second pass, because the endpoint is
 * unauthenticated and must stay safe against a modified or third-party client.
 *
 * It redacts rather than rejects: the message is user-authored prose written
 * to get help, so scrubbing it is strictly better than silently dropping a
 * report the user believes they filed.
 */
const REDACTIONS: [RegExp, string][] = [
  // Windows and POSIX absolute paths.
  [/[A-Za-z]:\\[^\s"'<>|]+/g, "[path-redacted]"],
  [/\\\\[^\s"'<>|]+/g, "[path-redacted]"],
  [/\/(?:home|Users|var|etc|private|tmp)\/[^\s"'<>|]+/g, "[path-redacted]"],
  // Credentials and tokens.
  [/\b(?:bearer\s+)[A-Za-z0-9._~+/=-]{8,}/gi, "[credential-redacted]"],
  [/\bey[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}/g, "[credential-redacted]"],
  [/\bsb_secret_[A-Za-z0-9_-]+/gi, "[credential-redacted]"],
  [/\bgh[pousr]_[A-Za-z0-9]{16,}/g, "[credential-redacted]"],
  [/\b(?:sk|pk)-[A-Za-z0-9]{16,}/g, "[credential-redacted]"],
  [/\bAKIA[0-9A-Z]{16}\b/g, "[credential-redacted]"],
  [/\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*\S+/gi, "[credential-redacted]"],
];

export function redactFeedbackText(value: string): string {
  return REDACTIONS.reduce((text, [pattern, replacement]) => text.replace(pattern, replacement), value);
}
