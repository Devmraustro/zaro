import Link from "next/link";
import BrandPhoto from "@/components/BrandPhoto";
import { buttonClass } from "@/components/ui/Button";
import { ArrowLeft } from "@/components/ui/icons";

export default function NotFound() {
  return (
    <main className="flex min-h-[100svh] items-center overflow-hidden">
      <div className="relative mx-auto grid w-full max-w-[100rem] grid-cols-1 items-center gap-10 px-6 py-32 sm:px-10 lg:grid-cols-2 lg:px-16">
        <div>
          <p className="eyebrow text-zaro-bronze-dark">Error 404</p>
          <h1 className="mt-5 font-serif text-4xl font-medium leading-[1.05] text-zaro-black sm:text-5xl">
            This piece isn&apos;t in the collection.
          </h1>
          <p className="mt-5 max-w-md text-[0.98rem] leading-relaxed text-zaro-steel">
            The page you were looking for has moved, or was never built. Head back to the
            collection or start a custom order instead.
          </p>
          <div className="mt-9 flex flex-wrap gap-4">
            <Link href="/shop" className={buttonClass("primary")}>
              Back to the collection
            </Link>
            <Link href="/custom" className={buttonClass("outline")}>
              <ArrowLeft className="size-4 rtl-mirror" />
              Custom order
            </Link>
          </div>
        </div>
        <div className="relative aspect-square w-full max-w-md overflow-hidden justify-self-center lg:max-w-none">
          <BrandPhoto name="metalwork" className="" />
        </div>
      </div>
    </main>
  );
}