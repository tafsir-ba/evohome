import React from "react";
import {
    FileText,
    BookOpen,
    Presentation,
    Newspaper,
    Clock,
} from "lucide-react";

const RESOURCES = [
    {
        icon: FileText,
        title: "Inception Report",
        desc: "Program framing, scope, and approach for the Caribbean RE-Connect initiative.",
    },
    {
        icon: BookOpen,
        title: "Publications",
        desc: "Technical notes and thematic publications on regional connectivity and logistics.",
    },
    {
        icon: Presentation,
        title: "Presentations",
        desc: "Slide decks shared at regional convenings and stakeholder workshops.",
    },
    {
        icon: Newspaper,
        title: "Regional Updates",
        desc: "Periodic updates on program activities, milestones, and regional engagements.",
    },
];

export default function Resources() {
    return (
        <section
            id="resources"
            data-testid="resources-section"
            className="bg-white py-20 sm:py-28"
        >
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
                    <div className="max-w-2xl">
                        <span className="eyebrow">Resources</span>
                        <h2 className="mt-4 font-display font-semibold text-3xl sm:text-4xl lg:text-[44px] leading-[1.1] tracking-tight text-[#00478F] text-balance">
                            A growing library of program materials.
                        </h2>
                        <p className="mt-5 text-base sm:text-lg text-foreground/75 leading-relaxed">
                            Reports, publications, and updates will be
                            shared here as the program advances. Materials
                            below are placeholders for upcoming releases.
                        </p>
                    </div>
                </div>

                <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 lg:gap-6">
                    {RESOURCES.map((r, i) => {
                        const Icon = r.icon;
                        return (
                            <article
                                key={r.title}
                                data-testid={`resource-card-${i}`}
                                className="group relative bg-white border border-border rounded-lg p-6 sm:p-7 flex flex-col transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_18px_40px_-20px_rgba(0,71,143,0.25)] hover:border-[#00478F]/30"
                            >
                                <div className="flex items-center justify-between">
                                    <div className="h-11 w-11 rounded-md bg-[#E6F0FA] text-[#00478F] flex items-center justify-center">
                                        <Icon size={20} />
                                    </div>
                                    <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold tracking-[0.14em] uppercase px-2 py-1 rounded-full bg-[#FFF8DB] text-[#7A5B00] border border-[#F5E6A8]">
                                        <Clock size={11} />
                                        Coming Soon
                                    </span>
                                </div>
                                <h3 className="mt-6 font-display font-semibold text-lg text-foreground">
                                    {r.title}
                                </h3>
                                <p className="mt-2 text-sm text-muted-foreground leading-relaxed flex-1">
                                    {r.desc}
                                </p>
                                <div
                                    aria-disabled
                                    className="mt-6 inline-flex items-center justify-center h-10 px-4 rounded-md text-xs font-semibold tracking-wide uppercase border border-border text-muted-foreground/70 bg-muted/40 cursor-not-allowed select-none"
                                    data-testid={`resource-disabled-cta-${i}`}
                                >
                                    Available Soon
                                </div>
                            </article>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}
