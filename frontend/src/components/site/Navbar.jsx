import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X, LogIn } from "lucide-react";

const LOGO_URL =
    "https://customer-assets.emergentagent.com/job_f6048c2b-8ed4-470f-aaf5-275d78ad015a/artifacts/civduknz_CRC%20logo.svg";

// External login destination — configured via REACT_APP_LOGIN_URL.
const LOGIN_URL = process.env.REACT_APP_LOGIN_URL || "/login";

const NAV_LINKS = [
    { href: "#about", label: "About", testid: "nav-about", external: false },
    { href: "#focus-areas", label: "Focus Areas", testid: "nav-focus-areas", external: false },
    {
        href: "#regional-perspective",
        label: "Regional Perspective",
        testid: "nav-regional",
        external: false,
    },
    { href: "#contact", label: "Contact", testid: "nav-contact", external: false },
    { href: "/gantt", label: "Planning", testid: "nav-gantt", external: false, route: true },
    { href: "/map", label: "Vessel map", testid: "nav-map", external: false, route: true },
];

export default function Navbar() {
    const [scrolled, setScrolled] = useState(false);
    const [open, setOpen] = useState(false);

    useEffect(() => {
        const onScroll = () => setScrolled(window.scrollY > 8);
        onScroll();
        window.addEventListener("scroll", onScroll, { passive: true });
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    return (
        <header
            data-testid="site-navbar"
            className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
                scrolled
                    ? "bg-white/95 backdrop-blur-xl border-b border-border shadow-[0_1px_0_rgba(0,0,0,0.02)]"
                    : "bg-white/85 backdrop-blur-md border-b border-transparent"
            }`}
        >
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 sm:h-24 flex items-center justify-between">
                <a
                    href="#home"
                    data-testid="brand-logo"
                    className="flex items-center gap-4"
                >
                    <img
                        src={LOGO_URL}
                        alt="Caribbean RE-Connect logo"
                        className="h-14 w-auto sm:h-16"
                    />
                    <div className="hidden sm:flex flex-col leading-tight">
                        <span className="font-display font-semibold text-[17px] text-[#00478F]">
                            Caribbean RE-Connect
                        </span>
                        <span className="text-[12px] text-muted-foreground tracking-wide">
                            Caribbean Regional Connectivity
                        </span>
                    </div>
                </a>

                <nav className="hidden lg:flex items-center gap-10">
                    {NAV_LINKS.map((link) =>
                        link.route ? (
                            <Link
                                key={link.href}
                                to={link.href}
                                data-testid={link.testid}
                                className="text-sm font-medium text-foreground/80 hover:text-[#00478F] transition-colors relative after:absolute after:left-0 after:-bottom-1 after:h-[2px] after:w-0 hover:after:w-full after:bg-[#00478F] after:transition-all after:duration-300"
                            >
                                {link.label}
                            </Link>
                        ) : (
                            <a
                                key={link.href}
                                href={link.href}
                                data-testid={link.testid}
                                className="text-sm font-medium text-foreground/80 hover:text-[#00478F] transition-colors relative after:absolute after:left-0 after:-bottom-1 after:h-[2px] after:w-0 hover:after:w-full after:bg-[#00478F] after:transition-all after:duration-300"
                            >
                                {link.label}
                            </a>
                        )
                    )}
                    <a
                        href={LOGIN_URL}
                        data-testid="nav-login"
                        className="inline-flex items-center gap-2 h-10 px-5 rounded-md bg-[#00478F] hover:bg-[#003366] text-white text-sm font-semibold tracking-wide transition-colors shadow-[0_4px_14px_-6px_rgba(0,71,143,0.55)]"
                    >
                        <LogIn size={15} strokeWidth={2.2} />
                        Login
                    </a>
                </nav>

                <button
                    type="button"
                    data-testid="mobile-menu-toggle"
                    onClick={() => setOpen((v) => !v)}
                    className="lg:hidden h-10 w-10 inline-flex items-center justify-center rounded-md border border-border text-[#00478F]"
                    aria-label="Toggle navigation"
                >
                    {open ? <X size={20} /> : <Menu size={20} />}
                </button>
            </div>

            {open && (
                <div
                    data-testid="mobile-menu"
                    className="lg:hidden border-t border-border bg-white"
                >
                    <div className="px-4 py-4 flex flex-col gap-1">
                        {NAV_LINKS.map((link) =>
                            link.route ? (
                                <Link
                                    key={link.href}
                                    to={link.href}
                                    onClick={() => setOpen(false)}
                                    data-testid={`${link.testid}-mobile`}
                                    className="px-3 py-3 text-sm font-medium text-foreground/80 hover:text-[#00478F] hover:bg-[#E6F0FA] rounded-md"
                                >
                                    {link.label}
                                </Link>
                            ) : (
                                <a
                                    key={link.href}
                                    href={link.href}
                                    onClick={() => setOpen(false)}
                                    data-testid={`${link.testid}-mobile`}
                                    className="px-3 py-3 text-sm font-medium text-foreground/80 hover:text-[#00478F] hover:bg-[#E6F0FA] rounded-md"
                                >
                                    {link.label}
                                </a>
                            )
                        )}
                        <a
                            href={LOGIN_URL}
                            onClick={() => setOpen(false)}
                            data-testid="nav-login-mobile"
                            className="mt-2 inline-flex items-center justify-center gap-2 h-11 px-4 rounded-md bg-[#00478F] hover:bg-[#003366] text-white text-sm font-semibold"
                        >
                            <LogIn size={15} strokeWidth={2.2} />
                            Login
                        </a>
                    </div>
                </div>
            )}
        </header>
    );
}
