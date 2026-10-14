r"""
complementar_backup.py - acrescenta ao F:\BKP_PLANAVEG o que falta para refazer a
conformidade SICAR x INCRA (repositório analise_conformidade_sicar-incra) do zero.

Grava no backup (um zip por item, conferido antes de seguir para o próximo):

  Cadastro_Ambiental_Rural\BASE_CAR_ESTADOS_05_2026\<ESTADO>.zip
      SICAR bruto de maio/2026 por estado: os 9 zips por plano, guardados sem
      recompressão (o 2_processar_dados_sicar.py e o 5_extracao_APP_RL_AUR.py leem
      exatamente esta estrutura). Mais o Dicionario_de_Dados_SICAR.pdf solto.
  Cadastro_INCRA\INCRA_SIGEF_SNCI_Brasil_20260610.zip
      Downloads nacionais do SIGEF e do SNCI (Brasil, Privado, Público) de 10/06/2026,
      entrada do 1_processar_dados_incra.py.
  Cadastro_INCRA\INCRA_SIGEF_SNCI_Privado_por_UF.zip
      SIGEF_Privado_<UF> e SNCI_Privado_<UF> (saída do passo 1, lida pelo passo 4).
  Analise_Conformidade_CAR-INCRA\Resultados_Analise_Conformidade\dados_saida_<UF>.zip
      Pasta de trabalho dados_saída_<UF> (GeoPackages e JSONs dos passos 2 a 6), SEM a
      subpasta <UF>_shapefile (temporária, refeita pelo passo 2).
  Analise_Conformidade_CAR-INCRA\Resultados_Analise_Conformidade\Registros_Resultados_Conformidade.zip
      Progressos, heartbeats, scripts temporários e logs da pasta de resultados.
  Analise_Conformidade_CAR-INCRA\Resultados_Analise_Conformidade\Relatorio_Conformidade_Areas_Brasil.xlsx

Opcional (--incluir-nacionais):
  Analise_Conformidade_CAR-INCRA\CAR_Nao_Analisado_Maio2026.zip
      CAR_Nao_Analisado_APP_Maio2026_corrigido, _RL_ e _AUR_ (GeoPackages nacionais,
      ~39 GB) e o CSV dos registros sem geometria. A versão APP não corrigida fica fora.
Opcional (--incluir-shapefile): inclui as subpastas <UF>_shapefile nos zips por UF.

ATENÇÃO - Dropbox "somente online": boa parte do SICAR e do INCRA está só na nuvem.
Ler esses arquivos faz o Dropbox baixá-los para o disco C: (e eles continuam lá depois).
A simulação mostra quanto será baixado e confere o espaço livre no C:. Depois de
concluir, pode clicar com o botão direito nas pastas e escolher "Tornar somente online".

Uso (Python 3 comum, não precisa do env geo; feche QGIS/ArcGIS antes):
  python complementar_backup.py                      # simulação: o que faria, tamanhos, espaço
  python complementar_backup.py --executar           # grava os zips que faltam
  python complementar_backup.py --executar --so sicar incra conformidade
  python complementar_backup.py --executar --verificar-crc   # relê cada zip gravado (mais lento)
Rodar de novo só grava o que falta: um zip que já existe e confere com a origem é pulado.
Ao terminar, regrave o manifesto: python organizar_backup.py --so-manifesto
"""
import argparse
import os
import shutil
import stat
import sys
import time
import zipfile
from pathlib import Path

BACKUP = Path(os.environ.get("PLANAVEG_BACKUP", r"F:\BKP_PLANAVEG"))
SICAR_ESTADOS = Path(r"C:\Users\User\Dropbox\Geoinformation\GEOINFO BRASIL\SICAR\BASE_CAR_ESTADOS_05_2026")
INCRA = Path(r"C:\Users\User\Dropbox\Geoinformation\GEOINFO BRASIL\INCRA")
CONFORMIDADE = Path(r"C:\Users\User\Dropbox\#CONSULTANCY\PLANAVEG\GEODATABASE\Analise_Conformidade_CAR-INCRA")
RESULTADOS = CONFORMIDADE / "Resultados_Analise_Conformidade"

