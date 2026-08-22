export default function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex min-h-screen">
      <aside className="w-64 bg-zaro-black text-zaro-steel p-6">
        <div className="text-zaro-ivory font-serif text-xl font-bold tracking-wider">ZARO OS</div>
        <nav className="mt-8 space-y-1">
          <a
            href="/admin"
            className="block px-3 py-2 text-sm text-zaro-steel hover:text-zaro-ivory transition-colors"
          >
            Dashboard
          </a>
          <a
            href="/admin/products"
            className="block px-3 py-2 text-sm text-zaro-steel hover:text-zaro-ivory transition-colors"
          >
            Products
          </a>
          <a
            href="/admin/custom-requests"
            className="block px-3 py-2 text-sm text-zaro-steel hover:text-zaro-ivory transition-colors"
          >
            Custom Requests
          </a>
          <a
            href="/admin/orders"
            className="block px-3 py-2 text-sm text-zaro-steel hover:text-zaro-ivory transition-colors"
          >
            Orders
          </a>
        </nav>
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}
