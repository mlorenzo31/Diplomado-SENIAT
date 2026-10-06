#!/usr/bin/env python3
"""Genera el quiz a partir de preguntas/claseN.json.

  python3 scripts/build.py check            valida las preguntas
  python3 scripts/build.py offline          dist/Quiz_Diplomado_SENIAT.html (preguntas incrustadas, sin login; solo para ti)
  python3 scripts/build.py online           docs/index.html (sin preguntas; pide login; es lo que se publica)
  python3 scripts/build.py sql [N ...]      dist/seed_claseN.sql para cargar las clases a Supabase
  python3 scripts/build.py all              check + offline + online + sql
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIPOS = {"mc", "multi", "tf"}


def load():
    qs = []
    files = sorted(glob.glob(os.path.join(ROOT, "preguntas", "clase*.json")),
                   key=lambda p: int(re.search(r"clase(\d+)", p).group(1)))
    if not files:
        sys.exit("No hay preguntas/claseN.json")
    for f in files:
        n = int(re.search(r"clase(\d+)", f).group(1))
        with open(f, encoding="utf8") as fh:
            items = json.load(fh)
        for i, q in enumerate(items):
            q = dict(q)
            q["clase"] = n
            q["_src"] = f"{os.path.basename(f)}[{i}]"
            q["id"] = n * 1000 + i + 1
            qs.append(q)
    return qs


def validate(qs):
    errs, seen = [], set()
    for q in qs:
        w = q["_src"]
        for k in ("tema", "tipo", "q", "o", "a", "e"):
            if k not in q:
                errs.append(f"{w}: falta '{k}'")
        if errs and errs[-1].startswith(w):
            continue
        if q["tipo"] not in TIPOS:
            errs.append(f"{w}: tipo '{q['tipo']}' inválido (mc|multi|tf)")
        if not isinstance(q["o"], list) or len(q["o"]) < 2 or not all(isinstance(x, str) and x.strip() for x in q["o"]):
            errs.append(f"{w}: 'o' debe ser una lista de al menos 2 textos")
            continue
        if len(set(q["o"])) != len(q["o"]):
            errs.append(f"{w}: opciones repetidas")
        if q["tipo"] == "tf" and q["o"] != ["Verdadero", "Falso"]:
            errs.append(f"{w}: tf requiere o=['Verdadero','Falso']")
        a = q["a"]
        if q["tipo"] == "multi":
            if not (isinstance(a, list) and len(a) >= 2 and len(set(a)) == len(a)):
                errs.append(f"{w}: multi requiere 'a' como lista de 2 o más índices distintos")
                continue
            idx = a
        else:
            if not isinstance(a, int) or isinstance(a, bool):
                errs.append(f"{w}: 'a' debe ser un entero (índice desde 0)")
                continue
            idx = [a]
        if not all(isinstance(i, int) and 0 <= i < len(q["o"]) for i in idx):
            errs.append(f"{w}: 'a' fuera de rango")
        if not q["e"].strip():
            errs.append(f"{w}: falta la explicación 'e'")
        if q["q"] in seen:
            errs.append(f"{w}: enunciado repetido")
        seen.add(q["q"])
    if errs:
        sys.exit("Errores en las preguntas:\n  " + "\n  ".join(errs))
    return qs


def public(q):
    return {k: q[k] for k in ("clase", "tema", "tipo", "q", "o", "a", "e")}


def js(obj):
    # Seguro dentro de <script>: evita cerrar la etiqueta o abrir un comentario HTML.
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")


def template():
    with open(os.path.join(ROOT, "src", "quiz.html"), encoding="utf8") as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf8") as fh:
        fh.write(text)
    print(f"  {os.path.relpath(path, ROOT)}  ({len(text) // 1024} KB)")


def build_offline(qs):
    csp = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:; base-uri \'none\'; form-action \'none\'">'
    html = template().replace("<!--__CSP__-->", csp).replace("/*__CFG__*/null", "null").replace("/*__DATA__*/null", js([public(q) for q in qs]))
    write(os.path.join(ROOT, "dist", "Quiz_Diplomado_SENIAT.html"), html)


def build_online():
    with open(os.path.join(ROOT, "config.json"), encoding="utf8") as fh:
        cfg = json.load(fh)
    url, key = cfg["supabase_url"].rstrip("/"), cfg["supabase_publishable_key"]
    csp = f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:; connect-src {url}; base-uri \'none\'; form-action \'none\'">'
    html = template().replace("<!--__CSP__-->", csp).replace("/*__CFG__*/null", js({"url": url, "key": key})).replace("/*__DATA__*/null", "null")
    write(os.path.join(ROOT, "docs", "index.html"), html)


def sql_str(s):
    assert "$q$" not in s, "el texto no puede contener $q$"
    return "$q$" + s + "$q$"


def build_sql(qs, clases):
    by = {}
    for q in qs:
        by.setdefault(q["clase"], []).append(q)
    for c in clases or sorted(by):
        if c not in by:
            sys.exit(f"No existe preguntas/clase{c}.json")
        ids = ",".join(str(q["id"]) for q in by[c])
        vals = []
        for q in by[c]:
            vals.append("(%d,%d,%s,%s,%s,%s::jsonb,%s::jsonb,%s)" % (
                q["id"], c, sql_str(q["tema"]), sql_str(q["tipo"]), sql_str(q["q"]),
                sql_str(json.dumps(q["o"], ensure_ascii=False)), sql_str(json.dumps(q["a"])), sql_str(q["e"])))
        # Idempotente: actualiza lo existente, inserta lo nuevo y borra lo que ya no está en el archivo.
        out = [f"-- Clase {c}: sincroniza con preguntas/clase{c}.json",
               f"delete from public.questions where clase = {c} and id not in ({ids});",
               "insert into public.questions (id,clase,tema,tipo,q,o,a,e) values\n" + ",\n".join(vals) +
               "\non conflict (id) do update set clase=excluded.clase, tema=excluded.tema, tipo=excluded.tipo, q=excluded.q, o=excluded.o, a=excluded.a, e=excluded.e;"]
        write(os.path.join(ROOT, "dist", f"seed_clase{c}.sql"), "\n".join(out) + "\n")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    qs = validate(load())
    print(f"{len(qs)} preguntas válidas en {len({q['clase'] for q in qs})} clases")
    if cmd == "check":
        return
    if cmd in ("offline", "all"):
        build_offline(qs)
    if cmd in ("online", "all"):
        build_online()
    if cmd in ("sql", "all"):
        build_sql(qs, [int(x) for x in sys.argv[2:]] if cmd == "sql" else None)
    if cmd not in ("offline", "online", "sql", "all"):
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
