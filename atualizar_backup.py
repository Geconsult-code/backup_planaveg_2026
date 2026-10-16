r"""
atualizar_backup.py - leva para o F:\BKP_PLANAVEG as mudanças feitas numa cópia restaurada
(restaurar_backup.py) sem refazer o backup inteiro.

A cópia restaurada tem a mesma estrutura da coluna destino_relativo do _manifesto_backup.csv.
Para cada zip do backup, o script compara cada arquivo do zip com o arquivo correspondente da
cópia (tamanho e CRC32, o mesmo que o zip guarda):
  - arquivo diferente na cópia      -> substituído no zip;
  - arquivo novo na cópia, numa pasta que corresponde a um só zip -> acrescentado a esse zip
    (com o mesmo prefixo interno dos outros arquivos);
  - arquivo igual ou ausente na cópia -> copiado do zip antigo sem alteração.
Só os zips com alguma mudança são regravados. Arquivos novos sem zip correspondente são
listados para decisão manual (não são gravados).

Cada zip novo é gravado ao lado do antigo (<nome>.zip.novo), conferido (CRC de todos os
arquivos e lista completa) e só então troca de lugar com o antigo. O antigo vai para a pasta
--antigos (padrão: F:\BKP_PLANAVEG_substituidos_<data>, FORA do backup, para não entrar no
manifesto nem na transferência), com o mesmo caminho relativo; apague-a depois de conferir.
Rodar de novo é seguro: zips já atualizados não têm diferença e são pulados.

Uso (Python 3 comum, não precisa do env geo; feche QGIS/ArcGIS antes):
  python atualizar_backup.py --origem D:\PLANAVEG_TEMP              # simulação: o que mudaria
  python atualizar_backup.py --origem D:\PLANAVEG_TEMP --executar   # grava
Opções:
  --backup PASTA        (padrão: F:\BKP_PLANAVEG ou a variável PLANAVEG_BACKUP)
  --antigos PASTA       para onde vão os zips substituídos
  --apagar-antigos      apaga os zips substituídos em vez de guardá-los
  --ignorar PADRAO ...  padrões de nome a não acrescentar (além dos padrões fixos abaixo)
Ao terminar, regrave o manifesto:  python organizar_backup.py --so-manifesto
"""
import argparse
import csv
import fnmatch
import os
import shutil
import sys
import time
import zipfile
import zlib
from collections import defaultdict
from pathlib import Path, PurePosixPath, PureWindowsPath

MANIFESTO = "_manifesto_backup.csv"
REGISTROS = "_registros_processamento.zip"
IGNORAR_SEMPRE = ["_restauracao_*", "*.parcial", "*.tmp", "*.novo", "_done_*", "*_SIMULACAO*",
                  "desktop.ini", "thumbs.db", "*.pyc", "*.gpkg-wal", "*.gpkg-shm", "*.gpkg-journal",
                  "*.log"]
BLOCO = 8 * 1024 * 1024


def crc32_arquivo(p):
    c = 0
    with open(p, "rb") as f:
        while True:
            b = f.read(BLOCO)
            if not b:
                return c & 0xFFFFFFFF
            c = zlib.crc32(b, c)


def chave(rel):
    """Caminho relativo normalizado (Windows, minúsculas) para comparar."""
    return str(PureWindowsPath(rel)).lower()


