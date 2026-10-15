r"""
restaurar_backup.py - restaura o backup do Planaveg 2026 na estrutura de pastas que os
scripts de processamento esperam, numa pasta de destino à escolha.

Lê o _manifesto_backup.csv (gerado por organizar_backup.py, na raiz do backup) e, para
cada item, extrai o arquivo do zip (ou copia o arquivo solto) para
<destino>\<destino_relativo>. A pasta <destino> passa a ser a raiz de dados dos scripts
(o equivalente à antiga pasta GEODATABASE\GEOPACKAGE).

Uso (Python 3 comum, não precisa do env geo):
  python restaurar_backup.py --destino D:\PLANAVEG_DADOS                  # simulação
  python restaurar_backup.py --destino D:\PLANAVEG_DADOS --executar       # restaura
Opções:
  --backup PASTA        pasta do backup (padrão: F:\BKP_PLANAVEG ou a variável PLANAVEG_BACKUP)
  --escopo minimo       só o necessário para reprocessar alguma etapa (padrão)
  --escopo completo     tudo: inclui produtos finais, referências, relatórios e registros
  --repo NOME [NOME..]  só o que um repositório produz ou lê: conformidade, cruzamento,
                        computo, visualizacao
  --sobrescrever        substitui arquivos já existentes no destino (padrão: pula se o
                        tamanho for igual)
  --manter-aninhados    não expande os zips que estão dentro de outros zips
  --filtro PADRAO [..]  só os itens cujo destino casa com algum padrão (curingas * e ?,
                        sem diferenciar maiúsculas), ex.: "Computo_Planaveg_2026\*" "IBGE_*"
O destino também pode vir da variável PLANAVEG_RAIZ.
"""
import argparse
import csv
import fnmatch
import os
import shutil
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path, PureWindowsPath

MANIFESTO = "_manifesto_backup.csv"
REPOS = {
    "conformidade": "analise_conformidade_sicar-incra",
    "cruzamento": "cruzamento_vegetacao-secundaria",
    "computo": "computo_hierarquia-planaveg",
    "visualizacao": "visualizacao_categoria-fundiaria",
}