D_SICAR = "Cadastro_Ambiental_Rural/BASE_CAR_ESTADOS_05_2026"
D_INCRA = "Cadastro_INCRA"
D_CONF = "Analise_Conformidade_CAR-INCRA"
D_RES = f"{D_CONF}/Resultados_Analise_Conformidade"
NACIONAIS = ["CAR_Nao_Analisado_APP_Maio2026_corrigido.gpkg", "CAR_Nao_Analisado_RL_Maio2026.gpkg",
             "CAR_Nao_Analisado_AUR_Maio2026.gpkg", "CAR_Nao_Analisado_APP_Maio2026_sem_geometria.csv"]
IGNORAR = {"desktop.ini", "thumbs.db", ".dropbox", ".dropbox.attr"}

# atributos de arquivo do Windows que indicam "só na nuvem" (o conteúdo é baixado ao ler)
_NUVEM = 0x00400000 | 0x00040000 | 0x00001000   # RECALL_ON_DATA_ACCESS | RECALL_ON_OPEN | OFFLINE


def na_nuvem(p):
    try:
        return bool(getattr(os.stat(p), "st_file_attributes", 0) & _NUVEM)
    except OSError:
        return False


def baixar(p, espera=30, max_falhas=40):
    """Força o Dropbox a baixar um arquivo "somente online" lendo-o do início ao fim.
    Arquivos grandes estouram o tempo limite de download do Windows (o erro aparece
    depois de alguns minutos); aqui a leitura é retomada do ponto em que parou, até
    max_falhas tentativas seguidas sem avanço."""
    tam, pos, falhas, ultimo_gb = p.stat().st_size, 0, 0, -1
    while pos < tam:
        try:
            with open(p, "rb") as f:
                f.seek(pos)
                while True:
                    bloco = f.read(64 * 1024 * 1024)
                    if not bloco:
                        break
                    pos += len(bloco)
                    falhas = 0
                    if pos // 1024**3 != ultimo_gb:
                        ultimo_gb = pos // 1024**3
                        print(f"         baixado {pos / 1024**3:5.1f} de {tam / 1024**3:.1f} GB", flush=True)
        except OSError as e:
            falhas += 1
            if falhas > max_falhas:
                raise IOError(f"o Dropbox não entregou {p.name} ({pos / 1024**3:.1f} de "
                              f"{tam / 1024**3:.1f} GB): {e}") from e
            print(f"         Dropbox ainda baixando ({e.__class__.__name__}); nova tentativa em {espera}s "
                  f"[{falhas}/{max_falhas}]", flush=True)
            time.sleep(espera)
        if pos < tam and falhas == 0:   # leitura terminou antes do tamanho esperado
            falhas += 1
            time.sleep(espera)


def arquivos(pasta, excluir_pastas=()):
    """Todos os arquivos sob `pasta`, com o caminho relativo, pulando as subpastas excluídas."""
    out = []
    for raiz, dirs, fs in os.walk(pasta):
        dirs[:] = sorted(d for d in dirs if d not in excluir_pastas and d != "__pycache__")
        for f in sorted(fs):
            if f.lower() not in IGNORAR:
                p = Path(raiz) / f
                out.append((p, p.relative_to(pasta).as_posix()))
    return out


class Tarefa:
    def __init__(self, grupo, destino_rel, itens, comprimir, copia_simples=False):
        self.grupo = grupo
        self.destino_rel = destino_rel     # relativo ao backup (posix)
        self.itens = itens                 # [(origem, nome no zip)]
        self.comprimir = comprimir
        self.copia_simples = copia_simples  # um único arquivo copiado solto (sem zip)

    @property
    def bytes(self):
        return sum(p.stat().st_size for p, _ in self.itens)

    @property
    def bytes_nuvem(self):
        return sum(p.stat().st_size for p, _ in self.itens if na_nuvem(p))


