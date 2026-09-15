# System_Ocenok - Technology Stack

## Backend Technologies

### Core Framework
- **Python 3.10+**: Primary programming language
- **FastAPI 0.104+**: Web framework with async support
- **Uvicorn**: ASGI server for production deployment

### Database
- **SQLite**: Primary database engine
- **SQLAlchemy 2.0**: ORM for database operations
- **Alembic**: Database migration tool
- **Pydantic**: Data validation and settings management

### Authentication & Security
- **JWT (PyJWT)**: Token-based authentication
- **bcrypt**: Password hashing
- **python-jose**: JWT operations
- **passlib**: Password hashing utilities

### Data Processing
- **pandas**: Data manipulation and analysis
- **openpyxl**: Excel file reading/writing
- **python-multipart**: File upload handling

### Utilities
- **python-dotenv**: Environment variable management
- **httpx**: Async HTTP client
- **apscheduler**: Background task scheduling
- **structlog**: Structured logging

## Frontend Technologies

### Core Framework
- **TypeScript 5.0+**: Type-safe JavaScript
- **React 18+**: UI component library
- **Vite 4.0+**: Build tool and dev server

### State Management & Routing
- **React Router**: Client-side routing
- **Context API**: State management

### HTTP & Data
- **Axios**: HTTP client for API communication
- **Zod**: Runtime validation (if used)

### Mobile Deployment
- **Capacitor 6.0+**: Cross-platform mobile app wrapper
- **Android SDK**: Android platform support

### Build Tools
- **ESBuild**: Fast JavaScript bundling
- **PostCSS**: CSS processing

## Development Commands

### Backend Setup
```bash
cd KingiseppApp/backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
cd KingiseppApp/frontend
npm install
npm run dev
npm run build
```

### Android Build
```bash
cd KingiseppApp/frontend
npx cap add android
npx cap sync
npx cap open android
```

### Database Migrations
```bash
cd KingiseppApp/backend
alembic revision --autogenerate -m "message"
alembic upgrade head
```

## Key Dependencies

### Backend (requirements.txt)
- fastapi>=0.104.0
- uvicorn[standard]>=0.24.0
- sqlalchemy>=2.0.0
- alembic>=1.12.0
- pydantic>=2.0.0
- pydantic-settings>=2.0.0
- python-jose[cryptography]>=3.3.0
- passlib[bcrypt]>=1.7.4
- python-multipart>=0.0.6
- pandas>=2.0.0
- openpyxl>=3.1.0
- httpx>=0.25.0
- apscheduler>=3.10.0
- structlog>=23.1.0

### Frontend (package.json)
- react>=18.2.0
- react-dom>=18.2.0
- typescript>=5.0.0
- vite>=4.4.0
- @capacitor/core>=6.0.0
- @capacitor/android>=6.0.0
- axios>=1.6.0
- react-router-dom>=6.20.0