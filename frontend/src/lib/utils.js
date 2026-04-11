import { clsx } from "clsx";
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/**
 * Canonical client context formatters.
 * Never returns N/A. Omits missing parts.
 * Used everywhere client/project/unit context is displayed.
 */

/** Full label: "Name — Project — Unit". For cards, detail displays. */
export const formatClientContext = ({ name, project_name, unit_reference }) => {
  return [name, project_name, unit_reference].filter(Boolean).join(' — ');
};

/** Compact label: "Name (Project / Unit)". For selectors, inline references. */
export const formatClientContextCompact = ({ name, project_name, unit_reference }) => {
  const context = [project_name, unit_reference].filter(Boolean).join(' / ');
  return context ? `${name} (${context})` : name;
};

/** Inline doc reference: "Client · Project · Unit". For list rows. */
export const formatDocContext = ({ client_name, project_name, unit_reference }) => {
  return [client_name, project_name, unit_reference].filter(Boolean).join(' · ');
};
