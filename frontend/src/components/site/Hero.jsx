import React from "react";
import { Anchor } from "lucide-react";

// Caribbean container port — institutional hero image
const HERO_BG =
    "https://images.unsplash.com/photo-1606185540834-d6e7483ee1a4?q=85&w=2400&auto=format&fit=crop";

// Soft, professional text shadow — no glow
const TITLE_SHADOW = { textShadow: "0 2px 14px rgba(0, 18, 42, 0.6)" };
const SUBTITLE_SHADOW = { textShadow: "0 1px 8px rgba(0, 18, 42, 0.55)" };

export default function Hero() {
    return (
        <section
            id="home"
            data-testid="hero-section"
            className="relative isolate overflow-hidden min-h-[86vh] sm:min-h-[90vh] flex items-center pt-28 sm:pt-32"
        >
            {/* Port photo */}
            <div
                aria-hidden
                className="absolute inset-0 -z-20 bg-cover bg-center bg-no-repeat"
                style={{ backgroundImage: `url('${HERO_BG}')` }}
            />

            {/* Light base wash — keeps brand-blue tone but lets the port image breathe */}
            <div
                aria-hidden
                className="absolute inset-0 -z-10 bg-[#001F3F]/20"
            />

            {/* Localised dark gradient ONLY behind the text block — fades quickly */}
            <div
                aria-hidden
                className="absolute inset-0 -z-10"
                style={{
                    backgroundImage:
                        "radial-gradient(ellipse 60% 70% at 22% 55%, rgba(0,19,42,0.72) 0%, rgba(0,19,42,0.55) 30%, rgba(0,19,42,0.25) 55%, rgba(0,19,42,0) 75%)",
                }}
            />

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
                <div className="max-w-2xl lg:max-w-[640px] lg:pr-8">
                    <span
                        data-testid="hero-eyebrow"
                        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/15 backdrop-blur border border-white/30 text-white text-[11px] sm:text-xs font-semibold tracking-[0.16em] uppercase"
                    >
                        <Anchor size={13} />
                        Caribbean Regional Connectivity & Logistics
                    </span>

                    <h1
                        data-testid="hero-title"
                        style={TITLE_SHADOW}
                        className="mt-8 font-display font-extrabold text-white text-[2.5rem] sm:text-5xl lg:text-[68px] leading-[1.02] tracking-tight text-balance"
                    >
                        Caribbean RE-Connect
                    </h1>

                    <p
                        data-testid="hero-subtitle"
                        style={SUBTITLE_SHADOW}
                        className="mt-8 text-lg sm:text-xl lg:text-[22px] font-semibold text-white/95 max-w-2xl leading-[1.45]"
                    >
                        Strengthening regional connectivity and logistics
                        across the Caribbean.
                    </p>
                </div>
            </div>
        </section>
    );
}
