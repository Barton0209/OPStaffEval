# System_Ocenok - Development Guidelines

## Code Quality Standards

### TypeScript/React Frontend Standards
- **Component Structure**: Functional components with explicit Props typing
- **State Management**: useState for local state, useMemo for derived values
- **Effect Patterns**: useEffect for data loading with proper cleanup
- **Type Safety**: Strict TypeScript with explicit types for all API responses
- **Naming Conventions**: PascalCase for components, camelCase for functions/variables
- **Import Organization**: Grouped by external libraries, then internal modules, then types

### Python Backend Standards
- **Type Hints**: Full type annotations using Mapped, relationship from SQLAlchemy
- **Enum Usage**: Python enum for status fields (UserRole, EvaluationStatus, etc.)
- **Pydantic Models**: Separate input/output schemas for API endpoints
- **Error Handling**: HTTPException for API errors with descriptive messages
- **Naming Conventions**: snake_case for functions/variables, PascalCase for classes

## Common Code Formatting Patterns

### TypeScript/React
- **JSX Elements**: Self-closing tags for empty elements
- **Conditional Rendering**: Ternary operators and logical && for simple conditions
- **Array Mapping**: Explicit key props for list items
- **Optional Chaining**: Use optional chaining (?.) for nested properties
- **Template Literals**: Backticks for multi-line strings and interpolation

### Python
- **F-strings**: Modern Python 3.6+ f-strings for string formatting
- **Type Checking**: isinstance() for runtime type checking
- **Context Managers**: with statements for file/database operations
- **List Comprehensions**: For filtering and transforming collections
- **Default Parameters**: Use None as default, check inside function

## Structural Conventions

### Frontend Component Structure
1. Imports (React, types, components, API, utilities)
2. Props type definition
3. Component function with destructured props
4. State declarations (useState)
5. Ref declarations (useRef)
6. Derived values (useMemo)
7. Effect hooks (useEffect)
8. Event handlers (async functions)
9. Helper functions
10. Column definitions (for tables)
11. JSX return statement

### Backend API Structure
1. Imports (FastAPI, models, schemas, services)
2. Router initialization
3. Dependency functions (get_db, require_roles)
4. Request/Response models (Pydantic)
5. Endpoint functions with decorators
6. Service layer calls
7. Response formatting

## Naming Standards

### Database Models
- Singular names (User, Employee, Assignment)
- PascalCase for class names
- snake_case for column names
- Foreign key naming: `{model}_id`

### API Endpoints
- snake_case for route paths
- HTTP method prefixes (GET, POST, PATCH, DELETE)
- Resource-based naming (/api/admin/assignments, /api/registry/rows)

### Variables and Functions
- camelCase for JavaScript/TypeScript
- snake_case for Python
- Descriptive names that explain purpose
- Boolean variables use is/has/can prefixes

## Documentation Standards

### TypeScript/React
- **Component Props**: Documented with JSDoc-style comments
- **Type Definitions**: Named types for complex objects
- **Function Documentation**: Parameters and return values documented
- **Inline Comments**: For complex logic, not obvious code

### Python
- **Docstrings**: Google-style docstrings for functions/classes
- **Type Hints**: Self-documenting through type annotations
- **Comment Style**: # for single-line, """ for docstrings
- **Import Organization**: Standard library, third-party, local

## Security Practices

### Authentication
- JWT tokens with version tracking
- Password hashing with bcrypt
- Token invalidation on password change
- Role-based access control (RBAC)

### Input Validation
- Pydantic models for request validation
- File upload validation (size, type)
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via proper escaping

### Data Access
- Organization isolation via organization_id
- User authorization checks before operations
- Scope limitation (site_chief can only access own site)

## Database Patterns

### SQLAlchemy Best Practices
- Use Mapped[T] for type-safe column definitions
- Define relationships with foreign_keys parameter
- Use joinedload() for eager loading
- Index frequently queried columns
- Use UniqueConstraint for business keys

