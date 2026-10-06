-- Quiz SENIAT: control de acceso por correo con vencimiento.
-- Las tablas tienen RLS activado. Nadie con la clave pública puede leerlas
-- salvo un usuario autenticado cuyo correo esté en allowed_emails y no haya vencido.

create table if not exists public.allowed_emails (
  email      text primary key check (email = lower(email) and email like '%_@_%'),
  nombre     text,
  expires_at timestamptz,            -- null = sin vencimiento
  created_at timestamptz not null default now()
);
alter table public.allowed_emails enable row level security;   -- sin políticas: solo service_role / postgres

create table if not exists public.questions (
  id         integer primary key,    -- clase*1000 + posición en el archivo de la clase
  clase      integer not null check (clase > 0),
  tema       text not null,
  tipo       text not null check (tipo in ('mc','multi','tf')),
  q          text not null,
  o          jsonb not null check (jsonb_typeof(o) = 'array'),
  a          jsonb not null,
  e          text not null default '',
  created_at timestamptz not null default now()
);
alter table public.questions enable row level security;

-- ¿El usuario de la sesión actual tiene acceso vigente?
create or replace function public.is_allowed()
returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.allowed_emails a
    where a.email = lower(coalesce(auth.jwt() ->> 'email', ''))
      and (a.expires_at is null or a.expires_at > now())
  );
$$;
revoke all on function public.is_allowed() from public, anon;
grant execute on function public.is_allowed() to authenticated;

create policy "lectura con acceso vigente" on public.questions
  for select to authenticated
  using (public.is_allowed());

-- Estado de acceso para mostrarlo en la página (solo devuelve datos del propio correo).
create or replace function public.my_access()
returns jsonb
language sql stable security definer set search_path = ''
as $$
  select coalesce(
    (select jsonb_build_object(
        'allowed', (a.expires_at is null or a.expires_at > now()),
        'expires_at', a.expires_at)
     from public.allowed_emails a
     where a.email = lower(coalesce(auth.jwt() ->> 'email', ''))),
    jsonb_build_object('allowed', false, 'expires_at', null));
$$;
revoke all on function public.my_access() from public, anon;
grant execute on function public.my_access() to authenticated;

-- Hook "Before User Created": no se crean usuarios (ni se envían códigos) para correos fuera de la lista.
-- Se activa en Authentication > Hooks del panel de Supabase.
create or replace function public.hook_before_user_created(event jsonb)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
begin
  if exists (
    select 1 from public.allowed_emails a
    where a.email = lower(event -> 'user' ->> 'email')
      and (a.expires_at is null or a.expires_at > now())
  ) then
    return '{}'::jsonb;
  end if;
  return jsonb_build_object('error', jsonb_build_object(
    'http_code', 403, 'message', 'Este correo no tiene acceso.'));
end;
$$;
revoke all on function public.hook_before_user_created(jsonb) from public, anon, authenticated;
grant execute on function public.hook_before_user_created(jsonb) to supabase_auth_admin;
