import type { ProductType } from "./product-type";

export type { ProductType } from "./product-type";

export interface HealthResponse {
  status: string;
  version: string;
  services: Record<string, string>;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

// --- Catalog (public) ---------------------------------------------------

export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
}

export interface ProductVariantPublic {
  id: string;
  sku: string;
  label: string;
  attributes: Record<string, string> | null;
  effective_price_minor: number;
  currency: string;
}

export interface ProductMediaPublic {
  id: string;
  url_path: string;
  media_kind: string;
  alt_text: string | null;
  sort_order: number;
}

export interface Product<V = ProductVariantPublic> {
  id: string;
  name: string;
  slug: string;
  product_code: string;
  description: string | null;
  category_id: string | null;
  dimensions: Record<string, unknown> | null;
  materials_spec: Array<Record<string, unknown>> | null;
  selling_price_minor: number;
  currency: string;
  stock_status: string;
  production_time_days: number | null;
  delivery_available: boolean;
  delivery_info: string | null;
  is_featured: boolean;
  variants: V[];
  media: ProductMediaPublic[];
}

export interface PaginatedProducts {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
}

// --- Custom requests ----------------------------------------------------

export interface CustomRequestSubmit {
  full_name: string;
  email?: string | null;
  phone?: string | null;
  product_type: ProductType;
  description: string;
  desired_dimensions?: string | null;
  materials?: string | null;
  colors?: string | null;
  finish?: string | null;
  quantity?: number;
  budget_min_minor?: number | null;
  budget_max_minor?: number | null;
}

export interface CustomRequestPublic {
  id: string;
  reference: string;
  product_type: string;
  description: string;
  desired_dimensions: string | null;
  materials: string | null;
  colors: string | null;
  finish: string | null;
  quantity: number;
  budget_min_minor: number | null;
  budget_max_minor: number | null;
  currency: string;
  status: string;
  created_at: string;
  updated_at: string;
}

// --- Admin ----------------------------------------------------------------

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  csrf_token: string;
  user: AuthUser;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  csrf_token: string;
}

export type ProductStatus = "draft" | "active" | "archived";

export type StockStatus = "in_stock" | "made_to_order" | "out_of_stock";

export type ProductMediaKind = "hero" | "gallery" | "detail" | "lifestyle" | "video";

export interface ProductVariantAdmin {
  id: string;
  sku: string;
  label: string;
  attributes: Record<string, string> | null;
  price_override_minor: number | null;
  is_active: boolean;
  sort_order: number;
}

export type AdminProductVariant = ProductVariantAdmin;

export interface AdminProduct extends Product<ProductVariantAdmin> {
  status: ProductStatus;
  created_at: string;
  updated_at: string;
}

export interface AdminCategory extends Category {
  created_at: string;
  updated_at: string;
}

export interface AdminProductList {
  items: AdminProduct[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface AdminCustomRequest extends CustomRequestPublic {
  customer_id: string | null;
  customer_name: string;
  customer_email: string | null;
  customer_phone: string | null;
  notes: string | null;
  source: string;
  assigned_to: string | null;
}

export interface AdminMedia {
  id: string;
  media_kind: string | null;
  alt_text: string | null;
  sort_order: number;
  original_filename: string | null;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface AdminMediaList {
  items: AdminMedia[];
  total: number;
}

export interface DashboardSummary {
  custom_requests?: {
    total: number;
    by_status: Record<string, number>;
    pending: number;
    this_week: number;
  };
  recent_requests?: Array<{
    id: string;
    reference: string;
    status: string;
    product_type: string;
    customer_name: string;
    wilaya: string | null;
    created_at: string | null;
  }>;
  customers_total?: number;
  products?: {
    total: number;
    active: number;
  };
}

export interface TrackResult {
  reference: string;
  product_type: string;
  description: string;
  status: string;
  wilaya: string | null;
  commune: string | null;
  created_at: string;
  updated_at: string;
}

// --- Catalog admin request payloads ---------------------------------------
// Mirrors the extra=forbid backend schemas. `is_featured` is intentionally
// absent from the protected set: it is merchandising data, editable by any
// role holding products.create / products.update.

export interface DimensionsInput {
  width: number;
  height?: number | null;
  depth?: number | null;
  unit: "cm" | "mm" | "m" | "in";
}

export interface MaterialSpecInput {
  name: string;
  grade?: string | null;
  finish?: string | null;
}

export interface ProductCreateInput {
  name: string;
  description?: string | null;
  category_id?: string | null;
  dimensions?: DimensionsInput | null;
  materials_spec?: MaterialSpecInput[] | null;
  weight_kg?: number | null;
  production_time_days?: number | null;
  stock_status?: StockStatus;
  delivery_available?: boolean;
  delivery_info?: string | null;
  is_featured?: boolean;
  meta_title?: string | null;
  meta_description?: string | null;
}

export type ProductUpdateInput = Partial<ProductCreateInput>;

export interface ProductPriceInput {
  selling_price_minor: number;
  currency?: string;
  reason?: string | null;
}

export interface CategoryCreateInput {
  name: string;
  description?: string | null;
  sort_order?: number;
}

export interface CategoryUpdateInput {
  name?: string;
  description?: string | null;
  sort_order?: number;
  is_active?: boolean;
}

export interface VariantCreateInput {
  label: string;
  attributes?: Record<string, string> | null;
  price_override_minor?: number | null;
  sort_order?: number;
}
