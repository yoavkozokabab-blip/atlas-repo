"use client";

import { trackClientEvent } from "../_lib/analytics-client";

export function DownloadButton({
  href,
  className,
  style,
  children,
}: {
  href: string;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}) {
  return (
    <a
      className={className}
      style={style}
      href={href}
      download
      onClick={() => trackClientEvent("download_clicked", { page: "/download" })}
    >
      {children}
    </a>
  );
}
