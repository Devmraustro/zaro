import CustomRequestForm from "@/components/CustomRequestForm";

export default function CustomPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="font-serif text-3xl font-bold text-zaro-black">Custom Orders</h1>
      <p className="mt-2 text-zaro-steel">
        Tell us about your vision. We craft custom furniture to your exact specifications.
      </p>
      <div className="mt-8">
        <CustomRequestForm />
      </div>
    </main>
  );
}