### Migration Strategy
- Alembic for schema migrations
- Auto-generated migrations with --autogenerate
- Manual review before applying migrations
- Version tracking in database

## API Design Patterns

### RESTful Conventions
- Resource-based URL structure
- HTTP status codes for outcomes (200, 201, 400, 403, 404)
- JSON request/response bodies
- Consistent error response format

### Error Handling
- HTTPException with descriptive messages
- Validation errors from Pydantic
- Database errors wrapped in HTTPException
- User-friendly error messages

## Testing Patterns

### Backend Testing
- pytest for test framework
- Test client for API endpoints
- Database fixtures for test data
- Coverage for critical paths

### Frontend Testing
- React Testing Library for components
- Mock API responses for unit tests
- Integration tests for key workflows

## Build and Deployment

### Frontend Build
- Vite for development and production builds
- Capacitor for Android mobile app
- Environment variables for configuration
- Build optimization with code splitting

### Backend Deployment
- Uvicorn ASGI server
- Environment-based configuration
- Database migrations on startup
- Logging with structlog

## Common Implementation Patterns

### Data Loading Pattern
```typescript
const [data, setData] = useState<Type[]>([]);
const [error, setError] = useState("");

useEffect(() => {
  (async () => {
    try {
      const result = await apiEndpoint();
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  })();
}, [dependencies]);
```

### Bulk Update Pattern
```python
updated = 0
errors: list[str] = []
for item_id in item_ids:
    item = db.get(Model, item_id)
    if not item or item.organization_id != user.organization_id:
        errors.append(f"id={item_id}: not found")
        continue
    # Process item
    updated += 1
db.commit()
return {"updated": updated, "errors": errors}
```

### Excel Import Pattern
1. Validate file signature (PK\x03\x04 for zip/xlsx)
2. Check file size limits
3. Check for zip-bomb attacks
4. Process row by row with error handling
5. Use savepoints for individual row failures
6. Emit domain events for audit trail

## Internal API Usage Patterns

### API Client Structure
```typescript
// api/admin.ts
export const apiDashboard = async (): Promise<Dashboard> => {
  const res = await fetch("/api/admin/dashboard");
  return await res.json();
};

export const apiBulkAssignments = async (body: BulkAssignmentsIn) => {
  const res = await fetch("/api/admin/assignments/bulk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return await res.json();
};
```

### Service Layer Separation
- API layer handles HTTP concerns
- Service layer contains business logic
- Models handle data persistence
- Clear separation of concerns

## Popular Annotations and Decorators

### Python
- `@router.get/post/put/delete()` - FastAPI route decorators
- `@Depends()` - Dependency injection
- `@router.patch()` - Partial updates
- `response_model=` - Response type validation

### TypeScript/React
- `type Props = {...}` - Component props typing
- `useMemo(() => {...}, [deps])` - Memoized calculations
- `useEffect(() => {...}, [deps])` - Side effects
- `React.FC` - Functional component typing (optional)

## Performance Considerations

### Frontend
- useMemo for expensive calculations
- useCallback for event handlers in lists
- Virtual scrolling for large tables
- Debouncing for search inputs

### Backend
- Database indexes on foreign keys
- Eager loading with joinedload()
- Pagination for large result sets
- Connection pooling via SQLAlchemy

## Accessibility Standards

### Frontend
- Semantic HTML elements
- ARIA labels for interactive elements
- Keyboard navigation support
- Color contrast ratios
- Screen reader friendly markup

## Code Review Checklist

- [ ] Type safety maintained throughout
- [ ] Error handling for all edge cases
- [ ] Security checks (authorization, validation)
- [ ] Database queries optimized
- [ ] API responses consistent
- [ ] Tests cover critical paths
- [ ] Documentation updated
- [ ] No hardcoded secrets or credentials
- [ ] Logging appropriate for production
- [ ] Code follows project conventions