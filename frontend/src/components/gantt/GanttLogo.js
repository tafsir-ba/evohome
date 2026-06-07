import { GANTT_APP_NAME } from './ganttHostUtils';

export const GANTT_LOGO_PATH = '/crc-logo.png';
export const GANTT_LOGO_MARK_PATH = '/crc-logo-mark.png';

const LOGO_CONFIG = {
  header: {
    src: GANTT_LOGO_MARK_PATH,
    className: 'h-12 sm:h-14 w-auto object-contain',
  },
  auth: {
    src: GANTT_LOGO_PATH,
    className: 'h-32 sm:h-36 w-auto max-w-[22rem] sm:max-w-[26rem] object-contain',
  },
  landing: {
    src: GANTT_LOGO_PATH,
    className: 'h-40 sm:h-48 w-auto max-w-[26rem] sm:max-w-[30rem] object-contain',
  },
};

/** CRC brand mark — used on carib-recon.org Gantt surfaces only. */
export const GanttLogo = ({ size = 'header', className = '', alt = GANTT_APP_NAME }) => {
  const config = LOGO_CONFIG[size] || LOGO_CONFIG.header;
  return (
    <img
      src={config.src}
      alt={alt}
      className={`${config.className} ${className}`.trim()}
      decoding="async"
    />
  );
};
