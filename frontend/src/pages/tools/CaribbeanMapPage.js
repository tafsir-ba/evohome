import { useGanttBranding } from '../../components/gantt/ganttBrandingUtils';
import { useGanttPublicConfig } from '../../components/gantt/ganttAuthUtils';
import { GANTT_APP_NAME } from '../../components/gantt/ganttHostUtils';

/** Caribbean Sea — similar framing to MarineTraffic live map at regional zoom. */
const CARIBBEAN_CENTER = { lat: 17.5, lon: -72.0, zoom: 5 };

const buildMarineTrafficEmbedUrl = ({ lat, lon, zoom }) =>
  [
    'https://www.marinetraffic.com/en/ais/embed',
    `zoom:${zoom}`,
    `centery:${lat}`,
    `centerx:${lon}`,
    'maptype:0',
    'shownames:false',
    'mmsi:0',
    'shipid:0',
    'fleet:',
    'fleet_id:',
    'vtypes:',
    'showmenu:false',
    'remember:false',
  ].join('/');

export const CaribbeanMapPage = () => {
  const { app_name: appName } = useGanttPublicConfig();
  useGanttBranding(appName || GANTT_APP_NAME);

  const embedUrl = buildMarineTrafficEmbedUrl(CARIBBEAN_CENTER);

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b px-4 py-3">
        <div>
          <h1 className="text-sm font-semibold sm:text-base">Live vessel map — Caribbean</h1>
          <p className="text-xs text-muted-foreground">
            MarineTraffic embed test · zoom {CARIBBEAN_CENTER.zoom}
          </p>
        </div>
        <a
          href="https://www.marinetraffic.com/en/ais/home/centerx:-72/centery:17.5/zoom:5"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-primary underline-offset-4 hover:underline sm:text-sm"
        >
          Open full MarineTraffic
        </a>
      </header>

      <div className="relative min-h-0 flex-1">
        <iframe
          title="MarineTraffic live AIS map — Caribbean"
          src={embedUrl}
          className="absolute inset-0 h-full w-full border-0"
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
          allowFullScreen
        />
      </div>

      <footer className="shrink-0 border-t px-4 py-2 text-center text-[11px] text-muted-foreground">
        Vessel data ©{' '}
        <a
          href="https://www.marinetraffic.com"
          target="_blank"
          rel="noopener noreferrer"
          className="underline-offset-4 hover:underline"
        >
          MarineTraffic
        </a>
        . Embedded via the{' '}
        <a
          href="https://www.marinetraffic.com/en/p/embed-map"
          target="_blank"
          rel="noopener noreferrer"
          className="underline-offset-4 hover:underline"
        >
          official embed
        </a>
        .
      </footer>
    </div>
  );
};
