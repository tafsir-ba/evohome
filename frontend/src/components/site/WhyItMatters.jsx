import React from "react";

const STATS = [
    {
        label: "Caribbean economies",
        value: "Small & open",
        desc: "Highly dependent on efficient maritime trade and connectivity.",
    },
    {
        label: "Regional approach",
        value: "Shared agenda",
        desc: "Coordinated action across borders unlocks economies of scale.",
    },
    {
        label: "Climate exposure",
        value: "Front-line region",
        desc: "Resilient logistics systems are critical to regional stability.",
    },
];

export default function WhyItMatters() {
    return (
        <section
            data-testid="why-it-matters"
            className="relative bg-[#F7FAFD] py-20 sm:py-28 border-y border-border"
        >
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-16 items-start">
                    <div className="lg:col-span-5">
                        <span className="eyebrow">Why it matters</span>
                        <h2 className="mt-4 font-display font-semibold text-3xl sm:text-4xl text-[#00478F] leading-tight tracking-tight text-balance">
                            Connectivity is the foundation of regional
                            opportunity.
                        </h2>
                    </div>
                    <div className="lg:col-span-7 space-y-5">
                        <p className="text-base sm:text-lg text-foreground/80 leading-relaxed">
                            The Caribbean&apos;s geography, size, and exposure
                            to climate risks make connectivity a strategic
                            priority. Modern ports, efficient logistics,
                            harmonised customs, and interoperable digital
                            systems are not luxuries — they are the
                            backbone of a competitive and resilient region.
                        </p>
                        <p className="text-base text-foreground/70 leading-relaxed">
                            By working together, Caribbean economies can
                            reduce trade costs, expand market access,
                            attract investment, and respond more
                            effectively to shocks.
                        </p>
                    </div>
                </div>

                <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-px bg-border rounded-lg overflow-hidden border border-border">
                    {STATS.map((s, i) => (
                        <div
                            key={s.label}
                            data-testid={`why-stat-${i}`}
                            className="bg-white p-7 sm:p-8"
                        >
                            <div className="text-xs font-semibold tracking-[0.14em] uppercase text-[#00478F]/70">
                                {s.label}
                            </div>
                            <div className="mt-3 font-display font-semibold text-2xl text-foreground">
                                {s.value}
                            </div>
                            <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                                {s.desc}
                            </p>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
