import React, { useEffect } from 'react';
import Navbar from '@/components/site/Navbar';
import Hero from '@/components/site/Hero';
import About from '@/components/site/About';
import FocusAreas from '@/components/site/FocusAreas';
import RegionalPerspective from '@/components/site/RegionalPerspective';
import Contact from '@/components/site/Contact';
import Footer from '@/components/site/Footer';
import { applyCaribSiteBranding } from '@/components/gantt/ganttBrandingUtils';
import '@/styles/carib-landing.css';

export const CaribLanding = () => {
  useEffect(() => {
    applyCaribSiteBranding();
  }, []);

  return (
    <main
      data-testid="landing-page"
      className="carib-landing min-h-screen bg-white text-foreground"
    >
      <Navbar />
      <Hero />
      <About />
      <FocusAreas />
      <RegionalPerspective />
      <Contact />
      <Footer />
    </main>
  );
};
