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

**Sprint 2.3 — Completado**
Autorización de rutas implementada mediante `Depends(require_auth)`. La validación del JWT dejó de estar inline en los endpoints y pasó a una dependencia reutilizable en `app/core/jwt.py`.

**Sprint 3.1 — Completado**
Context API base implementada. `/context` devuelve la identidad del usuario autenticado.

**Sprint 3.2 — Completado**
ContextProvider implementado. `/context` expone las cuatro fuentes del contexto interno de HASH. El contenido se resuelve en Sprint 5.

**Sprint 4.1 — Completado**
Memoria del usuario implementada. HASH solicita autorización incremental de Google Sheets, crea el documento de memoria en el Google Drive del usuario y registra la asociación `user_id → spreadsheet_id`. El refresh token se persiste cifrado con Fernet.

**Sprint 4.2 — Completado**
Lectura de memoria implementada. `GET /memory` devuelve el objeto `Memory` completo del usuario desacoplado de Google Sheets, con `index` (contenido de `id_name`) y `documents` (resto de hojas).

**Sprint 4.3 — Completado**
Escritura de memoria implementada. `POST /memory` escribe registros en la memoria del usuario. Si el documento no existe, lo crea automáticamente y registra la entrada en `id_name` con UUID, nombre, descripción y timestamp.

**Sprint 4.4 — Completado**
Manejo de estados de memoria implementado. `GET /memory/status` detecta y comunica cuatro estados: `not_found`, `active`, `inaccessible`, `unauthorized`. HASH no toma acciones automáticas — solo informa el estado y el frontend decide cómo guiar al usuario.

**Sprint 5.1 — Completado**
Base Compiler implementado. `GET /compiler/base` construye el `BaseContext` con las tres fuentes de identidad de HASH: `personal_log`, `cognitive_base` y `destilador`.

**Sprint 5.2 — Completado**
User Compiler implementado. `GET /compiler/user` construye el `UserContext` a partir del objeto `Memory` del usuario. No accede directamente al almacenamiento.

**Sprint 5.3 — Completado**
Style Compiler implementado. `GET /compiler/style` construye el `StyleContext` a partir de la fuente `style`. Separado del `BaseContext` porque constituye una fuente independiente con responsabilidad propia.

**Sprint 5.4 — Completado**
Hash Compiler implementado. `GET /compiler/hash` construye el `HashContext` reuniendo los tres contextos independientes (`base`, `user`, `style`) sin fusionarlos ni modificar su contenido. Cada fuente conserva su identidad y origen.

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
| google-api-python-client | 2.169.0 |
| google-auth | 2.40.3 |
| google-auth-oauthlib | 1.2.1 |
| cryptography | 44.0.3 |

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
| `CREDENTIALS_SECRET` | Clave Fernet para cifrar el refresh token del usuario |
| `MEMORY_CALLBACK_URI` | URI de callback para el flujo OAuth de memoria |

---

## Configuración de Google OAuth

1. Crear un proyecto en [Google Cloud Console](https://console.cloud.google.com)
2. Ir a **APIs y servicios → Pantalla de consentimiento OAuth** y completar los datos básicos
3. Agregar scopes: `spreadsheets` y `drive.file`
4. Agregar el usuario como tester en **Audiencia**
5. Ir a **APIs y servicios → Credenciales → Crear credenciales → ID de cliente OAuth**
   - Tipo: Aplicación web
   - Orígenes autorizados: `http://localhost:8000`
   - URIs de redireccionamiento autorizados:
     - `http://localhost:8000/auth/callback`
     - `http://localhost:8000/memory/callback`
6. Habilitar **Google Sheets API** en el proyecto
7. Copiar el **Client ID** y **Client Secret** al `.env`

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
| GET | `/context` | Bearer JWT | Devuelve identidad del usuario y contexto de HASH |
| GET | `/memory/status` | Bearer JWT | Estado de la memoria del usuario |
| POST | `/memory/session` | Bearer JWT | Registra la sesión antes del flujo OAuth de memoria |
| GET | `/memory/authorize` | No (requiere sesión) | Inicia el flujo OAuth incremental de Google Sheets |
| GET | `/memory/callback` | No | Callback OAuth de memoria. Crea el documento y persiste credenciales |
| GET | `/memory` | Bearer JWT | Lee la memoria completa del usuario |
| POST | `/memory` | Bearer JWT | Escribe un registro en la memoria del usuario |
| GET | `/compiler/base` | Bearer JWT | Construye el BaseContext de HASH |
| GET | `/compiler/user` | Bearer JWT | Construye el UserContext del usuario |
| GET | `/compiler/style` | Bearer JWT | Construye el StyleContext de HASH |
| GET | `/compiler/hash` | Bearer JWT | Construye el HashContext completo |
| GET | `/docs` | No | Documentación interactiva |

---

## Flujo de autenticación

```
Usuario → GET /auth/login → Google → GET /auth/callback → { token }
```

## Flujo de memoria

```
POST /memory/session  (JWT en header)
GET  /memory/authorize  (navegador)
Google autoriza → GET /memory/callback → memoria creada
```

## Separación de memorias

HASH mantiene dos memorias completamente independientes:

- **Memoria de HASH** — identidad del sistema. Vive en el Modelo Cognitivo Base. No pertenece al usuario.
- **Memoria del usuario** — activo del usuario. Vive en su Google Sheets. HASH solo accede con autorización explícita.

El Compiler recibe ambas como entradas independientes y construye un contexto temporal. Nunca las fusiona.

---

## Arquitectura

Ver [`tree.md`](./tree.md) para el mapa conceptual de la arquitectura actual.

---

## Desarrollo por Sprints

Este proyecto evoluciona por Sprints. Cada Sprint amplía este documento con información real ya implementada. No se documenta funcionalidad futura.
