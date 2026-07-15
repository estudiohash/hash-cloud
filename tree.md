# HASH Cloud — Mapa Conceptual

```
hash-cloud/
│
├── app/
│   ├── main.py             Aplicación FastAPI. Registro de middleware y routers.
│   │
│   ├── auth/
│   │   └── router.py       Endpoints OAuth y JWT (/login, /callback, /me).
│   │
│   ├── context/
│   │   └── router.py       Endpoint de contexto del usuario (/context).
│   │
│   ├── api/                Punto de entrada de las solicitudes HTTP externas.
│   ├── cognition/          Orquestación del proceso de razonamiento y respuesta.
│   ├── compiler/           Compilación y estructuración del conocimiento acumulado.
│   │
│   ├── core/
│   │   ├── config.py       Lectura de variables de entorno.
│   │   └── jwt.py          Generación, validación y dependencia de autenticación.
│   │
│   ├── memory/             Acceso y sincronización con la memoria persistente (Google Drive).
│   └── services/           Integración con servicios externos.
│
├── docs/               Documentación técnica del proyecto.
├── tests/              Pruebas del sistema.
│
├── .dockerignore       Archivos excluidos de la imagen Docker.
├── .env                Variables de entorno (no versionado).
├── .gitignore          Archivos excluidos del control de versiones.
├── Dockerfile          Imagen Docker para ejecutar HASH Cloud en cualquier entorno.
├── LICENSE             Licencia del proyecto.
├── README.md           Documentación viva del proyecto.
├── requirements.txt    Dependencias del proyecto.
└── tree.md             Este archivo. Mapa conceptual de la arquitectura.
```

---

**Sprint 1.1** — Estructura base inicializada.
**Sprint 1.2** — `app/main.py` agregado. FastAPI operativo con `/health`.
**Sprint 1.3** — `Dockerfile` y `.dockerignore` agregados. `.env` completado.
**Sprint 2.1** — `app/auth/router.py` y `app/core/config.py` agregados. Google OAuth operativo.
**Sprint 2.2** — `app/core/jwt.py` agregado. JWT generado en callback y validado en `/auth/me`.
**Sprint 2.3** — `require_auth` implementado como dependencia. Validación centralizada en `jwt.py`.
**Sprint 3.1** — `app/context/router.py` agregado. `/context` devuelve identidad del usuario autenticado.
