import React from "react";
import { ExternalLink, Radio } from "lucide-react";

const CARIBBEAN_CENTER = { lat: 17.5, lon: -72.0, zoom: 5 };

const buildMarineTrafficEmbedUrl = ({ lat, lon, zoom }) =>
    [
        "https://www.marinetraffic.com/en/ais/embed",
        `zoom:${zoom}`,
        `centery:${lat}`,
        `centerx:${lon}`,
        "maptype:0",
        "shownames:false",
        "mmsi:0",
        "shipid:0",
        "fleet:",
        "fleet_id:",
        "vtypes:",
        "showmenu:false",
        "remember:false",
    ].join("/");

const FULL_MAP_URL =
    "https://www.marinetraffic.com/en/ais/home/centerx:-72/centery:17.5/zoom:5";

export default function RegionalPerspective() {
    const embedUrl = buildMarineTrafficEmbedUrl(CARIBBEAN_CENTER);

    return (
        <section
            id="regional-perspective"
            data-testid="regional-perspective-section"
            className="relative isolate overflow-hidden py-24 sm:py-32"
        >
            {/* Layered background: soft blue gradient + subtle texture */}
            <div
                aria-hidden
                className="absolute inset-0 -z-20 bg-gradient-to-b from-[#EAF3FB] via-[#F4F9FD] to-[#EAF3FB]"
            />
            <div
                aria-hidden
                className="absolute inset-0 -z-10"
                style={{
                    backgroundImage:
                        "radial-gradient(ellipse 80% 60% at 50% 35%, rgba(0,71,143,0.10) 0%, transparent 60%)",
                }}
            />
            <div
                aria-hidden
                className="absolute inset-0 -z-10 bg-dot-grid opacity-50"
            />

            {/* Very slow drifting ambient gradient */}
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 -z-10 crc-drift opacity-70"
                style={{
                    background:
                        "radial-gradient(40% 35% at 30% 40%, rgba(0,71,143,0.10) 0%, transparent 70%), radial-gradient(35% 30% at 70% 60%, rgba(10,108,184,0.10) 0%, transparent 70%)",
                }}
            />

            {/* Decorative ambient blobs — very subtle */}
            <div
                aria-hidden
                className="pointer-events-none absolute -top-32 -left-32 h-96 w-96 rounded-full bg-[#00478F]/10 blur-3xl"
            />
            <div
                aria-hidden
                className="pointer-events-none absolute -bottom-40 -right-24 h-[28rem] w-[28rem] rounded-full bg-[#0a6cb8]/10 blur-3xl"
            />

            <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="max-w-3xl mx-auto text-center">
                    <span className="eyebrow">Regional Perspective</span>
                    <h2
                        data-testid="regional-title"
                        className="mt-5 font-display font-semibold text-3xl sm:text-4xl lg:text-[44px] leading-[1.1] tracking-tight text-[#00478F] text-balance"
                    >
                        One Region. Many Gateways.
                    </h2>
                    <p
                        data-testid="regional-subtitle"
                        className="mt-6 text-base sm:text-lg text-foreground/75 leading-relaxed max-w-2xl mx-auto"
                    >
                        Connecting major ports, logistics hubs, and trade
                        corridors across the Caribbean and the Americas.
                    </p>
                </div>

                {/* Floating glass-card live-map panel */}
                <div
                    data-testid="regional-map-frame"
                    className="relative mt-14 sm:mt-16"
                >
                    {/* Soft outer glow */}
                    <div
                        aria-hidden
                        className="absolute -inset-3 sm:-inset-5 rounded-[28px] bg-gradient-to-br from-white/70 via-[#E6F0FA]/60 to-white/40 blur-2xl opacity-80"
                    />
                    {/* Inner gradient ring */}
                    <div
                        aria-hidden
                        className="absolute -inset-px rounded-[20px] bg-gradient-to-br from-[#00478F]/25 via-white/60 to-[#7AB2DD]/30"
                    />

                    {/* Map panel */}
                    <div className="relative rounded-[20px] overflow-hidden bg-white/85 backdrop-blur-md shadow-[0_40px_80px_-30px_rgba(0,71,143,0.35),0_10px_30px_-15px_rgba(0,71,143,0.2)]">
                        {/* Card header strip */}
                        <div className="px-5 sm:px-6 py-3 sm:py-3.5 border-b border-[#00478F]/10 bg-white/70 backdrop-blur flex flex-wrap items-center justify-between gap-3">
                            <div className="flex items-center gap-2.5">
                                <span className="relative inline-flex h-2 w-2">
                                    <span className="absolute inline-flex h-full w-full rounded-full bg-[#16a34a] opacity-75 crc-pulse" />
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-[#16a34a]" />
                                </span>
                                <span className="text-[10px] sm:text-[11px] font-semibold tracking-[0.18em] uppercase text-[#00478F]/80 inline-flex items-center gap-2">
                                    <Radio size={12} strokeWidth={2.3} />
                                    Live Vessel Tracking
                                </span>
                            </div>
                            <a
                                href={FULL_MAP_URL}
                                target="_blank"
                                rel="noopener noreferrer"
                                data-testid="open-full-marinetraffic"
                                className="inline-flex items-center gap-1.5 text-[11px] sm:text-xs font-semibold text-[#00478F] hover:text-[#003366] transition-colors"
                            >
                                Open full MarineTraffic
                                <ExternalLink size={12} strokeWidth={2.3} />
                            </a>
                        </div>

                        {/* Map canvas */}
                        <div className="relative p-2 sm:p-3 lg:p-4">
                            <div className="relative rounded-[14px] overflow-hidden bg-[#dfeaf3]">
                                <div className="relative w-full aspect-[4/3] sm:aspect-[16/10] lg:aspect-[16/9]">
                                    <iframe
                                        title="MarineTraffic live AIS map — Caribbean"
                                        src={embedUrl}
                                        data-testid="marinetraffic-iframe"
                                        className="absolute inset-0 h-full w-full border-0"
                                        loading="lazy"
                                        referrerPolicy="no-referrer-when-downgrade"
                                        allowFullScreen
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Card footer with attribution */}
                        <div className="px-5 sm:px-6 py-3 sm:py-3.5 border-t border-[#00478F]/10 bg-white/60 backdrop-blur flex flex-wrap items-center justify-between gap-2">
                            <span className="text-[10px] sm:text-[11px] font-semibold tracking-[0.18em] uppercase text-[#00478F]/75">
                                Caribbean Maritime Network
                            </span>
                            <span className="text-[10px] sm:text-[11px] text-[#00478F]/65 tracking-wide">
                                Vessel data ©{" "}
                                <a
                                    href="https://www.marinetraffic.com"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="underline-offset-2 hover:underline"
                                >
                                    MarineTraffic
                                </a>
                                {" · Embedded via the "}
                                <a
                                    href="https://www.marinetraffic.com/en/p/embed-map"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="underline-offset-2 hover:underline"
                                >
                                    official embed
                                </a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
