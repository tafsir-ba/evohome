import React from "react";

const LOGO_URL =
    "https://customer-assets.emergentagent.com/job_f6048c2b-8ed4-470f-aaf5-275d78ad015a/artifacts/civduknz_CRC%20logo.svg";

export default function Footer() {
    return (
        <footer
            data-testid="site-footer"
            className="bg-[#001F3F] text-white/85"
        >
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-14">
                <div className="flex flex-col items-center text-center gap-5">
                    <img
                        src={LOGO_URL}
                        alt="Caribbean RE-Connect logo"
                        className="h-14 w-auto bg-white rounded-md p-2"
                    />
                    <div>
                        <div className="font-display font-semibold text-white text-lg">
                            CRC – Caribbean RE-Connect
                        </div>
                        <div className="mt-1 text-sm text-white/70 tracking-wide">
                            Caribbean Regional Connectivity and Logistics
                            Program
                        </div>
                    </div>
                </div>

                <div className="mt-10 pt-6 border-t border-white/10 text-center text-xs text-white/55 tracking-wide">
                    © {new Date().getFullYear()} All Rights Reserved
                </div>
            </div>
        </footer>
    );
}
