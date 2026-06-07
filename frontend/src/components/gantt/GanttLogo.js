import { GANTT_APP_NAME } from './ganttHostUtils';

export const GANTT_LOGO_PATH = '/crc-logo.png';

const SIZE_CLASS = {
  header: 'h-8 w-auto max-w-[10rem] sm:max-w-[12rem]',
  auth: 'h-24 w-auto max-w-[16rem] sm:max-w-[18rem]',
};

/** CRC brand mark — used on carib-recon.org Gantt surfaces only. */
export const GanttLogo = ({ size = 'header', className = '', alt = GANTT_APP_NAME }) => (
  <img
    src={GANTT_LOGO_PATH}
    alt={alt}
    className={`object-contain ${SIZE_CLASS[size] || SIZE_CLASS.header} ${className}`.trim()}
    decoding="async"
  />
);
