export const INSTALLER_WAIT_LABEL = "Windows build verification in progress";

export const INSTALLER_WAIT_MESSAGE =
  "The latest Atlas desktop build is undergoing final installed-app verification. Downloads will reopen when the verified installer is ready.";

export default function InstallerWaitState({
  compact = false,
}: {
  compact?: boolean;
}) {
  return (
    <div
      className={`installer-wait${compact ? " installer-wait--compact" : ""}`}
      role="status"
      data-analytics-state="download-unavailable"
    >
      <span className="btn-mag installer-wait-action" aria-disabled="true">
        {INSTALLER_WAIT_LABEL}
      </span>
      <p className="installer-wait-copy">{INSTALLER_WAIT_MESSAGE}</p>
    </div>
  );
}
