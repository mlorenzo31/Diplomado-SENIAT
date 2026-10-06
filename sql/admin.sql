-- Operaciones de administración. Se ejecutan en el SQL Editor de Supabase (o se las pides a Claude).
-- Los correos NUNCA van al repositorio: solo viven en esta tabla.

-- Agregar compañeros con vencimiento (los correos siempre en minúsculas)
insert into public.allowed_emails (email, nombre, expires_at) values
  ('ejemplo1@gmail.com', 'Ejemplo Uno', '2026-12-31 23:59:00-04'),
  ('ejemplo2@gmail.com', 'Ejemplo Dos', '2026-12-31 23:59:00-04')
on conflict (email) do update set nombre = excluded.nombre, expires_at = excluded.expires_at;

-- Extender el acceso de todos
update public.allowed_emails set expires_at = '2027-03-31 23:59:00-04';

-- Revocar a una persona (pierde acceso a las preguntas de inmediato, aunque tenga sesión abierta)
update public.allowed_emails set expires_at = now() where email = 'ejemplo1@gmail.com';

-- Ver quién tiene acceso vigente
select email, nombre, expires_at, (expires_at is null or expires_at > now()) as vigente
from public.allowed_emails order by email;

-- Cerrar las sesiones abiertas de un correo (opcional; el acceso a datos ya se corta con el update anterior)
-- delete from auth.sessions where user_id in (select id from auth.users where email = 'ejemplo1@gmail.com');
