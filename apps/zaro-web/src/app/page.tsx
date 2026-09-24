import HomeHero from "@/components/home/HomeHero";
import SelectedWork from "@/components/home/SelectedWork";
import Craftsmanship from "@/components/home/Craftsmanship";
import CustomDesign from "@/components/home/CustomDesign";
import ProductShowcase from "@/components/home/ProductShowcase";
import Materials from "@/components/home/Materials";
import WhyZaro from "@/components/home/WhyZaro";
import FinalCta from "@/components/home/FinalCta";

export default function HomePage() {
  return (
    <main>
      <HomeHero />
      <SelectedWork />
      <Craftsmanship />
      <CustomDesign />
      <ProductShowcase />
      <Materials />
      <WhyZaro />
      <FinalCta />
    </main>
  );
}