"use client";

import {
  BenefitsSection,
  CtaSection,
  FaqSection,
  FeaturesSection,
  HeroSection,
  SiteFooter,
  SiteHeader,
} from "@/components/landing";

export default function Home() {
  return (
    <>
      <SiteHeader />

      <main>
        <HeroSection />
        <BenefitsSection />
        <FeaturesSection />
        <CtaSection />
        <FaqSection />
      </main>

      <SiteFooter />
    </>
  );
}
