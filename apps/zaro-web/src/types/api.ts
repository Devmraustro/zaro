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

export interface Product {
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
  variants: ProductVariantPublic[];
  media: ProductMediaPublic[];
}

export interface PaginatedProducts {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
}

// --- Custom requests ----------------------------------------------------

export type ProductType =
  | "table"
  | "chair"
  | "sofa"
  | "shelf"
  | "bed"
  | "desk"
  | "metalwork"
  | "other";

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

export interface AdminProduct extends Product {
  status: string;
  created_at: string;
  updated_at: string;
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
