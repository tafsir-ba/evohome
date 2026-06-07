import { GANTT_APP_NAME } from './ganttHostUtils';

export const GANTT_LOGO_PATH = '/crc-logo.png';

const SIZE_CLASS = {
  // Crop to CRC + arc so the mark stays legible in the compact toolbar.
  header: 'h-12 sm:h-14 w-36 sm:w-44 object-cover object-[center_38%]',
  auth: 'h-28 sm:h-32 w-auto max-w-[20rem] sm:max-w-[22rem] object-contain',
  landing: 'h-36 sm:h-44 w-auto max-w-[24rem] sm:max-w-[28rem] object-contain',
};

/** CRC brand mark — used on carib-recon.org Gantt surfaces only. */
export const GanttLogo = ({ size = 'header', className = '', alt = GANTT_APP_NAME }) => (
  <img
    src={GANTT_LOGO_PATH}
    alt={alt}
    className={`${SIZE_CLASS[size] || SIZE_CLASS.header} ${className}`.trim()}
    decoding="async"
  />
);