def montar(a):
    t = []
    if "sicar" in a.so:
        if not SICAR_ESTADOS.exists():
            print(f"AVISO: pasta do SICAR por estado não encontrada: {SICAR_ESTADOS}")
        else:
            for est in sorted(d for d in SICAR_ESTADOS.iterdir() if d.is_dir()):
                itens = [(p, f"{est.name}/{rel}") for p, rel in arquivos(est)]
                if itens:
                    t.append(Tarefa("sicar", f"{D_SICAR}/{est.name}.zip", itens, comprimir=False))
            dic = SICAR_ESTADOS.parent / "Dicionario_de_Dados_SICAR.pdf"
            if dic.exists():
                t.append(Tarefa("sicar", f"{D_SICAR}/{dic.name}", [(dic, dic.name)], False, True))
    if "incra" in a.so:
        if not INCRA.exists():
            print(f"AVISO: pasta do INCRA não encontrada: {INCRA}")
        else:
            nac = [(p, f"{sub}/{p.name}") for sub in ("SIGEF", "SNCI")
                   for p in sorted((INCRA / sub).glob("*_20260610.zip"))]
            if nac:
                t.append(Tarefa("incra", f"{D_INCRA}/INCRA_SIGEF_SNCI_Brasil_20260610.zip", nac, comprimir=False))
            por_uf = [(p, p.name) for pref in ("SIGEF_Privado_", "SNCI_Privado_")
                      for p in sorted(INCRA.glob(pref + "*")) if p.is_file()]
            if por_uf:
                t.append(Tarefa("incra", f"{D_INCRA}/INCRA_SIGEF_SNCI_Privado_por_UF.zip", por_uf, comprimir=True))
    if "conformidade" in a.so:
        if not RESULTADOS.exists():
            print(f"AVISO: pasta de resultados da conformidade não encontrada: {RESULTADOS}")
        else:
            for d in sorted(x for x in RESULTADOS.iterdir() if x.is_dir() and x.name.startswith("dados_sa")):
                uf = d.name.split("_")[-1]
                excl = () if a.incluir_shapefile else (f"{uf}_shapefile",)
                itens = [(p, f"{d.name}/{rel}") for p, rel in arquivos(d, excl)]
                if itens:
                    t.append(Tarefa("conformidade", f"{D_RES}/dados_saida_{uf}.zip", itens, comprimir=True))
            soltos = [p for p in sorted(RESULTADOS.iterdir()) if p.is_file() and p.name.lower() not in IGNORAR]
            rel = [p for p in soltos if p.suffix.lower() == ".xlsx"]
            regs = [(p, p.name) for p in soltos if p not in rel]
            for p in rel:
                t.append(Tarefa("conformidade", f"{D_RES}/{p.name}", [(p, p.name)], False, True))
            if regs:
                t.append(Tarefa("conformidade", f"{D_RES}/Registros_Resultados_Conformidade.zip", regs, True))
            qgz = [(p, p.name) for p in sorted(CONFORMIDADE.glob("*.qgz"))]
            if qgz:
                t.append(Tarefa("conformidade", f"{D_CONF}/Projetos_QGIS_Conformidade.zip", qgz, True))
            if a.incluir_nacionais:
                nac = [(CONFORMIDADE / n, n) for n in NACIONAIS if (CONFORMIDADE / n).exists()]
                if nac:
                    t.append(Tarefa("conformidade", f"{D_CONF}/CAR_Nao_Analisado_Maio2026.zip", nac, True))
    return t


def confere(destino, tarefa, crc=False):
    """True se o destino já existe e corresponde à origem (nomes e tamanhos)."""
    if not destino.exists():
        return False
    if tarefa.copia_simples:
        return destino.stat().st_size == tarefa.itens[0][0].stat().st_size
    try:
        with zipfile.ZipFile(destino) as z:
            tam = {i.filename: i.file_size for i in z.infolist() if not i.is_dir()}
            if crc and z.testzip() is not None:
                return False
    except (zipfile.BadZipFile, OSError):
        return False
    return tam == {nome: p.stat().st_size for p, nome in tarefa.itens}


def gravar(tarefa, destino, crc):
    destino.parent.mkdir(parents=True, exist_ok=True)
    temp = destino.with_name(destino.name + ".tmp")
    if temp.exists():
        temp.unlink()
    if tarefa.copia_simples:
        if na_nuvem(tarefa.itens[0][0]):
            baixar(tarefa.itens[0][0])
        shutil.copy2(tarefa.itens[0][0], temp)
    else:
        modo = zipfile.ZIP_DEFLATED if tarefa.comprimir else zipfile.ZIP_STORED
        with zipfile.ZipFile(temp, "w", compression=modo, allowZip64=True, compresslevel=6 if tarefa.comprimir else None) as z:
            for i, (p, nome) in enumerate(tarefa.itens, 1):
                nuvem = na_nuvem(p)
                print(f"      [{i}/{len(tarefa.itens)}] {nome} ({p.stat().st_size / 1024**2:,.1f} MB)"
                      + (" - baixando do Dropbox" if nuvem else ""), flush=True)
                if nuvem:
                    baixar(p)
                z.write(p, nome)
    os.replace(temp, destino)
    if not confere(destino, tarefa, crc):
        destino.unlink()
        raise IOError("o arquivo gravado não confere com a origem; foi apagado")


