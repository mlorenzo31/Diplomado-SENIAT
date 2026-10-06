# Quiz Diplomado SENIAT

Quiz de práctica con 141+ preguntas (Clases 1 a 6) y control de acceso real por correo, con vencimiento.

## Cómo funciona

```
Compañero ──► GitHub Pages (docs/index.html: solo la interfaz, sin preguntas)
                  │  correo + código de un solo uso
                  ▼
              Supabase Auth ──► hook "before user created": solo entran correos de allowed_emails
                  │  sesión
                  ▼
              Supabase DB (RLS): las preguntas solo se entregan si el correo está en
              allowed_emails y expires_at no ha pasado
```

- La página publicada **no contiene preguntas ni correos**. Sin sesión vigente no hay nada que leer.
- El acceso se corta en el servidor: poner `expires_at = now()` bloquea a esa persona aunque tenga la página abierta.
- Máximo previsto: 50 usuarios (plan gratuito de Supabase).
- Quien entra puede copiar o fotografiar las preguntas. Lo que se controla es quién entra y hasta cuándo.

## Archivos

| Ruta | Qué es | ¿Se sube a Git? |
|---|---|---|
| `src/quiz.html` | Plantilla de la interfaz | sí |
| `scripts/build.py` | Valida preguntas y genera los HTML y el SQL | sí |
| `sql/001_schema.sql` | Tablas, RLS, funciones y hook (ya aplicado en Supabase) | sí |
| `sql/admin.sql` | Plantillas para agregar, extender o revocar correos | sí |
| `config.json` | URL del proyecto y clave **pública** (publishable) | sí |
| `docs/index.html` | Versión publicada, con login (generada) | sí |
| `preguntas/claseN.json` | Preguntas de cada clase | **no** (el repo es público) |
| `dist/Quiz_Diplomado_SENIAT.html` | Copia completa sin login, funciona sin internet, solo para ti | **no** |

## Agregar la Clase 7 (y siguientes)

1. Crea `preguntas/clase7.json` con un arreglo en este formato (`a` cuenta desde 0; en `multi` es una lista; en `tf` las opciones son `["Verdadero","Falso"]`):

   ```json
   [
     {"tema": "Potestad sancionadora", "tipo": "mc",
      "q": "Enunciado", "o": ["A", "B", "C", "D"], "a": 2,
      "e": "Explicación con la página o sección del resumen."},
     {"tema": "Prescripción", "tipo": "multi", "q": "...", "o": ["...", "..."], "a": [0, 2], "e": "..."}
   ]
   ```
   El número de clase sale del nombre del archivo. No lleva el campo `clase`.
2. `python3 scripts/build.py check` valida el formato.
3. `python3 scripts/build.py all` regenera `dist/Quiz_Diplomado_SENIAT.html`, `docs/index.html` y `dist/seed_claseN.sql`.
4. Carga `dist/seed_clase7.sql` en Supabase (SQL Editor, o pídeselo a Claude). Es idempotente: se puede repetir tras corregir una pregunta.
5. Sube `docs/index.html` y `scripts/` si cambiaron. Las preguntas nunca se suben.

Los ids son `clase*1000 + posición`. Si reordenas un archivo, cambia el id de cada pregunta y se pierde el progreso local de esas preguntas.

## Administrar correos

Usa `sql/admin.sql`. Los correos solo existen en la tabla `allowed_emails`.

## Configuración única en el panel de Supabase

Estos pasos no se pueden hacer por API y son obligatorios:

1. **Authentication → Hooks → Before User Created**: elegir "Postgres function" → `public.hook_before_user_created`. Sin esto cualquiera puede recibir un código.
2. **Authentication → Emails → SMTP Settings**: activar SMTP propio. El correo integrado de Supabase solo envía a miembros del equipo. Con Gmail: `smtp.gmail.com`, puerto 465, tu correo y una contraseña de aplicación (requiere verificación en dos pasos).
3. **Authentication → Emails → Templates**: en "Magic Link" y en "Confirm signup" cambiar el cuerpo por:
   ```html
   <h2>Tu código para el Quiz SENIAT</h2>
   <p>Código: <strong>{{ .Token }}</strong></p>
   <p>Vence en una hora. Si no lo pediste, ignora este correo.</p>
   ```
4. **Authentication → Rate Limits**: bajar "emails sent per hour" a unos 30 para proteger la cuenta de correo.
5. **Authentication → URL Configuration**: poner como Site URL la dirección de GitHub Pages.
6. **GitHub → Settings → Pages**: Deploy from a branch, carpeta `/docs`.

## Pruebas

La interfaz se probó con Playwright contra un Supabase simulado: login, correo rechazado, código incorrecto, carga de preguntas, ambos modos de quiz, nota, progreso, acceso vencido y ausencia de preguntas en el HTML publicado.
