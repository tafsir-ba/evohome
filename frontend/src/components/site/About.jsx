import React from "react";

export default function About() {
    return (
        <section
            id="about"
            data-testid="about-section"
            className="relative bg-white py-20 sm:py-28"
        >
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
                <span className="eyebrow" data-testid="about-eyebrow">
                    About the Program
                </span>
                <h2
                    data-testid="about-title"
                    className="mt-5 font-display font-semibold text-3xl sm:text-4xl lg:text-[44px] leading-[1.1] tracking-tight text-[#00478F] text-balance"
                >
                    A regional initiative for connectivity, trade, and
                    resilience.
                </h2>
                <p className="mt-6 text-base sm:text-lg text-foreground/75 leading-relaxed">
                    Caribbean RE-Connect supports a coordinated agenda to
                    strengthen the systems that move people, goods, and
                    information across the region — from modern ports and
                    logistics to digital systems and climate-resilient
                    infrastructure.
                </p>
            </div>
        </section>
    );
}