def main():
    ap = argparse.ArgumentParser(description="Complementa o backup com os insumos da conformidade SICAR x INCRA")
    ap.add_argument("--backup", default=str(BACKUP))
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--so", nargs="+", choices=["sicar", "incra", "conformidade"],
                    default=["sicar", "incra", "conformidade"])
    ap.add_argument("--incluir-nacionais", action="store_true")
    ap.add_argument("--incluir-shapefile", action="store_true")
    ap.add_argument("--verificar-crc", action="store_true")
    a = ap.parse_args()
    backup = Path(a.backup)
    if not backup.exists():
        sys.exit(f"Backup não encontrado: {backup}")

    print("Levantando os arquivos de origem...\n")
    tarefas = montar(a)
    pendentes, feitos = [], 0
    for t in tarefas:
        if confere(backup / t.destino_rel, t):
            feitos += 1
        else:
            pendentes.append(t)

    grupos = {}
    for t in pendentes:
        g = grupos.setdefault(t.grupo, [0, 0, 0])
        g[0] += 1
        g[1] += t.bytes
        g[2] += t.bytes_nuvem
    print(f"{'grupo':14s} {'arquivos':>9s} {'origem (GB)':>12s} {'a baixar (GB)':>14s}")
    for g, (n, b, nv) in sorted(grupos.items()):
        print(f"{g:14s} {n:9d} {b / 1024**3:12.2f} {nv / 1024**3:14.2f}")
    total = sum(t.bytes for t in pendentes)
    nuvem = sum(t.bytes_nuvem for t in pendentes)
    livre_f = shutil.disk_usage(backup).free
    livre_c = shutil.disk_usage(SICAR_ESTADOS.anchor or "C:\\").free
    print(f"\n{len(pendentes)} arquivo(s) a gravar no backup ({total / 1024**3:.1f} GB de origem, no máximo);"
          f" {feitos} já estão no backup e conferem.")
    print(f"Espaço livre: backup {livre_f / 1024**3:.1f} GB | C: {livre_c / 1024**3:.1f} GB"
          f" | o Dropbox vai baixar {nuvem / 1024**3:.1f} GB para o C:")
    for t in pendentes:
        print(f"   {t.destino_rel}  ({len(t.itens)} arquivo(s), {t.bytes / 1024**3:.2f} GB"
              + (f", {t.bytes_nuvem / 1024**3:.2f} GB na nuvem)" if t.bytes_nuvem else ")"))
    if not a.executar:
        print("\nSIMULAÇÃO: nada foi gravado. Rode com --executar para gravar.")
        return
    if livre_f < total * 1.02:
        sys.exit("Espaço insuficiente no disco do backup.")

    t0, ok, falhas = time.time(), 0, []
    for k, t in enumerate(pendentes, 1):
        precisa_c = t.bytes_nuvem * 1.05
        if precisa_c and shutil.disk_usage(SICAR_ESTADOS.anchor or "C:\\").free < precisa_c:
            print(f"\nParou antes de {t.destino_rel}: o C: não tem espaço para o Dropbox baixar "
                  f"{t.bytes_nuvem / 1024**3:.1f} GB. Torne 'somente online' as pastas já copiadas "
                  "e rode de novo (o que já foi gravado é pulado).")
            break
        print(f"[{time.time() - t0:7.0f}s] ({k}/{len(pendentes)}) {t.destino_rel}", flush=True)
        try:
            gravar(t, backup / t.destino_rel, a.verificar_crc)
            ok += 1
        except Exception as e:  # noqa: BLE001 - registra e segue para o próximo
            falhas.append((t.destino_rel, e))
            print(f"   FALHOU: {e}")
    print(f"\n{ok} gravado(s), {len(falhas)} falha(s) em {(time.time() - t0) / 60:.0f} min.")
    for d, e in falhas:
        print(f"   {d}: {e}")
    print("\nPróximo passo: python organizar_backup.py --so-manifesto")


if __name__ == "__main__":
    main()
