# HASH Cloud

Backend del ecosistema HASH.

## Responsabilidad

HASH Cloud es el núcleo de infraestructura del ecosistema HASH. Concentra los servicios de autenticación, contexto, memoria, compilación de conocimiento y comunicación con servicios externos.

No implementa el razonamiento del LLM.
No almacena la memoria del usuario como fuente de verdad. La memoria persistente vive en Google Drive.

---

## Estado del proyecto

**Sprint 1.1 — Completado**
Estructura base del proyecto inicializada.

**Sprint 1.2 — Completado**
Aplicación FastAPI funcionando localmente con endpoint `/health`.

**Sprint 1.3 — Completado**
Dockerfile y variables de entorno configurados. HASH Cloud ejecutable localmente y en Docker.

**Sprint 2.1 — Completado**
Autenticación con Google OAuth implementada. HASH Cloud identifica al usuario autenticado y devuelve su información básica.

**Sprint 2.2 — Completado**
JWT implementado. El callback de Google genera un token. `/auth/me` valida el token y devuelve la identidad del usuario.

---

## Dependencias

| Paquete | Versión |
|---|---|
| fastapi | 0.139.0 |
| uvicorn | 0.51.0 |
| authlib | 1.7.2 |
| httpx | 0.28.1 |
| python-dotenv | 1.2.2 |
| itsdangerous | 2.2.0 |
| PyJWT | 2.7.0 |

Instalar:

```bash
pip install -r requirements.txt
```

---

## Variables de entorno

| Variable | Descripción |
|---|---|
| `APP_NAME` | Nombre de la aplicación |
| `APP_ENV` | Entorno de ejecución (`development` / `production`) |
| `HOST` | Host del servidor |
| `PORT` | Puerto del servidor |
| `GOOGLE_CLIENT_ID` | Client ID del proyecto en Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Client Secret del proyecto en Google Cloud Console |
| `GOOGLE_REDIRECT_URI` | URI de callback registrada en Google (`/auth/callback`) |
| `SESSION_SECRET` | Clave secreta para firmar la sesión de OAuth |
| `JWT_SECRET` | Clave secreta para firmar los tokens JWT |
| `JWT_ALGORITHM` | Algoritmo JWT (default: `HS256`) |
| `JWT_EXPIRE_MINUTES` | Duración del token en minutos (default: `60`) |

---

## Configuración de Google OAuth

1. Crear un proyecto en [Google Cloud Console](https://console.cloud.google.com)
2. Ir a **APIs y servicios → Pantalla de consentimiento OAuth** y completar los datos básicos
3. Ir a **APIs y servicios → Credenciales → Crear credenciales → ID de cliente OAuth**
   - Tipo: Aplicación web
   - Orígenes autorizados de JavaScript: `http://localhost:8000`
   - URI de redireccionamiento autorizado: `http://localhost:8000/auth/callback`
4. Copiar el **Client ID** y **Client Secret** al `.env`

---

## Flujo de autenticación

```
Usuario → HASH AI (Frontend)
              │
              │ GET /auth/login
              ▼
         HASH Cloud ──── redirect ────► Google
                                            │
                                        Usuario autoriza
                                            │
                         GET /auth/callback ◄────────────
                              │
                         Verifica token con Google
                         Genera JWT
                              │
                         Devuelve { token }
                              │
              ┌───────────────┘
              │ GET /auth/me
              │ Authorization: Bearer <token>
              ▼
         HASH Cloud valida JWT
              │
         Devuelve { id, name, email }
```

---

## Ejecución local

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Primera vez:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## Ejecución con Docker

```bash
docker build -t hash-cloud .
docker run --env-file .env -p 8000:8000 hash-cloud
```

---

## Endpoints disponibles

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/health` | No | Estado del servidor |
| GET | `/auth/login` | No | Inicia el flujo OAuth con Google |
| GET | `/auth/callback` | No | Callback de Google. Devuelve JWT |
| GET | `/auth/me` | Bearer JWT | Devuelve identidad del usuario autenticado |
| GET | `/docs` | No | Documentación interactiva |

---

## Arquitectura

Ver [`tree.md`](./tree.md) para el mapa conceptual de la arquitectura actual.

---

## Desarrollo por Sprints

Este proyecto evoluciona por Sprints. Cada Sprint amplía este documento con información real ya implementada. No se documenta funcionalidad futura.

**Sprint 2.3 — Completado**
Autorización de rutas implementada mediante `Depends(require_auth)`. La validación del JWT dejó de estar inline en los endpoints y pasó a una dependencia reutilizable en `app/core/jwt.py`.

## Autorización de rutas

Las rutas protegidas usan `Depends(require_auth)` de FastAPI. La dependencia lee el header `Authorization`, valida el JWT y devuelve el payload. Si el token es inválido, expiró o no existe, responde HTTP 401 automáticamente.

Rutas públicas (`/health`, `/auth/login`, `/auth/callback`) no requieren token.

**Sprint 3.1 — Completado**
Context API base implementada. `/context` devuelve la identidad del usuario autenticado.

## Context API

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/context` | Bearer JWT | Devuelve la identidad del usuario autenticado |

Respuesta:

```json
{
  "user": {
    "id": "...",
    "name": "...",
    "email": "..."
  }
}
```
