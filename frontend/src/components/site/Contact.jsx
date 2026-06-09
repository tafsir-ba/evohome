import React, { useState } from "react";
import { toast } from "sonner";
import { Send, Mail, Building2, User, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

export default function Contact() {
    const [form, setForm] = useState({
        name: "",
        organization: "",
        email: "",
        message: "",
    });
    const [submitting, setSubmitting] = useState(false);

    const onChange = (key) => (e) =>
        setForm((f) => ({ ...f, [key]: e.target.value }));

    const onSubmit = (e) => {
        e.preventDefault();
        if (!form.name || !form.email || !form.message) {
            toast.error("Please fill in your name, email, and message.");
            return;
        }
        setSubmitting(true);
        // Simple thank-you toast, no backend
        setTimeout(() => {
            toast.success(
                "Thank you for your message. The Caribbean RE-Connect team will be in touch.",
            );
            setForm({ name: "", organization: "", email: "", message: "" });
            setSubmitting(false);
        }, 350);
    };

    return (
        <section
            id="contact"
            data-testid="contact-section"
            className="bg-white py-20 sm:py-28 border-t border-border"
        >
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16">
                    <div className="lg:col-span-5">
                        <span className="eyebrow">Contact</span>
                        <h2 className="mt-4 font-display font-semibold text-3xl sm:text-4xl lg:text-[44px] leading-[1.1] tracking-tight text-[#00478F] text-balance">
                            Engage with the program.
                        </h2>
                        <p className="mt-5 text-base sm:text-lg text-foreground/75 leading-relaxed">
                            For general enquiries about Caribbean
                            RE-Connect, please use the form. We welcome
                            interest from governments, regional
                            institutions, development partners, and the
                            private sector.
                        </p>

                        <div className="mt-10 space-y-5">
                            <div className="flex items-start gap-4">
                                <div className="h-10 w-10 rounded-md bg-[#E6F0FA] text-[#00478F] flex items-center justify-center flex-none">
                                    <Mail size={18} />
                                </div>
                                <div>
                                    <div className="text-xs font-semibold tracking-[0.14em] uppercase text-[#00478F]/70">
                                        General enquiries
                                    </div>
                                    <div className="mt-1 text-sm text-foreground/80">
                                        Use the form to reach the program
                                        team. Responses are coordinated
                                        with regional partners.
                                    </div>
                                </div>
                            </div>
                            <div className="flex items-start gap-4">
                                <div className="h-10 w-10 rounded-md bg-[#E6F0FA] text-[#00478F] flex items-center justify-center flex-none">
                                    <Building2 size={18} />
                                </div>
                                <div>
                                    <div className="text-xs font-semibold tracking-[0.14em] uppercase text-[#00478F]/70">
                                        Institutional partners
                                    </div>
                                    <div className="mt-1 text-sm text-foreground/80">
                                        Caribbean RE-Connect works closely
                                        with regional development
                                        institutions and partner agencies.
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="lg:col-span-7">
                        <form
                            data-testid="contact-form"
                            onSubmit={onSubmit}
                            className="bg-[#F7FAFD] border border-border rounded-lg p-6 sm:p-8 lg:p-10"
                        >
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                                <div className="space-y-2">
                                    <Label
                                        htmlFor="contact-name"
                                        className="text-[12px] font-semibold tracking-[0.1em] uppercase text-[#00478F]/80 flex items-center gap-2"
                                    >
                                        <User size={13} /> Name
                                    </Label>
                                    <Input
                                        id="contact-name"
                                        data-testid="contact-name"
                                        placeholder="Your full name"
                                        value={form.name}
                                        onChange={onChange("name")}
                                        className="h-11 bg-white border-border focus-visible:ring-[#00478F] focus-visible:border-[#00478F]"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label
                                        htmlFor="contact-org"
                                        className="text-[12px] font-semibold tracking-[0.1em] uppercase text-[#00478F]/80 flex items-center gap-2"
                                    >
                                        <Building2 size={13} /> Organization
                                    </Label>
                                    <Input
                                        id="contact-org"
                                        data-testid="contact-organization"
                                        placeholder="Your organization"
                                        value={form.organization}
                                        onChange={onChange("organization")}
                                        className="h-11 bg-white border-border focus-visible:ring-[#00478F] focus-visible:border-[#00478F]"
                                    />
                                </div>
                            </div>
                            <div className="space-y-2 mt-5">
                                <Label
                                    htmlFor="contact-email"
                                    className="text-[12px] font-semibold tracking-[0.1em] uppercase text-[#00478F]/80 flex items-center gap-2"
                                >
                                    <Mail size={13} /> Email
                                </Label>
                                <Input
                                    id="contact-email"
                                    type="email"
                                    data-testid="contact-email"
                                    placeholder="you@example.com"
                                    value={form.email}
                                    onChange={onChange("email")}
                                    className="h-11 bg-white border-border focus-visible:ring-[#00478F] focus-visible:border-[#00478F]"
                                />
                            </div>
                            <div className="space-y-2 mt-5">
                                <Label
                                    htmlFor="contact-message"
                                    className="text-[12px] font-semibold tracking-[0.1em] uppercase text-[#00478F]/80 flex items-center gap-2"
                                >
                                    <MessageSquare size={13} /> Message
                                </Label>
                                <Textarea
                                    id="contact-message"
                                    data-testid="contact-message"
                                    placeholder="Briefly tell us about your interest or enquiry..."
                                    rows={6}
                                    value={form.message}
                                    onChange={onChange("message")}
                                    className="bg-white border-border focus-visible:ring-[#00478F] focus-visible:border-[#00478F] resize-none"
                                />
                            </div>

                            <div className="mt-7 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-4">
                                <p className="text-xs text-muted-foreground max-w-md leading-relaxed">
                                    By submitting, you agree that the
                                    information provided may be used to
                                    respond to your enquiry.
                                </p>
                                <Button
                                    type="submit"
                                    data-testid="contact-submit"
                                    disabled={submitting}
                                    className="bg-[#00478F] hover:bg-[#003366] text-white rounded-md h-12 px-6 font-semibold inline-flex items-center gap-2 disabled:opacity-70"
                                >
                                    {submitting ? "Sending..." : "Send Message"}
                                    <Send size={15} />
                                </Button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </section>
    );
}