def ler_manifesto(backup):
    arq = backup / MANIFESTO
    if not arq.exists():
        sys.exit(f"Manifesto não encontrado: {arq}")
    with open(arq, encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    if "destino_relativo" not in linhas[0]:
        sys.exit("O manifesto não tem a coluna destino_relativo. Regere com:\n"
                 "  python organizar_backup.py --so-manifesto")
    return linhas


def selecionar(linhas, escopo, repos, filtros=None):
    sel = []
    for l in linhas:
        if l["nivel"] not in ("arquivo", "conteudo_zip") or not l["destino_relativo"]:
            continue
        if filtros and not any(fnmatch.fnmatch(l["destino_relativo"].lower(), f.lower().replace("/", "\\"))
                               for f in filtros):
            continue
        if escopo == "minimo" and l["necessario_reprocessar"] != "sim":
            continue
        if repos:
            texto = " ".join((l["repositorio"], l["script_produtor"], l["scripts_consumidores"]))
            if not any(REPOS[r] in texto for r in repos):
                continue
        sel.append(l)
    return sel


def origem(l, backup_real):
    """(arquivo no backup, membro do zip ou None), ajustando a raiz se o backup mudou de lugar."""
    caminho = l["caminho_backup"]
    arq, _, membro = caminho.partition("::")
    p = PureWindowsPath(arq)
    # o manifesto guarda o caminho absoluto da época; reancora na pasta de backup informada
    partes = p.parts
    for i in range(len(partes)):
        cand = backup_real.joinpath(*partes[i + 1:]) if i + 1 < len(partes) else backup_real
        if cand.exists():
            return cand, (membro or None)
    return Path(arq), (membro or None)


def expandir_aninhado(zip_interno):
    """Extrai um zip que estava dentro de outro zip na mesma pasta (sem subpastas) e o apaga."""
    pasta = zip_interno.parent
    n = 0
    with zipfile.ZipFile(zip_interno) as z:
        for i in z.infolist():
            if i.is_dir():
                continue
            alvo = pasta / PureWindowsPath(i.filename.replace("/", "\\")).name
            with z.open(i) as src, open(alvo, "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            n += 1
    zip_interno.unlink()
    return n


def main():
    ap = argparse.ArgumentParser(description="Restaura o backup do Planaveg 2026")
    ap.add_argument("--backup", default=os.environ.get("PLANAVEG_BACKUP", r"F:\BKP_PLANAVEG"))
    ap.add_argument("--destino", default=os.environ.get("PLANAVEG_RAIZ"))
    ap.add_argument("--escopo", choices=["minimo", "completo"], default="minimo")
    ap.add_argument("--repo", nargs="+", choices=sorted(REPOS))
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--sobrescrever", action="store_true")
    ap.add_argument("--manter-aninhados", action="store_true")
    ap.add_argument("--filtro", nargs="+")
    a = ap.parse_args()
    if not a.destino:
        sys.exit("Informe --destino (ou defina a variável PLANAVEG_RAIZ).")
    backup, destino = Path(a.backup), Path(a.destino)
    if not backup.exists():
        sys.exit(f"Backup não encontrado: {backup}")

    sel = selecionar(ler_manifesto(backup), a.escopo, a.repo, a.filtro)
    tarefas, pulos, manuais = [], 0, []
    for l in sel:
        alvo = destino.joinpath(*PureWindowsPath(l["destino_relativo"]).parts)
        tam = float(l["tamanho_MB"] or 0) * 1024**2
        if l["destino_relativo"].startswith("_SICAR_bruto"):
            manuais.append(l)
        if alvo.exists() and not a.sobrescrever and abs(alvo.stat().st_size - tam) < 1024**2 * 0.01 + 1:
            pulos += 1
            continue
        tarefas.append((l, alvo, tam))

    por_pasta = defaultdict(lambda: [0, 0.0])
    for l, alvo, tam in tarefas:
        topo = PureWindowsPath(l["destino_relativo"]).parts[0] if len(PureWindowsPath(l["destino_relativo"]).parts) > 1 else "(raiz)"
        por_pasta[topo][0] += 1
        por_pasta[topo][1] += tam
    total = sum(t for *_, t in tarefas)
    print(f"Backup:  {backup}\nDestino: {destino}\nEscopo:  {a.escopo}"
          + (f" | repositórios: {', '.join(a.repo)}" if a.repo else "")
          + (f" | filtro: {' '.join(a.filtro)}" if a.filtro else "") + "\n")
    for topo, (n, b) in sorted(por_pasta.items()):
        print(f"  {topo:45s} {n:5d} arquivos  {b / 1024**3:8.2f} GB")
    print(f"\n{len(tarefas)} arquivos a restaurar ({total / 1024**3:.2f} GB); {pulos} já existem no destino.")
    if manuais:
        print("\nObs.: _SICAR_bruto\\ recebe o SICAR nacional em GeoPackage (só referência). Para a "
              "conformidade use Analise_Conformidade_CAR-INCRA\\SICAR_BASE_CAR_ESTADOS_05_2026 (por estado).")
    if not a.executar:
        print("\nSIMULAÇÃO: nada foi gravado. Rode com --executar para restaurar.")
        return

    destino.mkdir(parents=True, exist_ok=True)
    livre = shutil.disk_usage(destino).free
    if livre < total * 1.05:
        sys.exit(f"Espaço insuficiente em {destino}: {livre / 1024**3:.1f} GB livres, "
                 f"precisa de {total / 1024**3:.1f} GB.")

    log = destino / f"_restauracao_{time.strftime('%Y%m%d_%H%M')}.csv"
    por_zip = defaultdict(list)
    for t in tarefas:
        arq, membro = origem(t[0], backup)
        por_zip[(arq, membro is not None)].append((t, membro))
    feitos = falhas = 0
    t0 = time.time()
    with open(log, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["origem", "destino", "tamanho_MB", "status"])
        for (arq, eh_zip), itens in sorted(por_zip.items(), key=lambda k: str(k[0][0])):
            print(f"[{time.time() - t0:7.0f}s] {arq.name} ({len(itens)} arquivo(s))", flush=True)
            try:
                zf = zipfile.ZipFile(arq) if eh_zip else None
                for (l, alvo, tam), membro in itens:
                    alvo.parent.mkdir(parents=True, exist_ok=True)
                    temp = alvo.with_name(alvo.name + ".parcial")
                    if zf:
                        with zf.open(membro) as src, open(temp, "wb") as dst:
                            shutil.copyfileobj(src, dst, 1024 * 1024)
                    else:
                        shutil.copy2(arq, temp)
                    os.replace(temp, alvo)
                    status = "ok"
                    if alvo.suffix.lower() == ".zip" and "aninhado" in l["observacao"].lower() \
                            and not a.manter_aninhados:
                        status = f"ok (zip aninhado expandido: {expandir_aninhado(alvo)} arquivos)"
                    w.writerow([f"{arq}::{membro}" if membro else str(arq), str(alvo), l["tamanho_MB"], status])
                    feitos += 1
                if zf:
                    zf.close()
            except Exception as e:  # noqa: BLE001 - registra e segue para o próximo arquivo do backup
                falhas += 1
                print(f"   FALHOU: {e}")
                w.writerow([str(arq), "", "", f"FALHOU: {e}"])
            f.flush()
    print(f"\n{feitos} arquivos restaurados, {falhas} falha(s). Registro: {log}")
    print(f"\nPara os scripts usarem esta pasta, defina PLANAVEG_RAIZ e PLANAVEG_GEO = {destino}"
          " (ver README).")


if __name__ == "__main__":
    main()
