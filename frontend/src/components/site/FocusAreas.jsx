import React from "react";
import {
    Anchor,
    Truck,
    ShieldCheck,
    Network,
    Handshake,
    Leaf,
} from "lucide-react";

const AREAS = [
    {
        icon: Anchor,
        title: "Ports & Maritime Transport",
        desc: "Modernising port infrastructure and maritime services for regional and global trade.",
    },
    {
        icon: Truck,
        title: "Logistics & Supply Chains",
        desc: "Reliable end-to-end logistics linking islands and international markets.",
    },
    {
        icon: ShieldCheck,
        title: "Customs & Border Management",
        desc: "Simpler, faster, and more transparent processes at the border.",
    },
    {
        icon: Network,
        title: "Digital Systems & Interoperability",
        desc: "Connected digital platforms that share data securely across the region.",
    },
    {
        icon: Handshake,
        title: "Private Sector Participation",
        desc: "An active role for private operators, investors, and innovators.",
    },
    {
        icon: Leaf,
        title: "Climate Resilience",
        desc: "Sustainable, climate-resilient transport and digital infrastructure.",
    },
];

export default function FocusAreas() {
    return (
        <section
            id="focus-areas"
            data-testid="focus-areas-section"
            className="bg-[#F7FAFD] py-20 sm:py-28 border-y border-border"
        >
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="max-w-2xl mx-auto text-center">
                    <span className="eyebrow">Focus Areas</span>
                    <h2 className="mt-5 font-display font-semibold text-3xl sm:text-4xl text-[#00478F] leading-tight tracking-tight text-balance">
                        Six priority areas shaping the program.
                    </h2>
                </div>

                <div className="mt-14 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 lg:gap-6">
                    {AREAS.map((a, i) => {
                        const Icon = a.icon;
                        return (
                            <article
                                key={a.title}
                                data-testid={`focus-card-${i}`}
                                className="group bg-white border border-border rounded-lg p-7 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_18px_40px_-20px_rgba(0,71,143,0.25)] hover:border-[#00478F]/30"
                            >
                                <div className="h-12 w-12 rounded-md bg-[#E6F0FA] text-[#00478F] flex items-center justify-center group-hover:bg-[#00478F] group-hover:text-white transition-colors">
                                    <Icon size={22} />
                                </div>
                                <h3 className="mt-6 font-display font-semibold text-lg text-foreground">
                                    {a.title}
                                </h3>
                                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                                    {a.desc}
                                </p>
                            </article>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}