def ler_manifesto(backup):
    arq = backup / MANIFESTO
    if not arq.exists():
        sys.exit(f"Manifesto não encontrado: {arq}")
    with open(arq, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def mapear(backup, linhas):
    """zips: {zip_path: {membro: destino_rel}}; destinos conhecidos; soltos: {arquivo: destino_rel}."""
    zips, soltos, conhecidos = defaultdict(dict), {}, set()
    for l in linhas:
        dest = l.get("destino_relativo", "")
        if dest:
            conhecidos.add(chave(dest))
        if l["nivel"] == "conteudo_zip" and dest:
            z, _, membro = l["caminho_backup"].partition("::")
            zips[Path(z)][membro.replace("\\", "/")] = dest
        elif l["nivel"] == "arquivo" and dest and not l["caminho_backup"].lower().endswith(".zip"):
            soltos[Path(l["caminho_backup"])] = dest
    # o manifesto guarda o caminho absoluto da época: reancora na pasta de backup informada
    def reancora(p):
        partes = PureWindowsPath(str(p)).parts
        for i in range(len(partes)):
            cand = backup.joinpath(*partes[i + 1:])
            if cand.exists():
                return cand
        return Path(p)
    zips = {reancora(z): m for z, m in zips.items()}
    soltos = {reancora(a): d for a, d in soltos.items()}
    return zips, soltos, conhecidos


def ignorado(nome, padroes):
    return any(fnmatch.fnmatch(nome.lower(), x.lower()) for x in padroes)


def planejar(origem, backup, padroes):
    linhas = ler_manifesto(backup)
    zips, soltos, conhecidos = mapear(backup, linhas)

    # pasta de destino -> zips que restauram arquivos nela (e o prefixo interno usado)
    pasta_zip = defaultdict(dict)
    for z, membros in zips.items():
        if z.name.lower() == REGISTROS:
            continue
        for membro, dest in membros.items():
            pasta = chave(PureWindowsPath(dest).parent)
            prefixo = str(PurePosixPath(membro).parent)
            pasta_zip[pasta][z] = "" if prefixo == "." else prefixo + "/"

    print(f"Comparando a cópia {origem} com o backup {backup} (CRC32 dos arquivos de mesmo tamanho)...",
          flush=True)
    t0 = time.time()
    plano = {}   # zip -> dict(trocar={membro: origem}, novos={membro: origem}, crc={membro: crc})
    infos = {}   # zip -> {membro: ZipInfo} (conteúdo real do zip, não só o que o manifesto lista)
    lidos = 0
    for z, membros in sorted(zips.items()):
        if z.name.lower() == REGISTROS or not z.exists():
            continue
        trocar, crcs = {}, {}
        with zipfile.ZipFile(z) as zf:
            info = {i.filename: i for i in zf.infolist()}
        infos[z] = info
        for membro, dest in membros.items():
            src = origem / PureWindowsPath(dest)
            i = info.get(membro)
            if i is None or not src.is_file():
                continue
            if src.stat().st_size != i.file_size:
                trocar[membro] = src
                continue
            c = crc32_arquivo(src)
            lidos += i.file_size
            if c != i.CRC:
                trocar[membro] = src
                crcs[membro] = c
        if trocar:
            plano[z] = dict(trocar=trocar, novos={}, crc=crcs)
    print(f"  {lidos / 1024**3:.1f} GB conferidos por CRC em {time.time() - t0:.0f} s", flush=True)

    # arquivos novos na cópia
    sem_zip = []
    for src in sorted(origem.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(origem)
        if chave(rel) in conhecidos or ignorado(src.name, padroes) or len(rel.parts) == 1:
            continue
        candidatos = pasta_zip.get(chave(rel.parent), {})
        if len(candidatos) > 1:   # várias opções (ex.: um zip por arquivo): o de nome mais parecido
            def parecido(z):
                return len(os.path.commonprefix([z.stem.lower(), src.stem.lower()]))
            melhor = sorted(candidatos, key=parecido, reverse=True)
            if parecido(melhor[0]) == parecido(melhor[1]) or parecido(melhor[0]) < 5:
                sem_zip.append((rel, "mais de um zip possível: " + ", ".join(z.name for z in candidatos)))
                continue
            candidatos = {melhor[0]: candidatos[melhor[0]]}
        if not candidatos:
            sem_zip.append((rel, "nenhum zip restaura arquivos nesta pasta"))
            continue
        z, prefixo = next(iter(candidatos.items()))
        if z not in infos:
            sem_zip.append((rel, f"zip {z.name} não encontrado"))
            continue
        membro = prefixo + src.name
        p = plano.setdefault(z, dict(trocar={}, novos={}, crc={}))
        i = infos[z].get(membro)
        if i is None:
            p["novos"][membro] = src
        elif src.stat().st_size != i.file_size:          # já está no zip (manifesto antigo): compara
            p["trocar"][membro] = src
        else:
            c = crc32_arquivo(src)
            if c != i.CRC:
                p["trocar"][membro] = src
                p["crc"][membro] = c
        if not (p["trocar"] or p["novos"]):
            del plano[z]

    soltos_trocar = {}
    for arq, dest in soltos.items():
        src = origem / PureWindowsPath(dest)
        if arq.exists() and src.is_file() and (src.stat().st_size != arq.stat().st_size
                                               or crc32_arquivo(src) != crc32_arquivo(arq)):
            soltos_trocar[arq] = src
    return plano, soltos_trocar, sem_zip


def gravar_zip(z, p):
    novo = z.with_name(z.name + ".novo")
    if novo.exists():
        novo.unlink()
    esperado = {}
    with zipfile.ZipFile(z) as antigo, \
            zipfile.ZipFile(novo, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as out:
        for i in antigo.infolist():
            if i.is_dir():
                continue
            if i.filename in p["trocar"]:
                out.write(p["trocar"][i.filename], i.filename)
                esperado[i.filename] = p["trocar"][i.filename].stat().st_size
            else:
                zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
                zi.compress_type = i.compress_type
                zi.external_attr = i.external_attr
                with antigo.open(i) as src, out.open(zi, "w", force_zip64=i.file_size > 2**31) as dst:
                    shutil.copyfileobj(src, dst, BLOCO)
                esperado[i.filename] = i.file_size
        for membro, src in sorted(p["novos"].items()):
            out.write(src, membro)
            esperado[membro] = src.stat().st_size
    with zipfile.ZipFile(novo) as zf:
        ruim = zf.testzip()
        reais = {i.filename: i.file_size for i in zf.infolist() if not i.is_dir()}
        crc_ok = all(zf.getinfo(m).CRC == c for m, c in p["crc"].items())
    if ruim or reais != esperado or not crc_ok:
        novo.unlink()
        raise RuntimeError(f"zip novo não confere (CRC ruim: {ruim}; lista igual: {reais == esperado}; "
                           f"CRC das trocas: {crc_ok}). O antigo foi mantido.")
    return novo


def guardar_antigo(arq, backup, antigos, apagar):
    if apagar:
        arq.unlink()
        return ""
    destino = antigos / arq.relative_to(backup)
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(arq), str(destino))
    return str(destino)


def main():
    ap = argparse.ArgumentParser(description="Leva para o backup as mudanças de uma cópia restaurada")
    ap.add_argument("--origem", required=True)
    ap.add_argument("--backup", default=os.environ.get("PLANAVEG_BACKUP", r"F:\BKP_PLANAVEG"))
    ap.add_argument("--antigos")
    ap.add_argument("--apagar-antigos", action="store_true")
    ap.add_argument("--ignorar", nargs="+", default=[])
    ap.add_argument("--executar", action="store_true")
    a = ap.parse_args()
    origem, backup = Path(a.origem), Path(a.backup)
    if not origem.is_dir() or not backup.is_dir():
        sys.exit(f"Pasta não encontrada: {origem if not origem.is_dir() else backup}")
    if origem.resolve() == backup.resolve():
        sys.exit("--origem não pode ser o próprio backup.")
    antigos = Path(a.antigos) if a.antigos else backup.with_name(
        f"{backup.name}_substituidos_{time.strftime('%Y%m%d')}")

    plano, soltos, sem_zip = planejar(origem, backup, IGNORAR_SEMPRE + a.ignorar)

    total = 0
    print("\nZips a regravar:")
    for z, p in sorted(plano.items()):
        tam = z.stat().st_size
        total += tam
        print(f"  {z.relative_to(backup)}  ({tam / 1024**3:.2f} GB): "
              f"{len(p['trocar'])} substituído(s), {len(p['novos'])} novo(s)")
        for m in sorted(p["trocar"]):
            print(f"      ~ {m}")
        for m in sorted(p["novos"]):
            print(f"      + {m}")
    if not plano:
        print("  nenhum (o backup já está igual à cópia)")
    for arq, src in soltos.items():
        print(f"  arquivo solto a substituir: {arq.relative_to(backup)}")
    if sem_zip:
        print("\nArquivos novos SEM destino no backup (não serão gravados; decidir manualmente):")
        for rel, motivo in sem_zip:
            print(f"  {rel}  ({motivo})")

    print(f"\n{len(plano)} zip(s), {total / 1024**3:.1f} GB a regravar. Zips antigos -> "
          + ("apagados" if a.apagar_antigos else str(antigos)))
    if not a.executar:
        print("\nSIMULAÇÃO: nada foi gravado. Rode com --executar para atualizar o backup.")
        return

    log = []
    t0 = time.time()
    for z, p in sorted(plano.items()):
        livre = shutil.disk_usage(z.parent).free
        if livre < z.stat().st_size * 1.3 + 1024**3:
            sys.exit(f"Espaço insuficiente em {z.anchor} para regravar {z.name} "
                     f"({livre / 1024**3:.1f} GB livres). Nada mais foi alterado.")
        print(f"[{time.time() - t0:7.0f}s] {z.relative_to(backup)}", flush=True)
        try:
            novo = gravar_zip(z, p)
        except Exception as e:  # noqa: BLE001 - registra e segue
            print(f"   FALHOU: {e}")
            log.append([str(z), "", "", f"FALHOU: {e}"])
            continue
        velho = guardar_antigo(z, backup, antigos, a.apagar_antigos)
        os.replace(novo, z)
        print(f"   ok: {len(p['trocar'])} substituído(s), {len(p['novos'])} novo(s); "
              f"{z.stat().st_size / 1024**3:.2f} GB")
        log.append([str(z), len(p["trocar"]), len(p["novos"]), "ok", velho])
    for arq, src in soltos.items():
        velho = guardar_antigo(arq, backup, antigos, a.apagar_antigos)
        shutil.copy2(src, arq)
        log.append([str(arq), 1, 0, "ok (arquivo solto)", velho])

    if not a.apagar_antigos:
        antigos.mkdir(parents=True, exist_ok=True)
    reg = (antigos if not a.apagar_antigos else origem) / f"_atualizacao_backup_{time.strftime('%Y%m%d_%H%M')}.csv"
    with open(reg, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["arquivo_backup", "substituidos", "novos", "status", "antigo_guardado_em"])
        w.writerows(log)
    falhas = sum(1 for l in log if str(l[3]).startswith("FALHOU"))
    print(f"\n{len(log) - falhas} item(ns) atualizado(s), {falhas} falha(s). Registro: {reg}")
    print("Agora regrave o manifesto:  python organizar_backup.py --so-manifesto")


if __name__ == "__main__":
    main()
