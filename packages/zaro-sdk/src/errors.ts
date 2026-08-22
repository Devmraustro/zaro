export class ZaroError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly details?: unknown;

  constructor(message: string, code: string, statusCode: number, details?: unknown) {
    super(message);
    this.name = "ZaroError";
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
  }
}

export class AuthenticationError extends ZaroError {
  constructor(message = "Authentication required") {
    super(message, "unauthorized", 401);
    this.name = "AuthenticationError";
  }
}

export class ForbiddenError extends ZaroError {
  constructor(message = "Insufficient permissions") {
    super(message, "forbidden", 403);
    this.name = "ForbiddenError";
  }
}

export class NotFoundError extends ZaroError {
  constructor(message = "Resource not found") {
    super(message, "not_found", 404);
    this.name = "NotFoundError";
  }
}

export class ValidationError extends ZaroError {
  constructor(message = "Validation failed", details?: unknown) {
    super(message, "validation_error", 422, details);
    this.name = "ValidationError";
  }
}
