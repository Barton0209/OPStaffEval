# System_Ocenok - Project Structure

## Directory Organization

```
System_Ocenok/
├── KingiseppApp/              # Main application directory
│   ├── backend/               # Python FastAPI backend
│   │   ├── app/               # Application code
│   │   │   ├── api/           # API endpoints
│   │   │   │   ├── admin.py   # Admin panel endpoints
│   │   │   │   ├── economist.py # Economist panel endpoints
│   │   │   │   ├── field.py   # Field worker endpoints
│   │   │   │   ├── notifications.py # Notification endpoints
│   │   │   │   └── registry.py # Registry endpoints
│   │   │   ├── services/      # Business logic layer
│   │   │   │   ├── evaluations.py
│   │   │   │   ├── events.py
│   │   │   │   ├── imports.py
│   │   │   │   └── tariff.py
│   │   │   ├── models.py      # Database models
│   │   │   ├── schemas.py     # Pydantic schemas
│   │   │   ├── security.py    # Authentication/authorization
│   │   │   ├── config.py      # Configuration management
│   │   │   ├── db.py          # Database connection
│   │   │   └── main.py        # Application entry point
│   │   ├── alembic/           # Database migrations
│   │   ├── tests/             # Unit and integration tests
│   │   ├── scripts/           # Utility scripts
│   │   ├── requirements.txt   # Python dependencies
│   │   └── .env.example       # Environment template
│   │
│   ├── frontend/              # React/Vite frontend
│   │   ├── src/               # Source code
│   │   │   ├── admin/         # Admin panel components
│   │   │   ├── api/           # API client modules
│   │   │   ├── AdminApp.tsx   # Admin application entry
│   │   │   ├── EconomistApp.tsx # Economist application
│   │   │   ├── FieldApp.tsx   # Field worker application
│   │   │   └── RegistryApp.tsx # Registry application
│   │   ├── public/            # Static assets
│   │   ├── package.json       # Node.js dependencies
│   │   └── vite.config.ts     # Vite configuration
│   │
│   ├── data/                  # Database files
│   ├── backups/               # Automated backups
│   ├── logs/                  # Application logs
│   └── README.md              # Setup documentation
│
├── docs/                      # Documentation
│   ├── README.md              # Project overview
│   ├── TZ_v0.2.md             # Technical specifications
│   └── ПОШАГОВЫЙ ПЛАН...      # Implementation plan
│
└── Files/                     # Data files
    ├── UpLoad/                # Upload directory for imports
    ├── DownLoads/             # Download directory for exports
    └── OLD/                   # Historical data archive
```

## Core Components

### Backend Architecture
- **FastAPI Framework**: Modern Python web framework with automatic OpenAPI documentation
- **SQLAlchemy ORM**: Database abstraction with Alembic migrations
- **Pydantic Models**: Type validation and serialization
- **JWT Authentication**: Secure token-based authentication
- **CORS Middleware**: Cross-origin resource sharing for frontend integration

### Frontend Architecture
- **React 18**: Component-based UI framework
- **Vite**: Fast build tool and development server
- **TypeScript**: Type-safe JavaScript development
- **Capacitor**: Mobile app wrapper for Android deployment
- **Axios**: HTTP client for API communication

### Data Flow
1. User authentication via JWT tokens
2. API requests routed to appropriate handlers
3. Business logic in services layer
4. Database operations via SQLAlchemy
5. Response formatted with Pydantic schemas
6. Frontend displays data with React components

## Architectural Patterns

### Layered Architecture
- **Presentation Layer**: React components and API endpoints
- **Business Logic Layer**: Services handling core operations
- **Data Layer**: Database models and migrations

### RESTful API Design
- Standard HTTP methods (GET, POST, PUT, DELETE)
- Consistent endpoint naming conventions
- Proper HTTP status codes
- JSON request/response bodies

### Security Patterns
- Role-based access control (RBAC)
- Password hashing with bcrypt
- JWT token management
- Input validation and sanitization