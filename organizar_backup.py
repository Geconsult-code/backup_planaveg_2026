r"""
organizar_backup.py - organiza o F:\BKP_PLANAVEG e gera o _manifesto_backup.csv

O backup é a estrutura de REFERÊNCIA do projeto (decisão de 13/10/2026). O manifesto
registra, para cada pasta, arquivo e conteúdo de zip do backup:
  - grupo e etapa do processamento;
  - repositório e script que PRODUZ o dado, e scripts que o CONSOMEM;
  - o caminho que o código usa HOJE (para restaurar, ou para adaptar os scripts);
  - se o item é necessário para reprocessar alguma etapa.

Ações (só com --executar; sem ele, apenas simula e mostra o plano):
  1. Junta logs e registros soltos (_log*.txt, _progresso*.json, heartbeat_*.txt,
     _manifesto_quarentena.csv) e o Registros_Processamento.zip do Dropbox em
     _Registros_Processamento.zip, na raiz do backup. Confere o zip antes de apagar
     os originais.
  2. Apaga os marcadores _done_*.txt (só serviam para a retomada dos scripts).
  3. Apaga os Planaveg_2025_*_com_area.zip (Area_ha recalculado; o reporte 2025
     entregue são os arquivos sem sufixo).
  4. Grava o _manifesto_backup.csv (lista também o que está só no Dropbox).

A coluna destino_relativo diz onde cada item é restaurado (ver restaurar_backup.py, no
repositório backup_planaveg_2026, onde este script é mantido).

Uso (Python 3 comum, não precisa do env geo):
  python organizar_backup.py                 # simulação
  python organizar_backup.py --executar      # aplica as ações e grava o manifesto
  python organizar_backup.py --so-manifesto  # só regrava o manifesto (após mudanças)
  python organizar_backup.py --verificar-crc # idem + confere o CRC de todos os zips (lento, lê ~90 GB)
"""
import argparse
import csv
import fnmatch
import os
import re
import sys
import time
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

BACKUP = Path(os.environ.get("PLANAVEG_BACKUP", r"F:\BKP_PLANAVEG"))
DROPBOX = Path(r"C:\Users\User\Dropbox\#CONSULTANCY\PLANAVEG\GEODATABASE\GEOPACKAGE")
G = r"C:\Users\User\Dropbox\#CONSULTANCY\PLANAVEG\GEODATABASE\GEOPACKAGE"   # raiz usada no código hoje
SICAR_BRUTO = r"C:\Users\User\Dropbox\Geoinformation\GEOINFO BRASIL\SICAR\BASE_CAR_ESTADOS_05_2026"

MANIFESTO = "_manifesto_backup.csv"
REGISTROS = "_Registros_Processamento.zip"
PADROES_LOG = ["_log*.txt", "_progresso*.json", "heartbeat_*.txt", "_manifesto_quarentena.csv"]
PADROES_DESCARTE = ["_done_*.txt"]
DESCARTAR = [
    "Computo_Planaveg_2025/Planaveg_2025_Projetos_ORR_com_area.zip",
    "Computo_Planaveg_2025/Planaveg_2025_Projetos_Outros_com_area.zip",
    "Computo_Planaveg_2025/Planaveg_2025_Projetos_Recooperar_com_area.zip",
]
# pasta do backup -> pasta de trabalho equivalente (para itens que o código não lê diretamente)
PASTA_TRABALHO = {
    "Dados_originais_Planaveg_2026": "",
    "Vegetacao_Secundaria": "Vegetacao_Secundaria_INPE",
    "Cruzamento_Espacial": "Cruzamento_Espacial_Vegetacao_Secundaria",
    "Computo_Planaveg_2026/Hierarquia": "Computo_Planaveg_2026",
    "Cadastro_Ambiental_Rural": "_SICAR_bruto",
    "Cadastro_Ambiental_Rural_UF": "CAR_Maio2026_Imoveis_Selecionados",
}
IGNORAR = {"desktop.ini", "thumbs.db", MANIFESTO.lower(), "organizar_backup.py"}

R_CONF = "analise_conformidade_sicar-incra"
R_VS = "cruzamento_vegetacao-secundaria"
R_COMP = "computo_hierarquia-planaveg"
R_VIZ = "visualizacao_categoria-fundiaria"

# ---------------------------------------------------------------------------
# Insumos originais (Dados_originais_Planaveg_2026): arquivo -> (descrição, consumidores)
# ---------------------------------------------------------------------------
ORIGINAIS = {
    "Assentamentos_Rurais_INCRA20260610.gpkg": ("Assentamentos INCRA", f"{R_VIZ} (flag AS_)"),
    "Territorios_Quilombolas_INCRA20260610.gpkg": ("Territórios quilombolas INCRA", f"{R_VIZ} (flag QL)"),
    "CAR_Junho26_Regularizacao_Ambiental.gpkg": ("SICAR em regularização ambiental (AC, MT, PB, RJ, SP)",
                                                 f"{R_COMP}: 1_preparar_insumos.py (classe 3)"),
    "IBAMA_Areas_Embargadas_PANGIA20260920_Poligonos.gpkg": ("Embargos PANGIA 2026 só polígonos",
        f"{R_COMP}: 1_preparar_insumos.py (classe 4); {R_VS}: cruzar_embargos_vegsec.py"),
    "IBAMA_Areas_Embargadas_PANGIA20251023_Poligonos.gpkg": ("Embargos PANGIA 2025 só polígonos",
        f"{R_VS}: cruzar_embargos_vegsec.py"),
    "IBAMA_Areas_Embargadas_PANGIA20260920.gpkg": ("Embargos PANGIA 2026 bruto (com pontos e registros sem geometria)",
                                                   "origem do arquivo _Poligonos"),
    "IBAMA_Areas_Embargadas_PANGIA20251023.gpkg": ("Embargos PANGIA 2025 bruto", "origem do arquivo _Poligonos"),
    "IBAMA_Projetos_Recooperar_2025_com_area.gpkg": ("Recooperar 2025 com área",
        f"{R_VS}: cruzar_projetos_vegsec*.py, incorporar_vegsec_projetos.py"),
    "IBAMA_Projetos_Recooperar_2026_com_area.gpkg": ("Recooperar 2026 com área",
        f"{R_VS}: cruzar_projetos_vegsec*.py, incorporar_vegsec_projetos.py"),
    "ICMBio_Projetos_GEF_Terrestre_2026_com_area.gpkg": ("ICMBio GEF Terrestre com área",
        f"{R_VS}: cruzar_projetos_vegsec*.py, incorporar_vegsec_projetos.py"),
    "ICMBio_Projetos_Restauracao_2026_com_area.gpkg": ("ICMBio Restauração com área",
        f"{R_VS}: cruzar_projetos_vegsec*.py, incorporar_vegsec_projetos.py"),
    "IBAMA_Projetos_Recooperar_2025.gpkg": ("Recooperar 2025 padronizado", "origem da versão _com_area"),
    "IBAMA_Projetos_Recooperar_2026.gpkg": ("Recooperar 2026 padronizado", "origem da versão _com_area"),
    "ICMBio_Projetos_GEF_Terrestre_2026.gpkg": ("ICMBio GEF Terrestre padronizado", "origem da versão _com_area"),
    "ICMBio_Projetos_Restauracao_2026.gpkg": ("ICMBio Restauração padronizado", "origem da versão _com_area"),
    "IBGE_Limite_Estados.gpkg": ("Limites estaduais IBGE 2025", f"{R_COMP} (UF); {R_VIZ}"),
    "IBGE_Limite_Biomas.gpkg": ("Biomas IBGE 1:250.000", f"{R_COMP} (bioma)"),
    "IBGE_Limite_Municipios.gpkg": ("Municípios IBGE (malha 2020)", f"{R_VIZ}: Municipio"),
    "IBGE_Divisao_Hidrografica.gpkg": ("Divisão hidrográfica IBGE (micro/meso/macro RH)", f"{R_VIZ}: Bacia"),
    "ORR_Observatorio_Restauracao_2026.gpkg": ("Observatório da Restauração 2026",
        f"{R_COMP}: 1_preparar_insumos.py (classe 5)"),
    "ORR_Observatorio_Restauracao_2025.gpkg": ("Observatório da Restauração 2025",
        "substituído pelo ORR 2026 no cômputo (histórico)"),
    "Pro-Manguezal_IBAMA20260508.gpkg": ("Pró-Manguezal IBAMA",
        f"{R_COMP} (classe 8); {R_VS}: cruzar_projetos_vegsec_qualificado*.py; {R_VIZ} (flag Manguezal)"),
    "Projetos_Restauracao_ICMBio20260727.gpkg": ("Download original ICMBio", "origem dos arquivos ICMBio padronizados"),
    "Projetos_Restauracao_ORR2025.gpkg": ("Download original ORR 2025", "origem do ORR_Observatorio_Restauracao_2025"),
    "Projetos_Restauracao_Recooperar20251113.gpkg": ("Download original Recooperar", "origem dos arquivos Recooperar padronizados"),
    "SIGEF_Publico_em_APA.gpkg": ("Imóveis públicos SIGEF dentro de APA", f"{R_COMP}: classe 7 (área pública das APAs)"),
    "Terras_Indigenas_FUNAI20260507.gpkg": ("Terras Indígenas FUNAI",
        f"{R_COMP} (classe 6); {R_VS}: cruzar_projetos_vegsec*.py; {R_VIZ} (flag TI)"),
    "Unidades_Conservacao_CNUC20260507.gpkg": ("Unidades de Conservação CNUC",
        f"{R_COMP} (classe 7); {R_VS}: cruzar_projetos_vegsec*.py; {R_VIZ} (UC/APA/RPPN)"),
}

TIER_PRODUTOR = {1: "2_camada2_projetos.py", 3: "2_camada2_projetos.py", 4: "2_camada2_projetos.py",
                 5: "2_camada2_projetos.py", 6: "3_camada1_vs_governanca.py", 7: "3_camada1_vs_governanca.py",
                 8: "3_camada1_vs_governanca.py", 9: "3b_camada1_car.py", 10: "3b_camada1_car.py",
                 11: "3b_camada1_car.py"}
TIER_VIZ = {1, 3, 4, 5, 9, 10, 11}   # classes cujas saídas P1/P2 são lidas pela visualização


def info(grupo, etapa="", repositorio="", produtor="", consumidores="", codigo="", essencial="", obs=""):
    if not essencial:
        essencial = {"Relatório": "não - registro", "Registro": "não - registro",
                     "Produto final (referência)": "não - referência",
                     "Script (cópia)": "não - cópia"}.get(grupo, "")
    return dict(grupo=grupo, etapa=etapa, repositorio=repositorio, script_produtor=produtor,
                scripts_consumidores=consumidores, caminho_no_codigo=codigo,
                necessario_reprocessar=essencial, observacao=obs)


def classificar(rel):
    """rel: caminho relativo ao backup (posix). Devolve o dicionário de anotação."""
    p = rel.lower()
    nome = PurePosixPath(rel).name
    stem = nome[:-4] if nome.lower().endswith(".zip") else nome
    m = re.match(r"computo_planaveg_2026/hierarquia/(tier(\d+)_[^/]+)/", p)

    if p == REGISTROS.lower():
        return info("Registro", "Todas", obs="Logs, progressos e manifesto da quarentena; caminhos internos = caminho de origem")
    if p.startswith("dados_originais_planaveg_2026/"):
        desc, cons = ORIGINAIS.get(nome, ("Insumo original", ""))
        uso = "sim" if any(r in cons for r in (R_COMP, R_VS, R_VIZ)) else "não - referência"
        return info("Dado original", "Insumos", "", "fonte externa", cons, rf"{G}\{nome}", uso, desc)
    if p.startswith("analise_territorial_car-incra_dissolvido/"):
        if p.endswith(".xlsx"):
            return info("Relatório", "Análise territorial CAR x INCRA", obs="Planilha de áreas/métricas")
        cons = {
            "CAR_Brasil_Maio26_Habilitado_Planaveg_dissolvido_UF": f"{R_VIZ} (CAR_Habilitado)",
            "CAR_Brasil_Maio26_Selecionado_Analisado_dissolvido_UF": f"{R_VIZ} (CAR_Analisado)",
            "CAR_Brasil_Maio26_Selecionado_Não_Analisado_dissolvido_UF": f"{R_VIZ} (CAR_Nao_Analisado)",
            "CAR_Brasil_Maio2026_Imovel_Area_Total_dissolvido_UF": f"{R_COMP}: 1_preparar_insumos.py (área privada das APAs)",
        }.get(stem, "")
        return info("Produto intermediário", "Análise territorial CAR x INCRA", "",
                    "dissolver_car_total.py (fora dos repositórios)", cons,
                    rf"{G}\Analise_Territorial_CAR-INCRA_dissolvido\{stem}.gpkg",
                    "sim" if cons else "não - referência",
                    "" if cons else "Não é lido pelos scripts (comparação/versão alternativa)")
    if p.startswith("cadastro_ambiental_rural/"):
        if "20260501" in p:
            return info("Dado original", "SICAR bruto maio/2026", R_CONF, "download SICAR",
                        f"{R_CONF}: 2_processar_dados_sicar.py, 5_extracao_APP_RL_AUR.py",
                        rf"{SICAR_BRUTO}\<ESTADO>\ (um .zip por plano)", "sim",
                        "O código lê a pasta por estado; o backup guarda o GeoPackage nacional")
        return info("Dado original", "SICAR bruto junho/2026", "", "download SICAR",
                    "origem do CAR_Junho26_Regularizacao_Ambiental e do CAR Habilitado Junho26",
                    "", "não - referência")
    if p.startswith("cadastro_ambiental_rural_uf/imoveis_selecionados"):
        return info("Produto intermediário", "Conformidade SICAR x INCRA (imóveis selecionados por UF)", R_CONF,
                    f"{R_CONF}: 3_categorizar_dados_sicar.py, 4_analise_conformidade.py, 5_extracao_APP_RL_AUR.py; "
                    f"{R_VS}: 0_incorporar_app_rl_aur_analisados.py",
                    f"{R_COMP}: 3b_camada1_car.py; {R_VS}: 1_processar_dados_VS_*.py, 2_cruzamento_espacial_VS_*.py",
                    rf"{G}\CAR_Maio2026_Imoveis_Selecionados\<UF>_CAR_Imoveis_Selecionados_<categoria>.gpkg", "sim",
                    r"Scripts do cruzamento VS ainda apontam para GEOPACKAGE\Cadastro Ambiental Rural_Maio2026")
    if p.startswith("computo_planaveg_2025/"):
        return info("Produto final (referência)", "Cômputo Planaveg 2025", obs="Reporte 2025 entregue; não é lido pelos scripts")
    if p.startswith("computo_planaveg_2026/insumos/"):
        return info("Produto intermediário", "Cômputo 2026 - passo 1", R_COMP, "1_preparar_insumos.py",
                    "2_camada2_projetos.py, 3_camada1_vs_governanca.py",
                    rf"{G}\Computo_Planaveg_2026\Insumos\ ", "sim")
    if m:
        pasta, n = m.group(1), int(m.group(2))
        pasta = rel.split("/")[2]
        cons = "classes seguintes; gerar_geopackages_finais.py"
        if n in TIER_VIZ:
            cons += f"; {R_VIZ}: 2_fragmentar_e_atribuir.py"
        if p.endswith("_por_uf.zip"):
            return info("Produto intermediário", f"Cômputo 2026 - classe {n} (por UF)", R_COMP, TIER_PRODUTOR.get(n, ""),
                        "gerar_geopackages_finais.py; 3b_camada1_car.py --consolidar",
                        rf"{G}\Computo_Planaveg_2026\{pasta}\_por_uf\ ", "sim",
                        "ESSENCIAL: o reporte final de APP/AUR/RL é montado a partir destes arquivos por UF")
        return info("Produto intermediário", f"Cômputo 2026 - classe {n}", R_COMP, TIER_PRODUTOR.get(n, ""), cons,
                    rf"{G}\Computo_Planaveg_2026\{pasta}\ ", "sim")
    if p.startswith("computo_planaveg_2026/hierarquia/") and p.endswith(".xlsx"):
        return info("Relatório", "Cômputo 2026 - validação", R_COMP, obs="Resumo da validação feita em nuvem")
    if p.startswith("computo_planaveg_2026/reporte_final/"):
        total = stem == "Planaveg_2026_Total"
        return info("Produto final", "Cômputo 2026 - reporte", R_COMP, "gerar_geopackages_finais.py",
                    f"{R_VIZ}: 1_checar_fontes.py, 2_fragmentar_e_atribuir.py" if total else "",
                    rf"{G}\Computo_Planaveg_2026\Reporte_Final\{stem}.gpkg",
                    "sim" if total else "não - produto final")
    if p.startswith("computo_planaveg_2026/visualizacao/"):
        if "logs" in p:
            return info("Registro", "Visualização - validação", R_VIZ, "1_checar_fontes.py ... 4_consolidar_brasil.py", "",
                        rf"{G}\Computo_Planaveg_2026\Visualizacao\_logs\ ", "não - registro")
        if "_uf_" in p:
            return info("Produto intermediário", "Visualização - por UF", R_VIZ, "2_fragmentar_e_atribuir.py",
                        "3_validar.py, 4_consolidar_brasil.py",
                        rf"{G}\Computo_Planaveg_2026\Visualizacao\_por_uf\ ", "não - pode ser refeito")
        return info("Produto final", "Visualização - Brasil", R_VIZ, "4_consolidar_brasil.py", "",
                    rf"{G}\Computo_Planaveg_2026\Visualizacao\Planaveg_2026_Categorias_Visualizacao.gpkg",
                    "não - produto final")
    if p.startswith("cruzamento_espacial/"):
        cz = rf"{G}\Cruzamento_Espacial_Vegetacao_Secundaria"
        if stem == "VS-Areas_Embargadas":
            return info("Produto intermediário", "Cruzamento VS x embargos PANGIA", R_VS, "cruzar_embargos_vegsec.py",
                        f"{R_COMP}: 1_preparar_insumos.py (classe 4)", rf"{cz}\VS-Areas_Embargadas\ ", "sim")
        if stem == "VS-Cadastro_Ambiental_Rural":
            return info("Produto intermediário", "Cruzamento VS x APP/AUR/RL dos imóveis selecionados", R_VS,
                        "2_cruzamento_espacial_VS_qualificado.py, 2_cruzamento_espacial_VS_2024.py (e 2_cruzamento_espacial_VS.py, não qualificado)",
                        f"{R_COMP}: 3b_camada1_car.py", rf"{cz}\VS-Cadastro_Ambiental_Rural\ ", "sim",
                        r"Os scripts 2_* gravam em GEOPACKAGE\Cruzamento CAR Vegetacao Secundaria")
        if stem == "VS-Cadastro_Ambiental_Rural_UF":
            return info("Produto intermediário", "VS qualificada recortada por UF", R_VS,
                        "1_processar_dados_VS_qualificada.py, 1_processar_dados_VS_2024_qualificada.py",
                        "2_cruzamento_espacial_VS_qualificado.py, 2_cruzamento_espacial_VS_2024.py",
                        rf"{G}\CAR_Maio2026_Imoveis_Selecionados\_veg_qualificada_uf\ e \_veg_2024_qualificada_uf\ ",
                        "não - pode ser refeito", "Evita recortar a VS de novo ao refazer o cruzamento")
        if stem == "VS-Cadastro_Ambiental_Rural_validacao":
            return info("Registro", "Validação em nuvem do cruzamento VS x CAR", R_VS, "", "", "", "não - registro",
                        "Amostra usada para validar o cruzamento VS x APP/AUR/RL (não é lida pelos scripts)")
        if stem in ("VS-Pro_Manguezal", "VS-Terras_Indigenas", "VS-Unidades_Conservacao", "VS-Projetos_Restauracao"):
            cons = (f"{R_VS}: incorporar_vegsec_projetos.py; {R_COMP}: 1_preparar_insumos.py (Recooperar)"
                    if stem == "VS-Projetos_Restauracao" else f"{R_COMP}: 1_preparar_insumos.py (classes 6 a 8)")
            return info("Produto intermediário", f"Cruzamento VS x {stem[3:]}", R_VS,
                        "cruzar_projetos_vegsec_qualificado.py, cruzar_projetos_vegsec_qualificado_2022_2024.py",
                        cons, rf"{cz}\{stem}\ ", "sim",
                        r"Os scripts gravam em GEOPACKAGE\Cruzamento_Projetos_VegSec")
        if stem == "Projetos_com_Vegetacao_Secundaria":
            return info("Produto intermediário", "Projetos com atributos de VS", R_VS, "incorporar_vegsec_projetos.py",
                        f"{R_COMP}: 1_preparar_insumos.py (Recooperar 2026)", rf"{G}\Projetos_com_VegSec\ ", "sim",
                        r"No Dropbox reduzido a pasta se chama Vegetacao_Secundaria_Projetos")
        if nome.lower().startswith("resumo_areas_uc"):
            return info("Relatório", "Cruzamento VS x UC", R_VS, "agregar_areas_uc*.py", "", "", "não - registro")
        return info("Relatório", "Cruzamentos espaciais", obs="Planilha de análise")
    if p.startswith("vegetacao_secundaria/"):
        if p.endswith(".py"):
            return info("Script (cópia)", "Vegetação secundária", R_VS, obs="Cópia de script que já está no repositório")
        if p.endswith((".csv", ".xlsx")):
            return info("Relatório", "Vegetação secundária", R_VS, "analisar_vegsec_*.py", obs="Resumo de áreas/polígonos")
        qualif = "qualificada" in p
        cons = (f"{R_COMP} (VS_VERSOES); {R_VS}: 1_processar_dados_VS_*qualificada.py, cruzar_*_qualificado*.py, cruzar_embargos_vegsec.py"
                if qualif else f"{R_VS}: analisar_vegsec_*.py (comparação bruto x qualificado)")
        return info("Dado original", "Vegetação secundária INPE", "", "INPE (TerraBrasilis / TerraClass)", cons,
                    rf"{G}\Vegetacao_Secundaria_INPE\{stem}.gpkg", "sim" if qualif else "não - referência",
                    r"Scripts do cruzamento VS usam GEOPACKAGE\INPE_Vegetacao_Secundaria" if qualif else "VS sem qualificação")
    return info("Não classificado", obs="Revisar")


def membro_codigo(base, membro):
    """Caminho no código de um arquivo dentro de um zip: pasta do zip + nome do arquivo."""
    base = base.strip()
    if not base or base.endswith(".gpkg"):
        return base
    return base.rstrip("\\ ") + "\\" + PurePosixPath(membro).name


def destino_rel(rel, codigo, grupo, membro=None):
    """Caminho relativo à raiz dos dados (pasta GEOPACKAGE) onde o item deve ser restaurado.
    Vazio = não é restaurado (zip cujo conteúdo é restaurado item a item, cópia de script, pasta)."""
    nome = PurePosixPath(membro).name if membro else PurePosixPath(rel).name
    if grupo in ("Pasta", "Script (cópia)", "Não está no backup"):
        return ""
    if rel.lower() == REGISTROS.lower():
        return "" if membro else REGISTROS            # o zip de registros é copiado inteiro, sem extrair
    if not membro and rel.lower().endswith(".zip"):
        return ""                                    # restaura-se o conteúdo do zip
    codigo = codigo.strip()
    if codigo.startswith(G):
        r = codigo[len(G):].strip("\\ ")
        if "<" in r or (membro and codigo.endswith("\\")):
            r = str(PureWindowsPath(r) / nome) if not "<" in r else str(PureWindowsPath(r).parent / nome)
        return r
    if codigo.startswith(SICAR_BRUTO):
        return "_SICAR_bruto\\" + nome                 # o código lê pastas por estado: conversão manual
    # sem caminho no código: pasta do backup traduzida para a pasta de trabalho equivalente
    partes = rel.split("/")[:-1]
    chave = "/".join(partes[:2]) if partes[:2] == ["Computo_Planaveg_2026", "Hierarquia"] else (partes[0] if partes else "")
    if chave in PASTA_TRABALHO:
        partes = [x for x in PASTA_TRABALHO[chave].split("/") if x] + partes[len(chave.split("/")):]
    return str(PureWindowsPath(*partes, nome)) if partes else nome


def mtime(p):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))


def casa(nome, padroes):
    return any(fnmatch.fnmatch(nome.lower(), x.lower()) for x in padroes)


# ---------------------------------------------------------------------------
# 1-3. Consolidação de logs e descartes
# ---------------------------------------------------------------------------
def planejar(backup):
    logs, descartes = [], []
    for p in sorted(backup.rglob("*")):
        if not p.is_file() or p.name.lower() in IGNORAR or p.name == REGISTROS:
            continue
        if casa(p.name, PADROES_DESCARTE):
            descartes.append(p)
        elif casa(p.name, PADROES_LOG):
            logs.append(p)
    descartes += [backup / d for d in DESCARTAR if (backup / d).exists()]
    return logs, descartes


def consolidar(backup, logs, dropbox_zip):
    destino = backup / REGISTROS
    temp = destino.with_suffix(".zip.tmp")
    if temp.exists():
        temp.unlink()
    vistos = {}
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        if destino.exists():                       # rodada anterior: preserva o que já estava no zip
            with zipfile.ZipFile(destino) as antigo:
                for i in antigo.infolist():
                    z.writestr(i, antigo.read(i.filename))
                    vistos[(PurePosixPath(i.filename).name.lower(), i.file_size)] = True
        for p in logs:
            nome = p.relative_to(backup).as_posix()
            if (p.name.lower(), p.stat().st_size) not in vistos:
                z.write(p, nome)
                vistos[(p.name.lower(), p.stat().st_size)] = True
        if dropbox_zip and dropbox_zip.exists():
            with zipfile.ZipFile(dropbox_zip) as dz:
                for i in dz.infolist():
                    chave = (PurePosixPath(i.filename).name.lower(), i.file_size)
                    if i.is_dir() or chave in vistos:
                        continue
                    z.writestr("Dropbox_GEOPACKAGE_2026-10-02/" + i.filename, dz.read(i.filename))
                    vistos[chave] = True
    with zipfile.ZipFile(temp) as z:
        erro = z.testzip()
        nomes = {PurePosixPath(n).name.lower() for n in z.namelist()}
    faltam = [p for p in logs if p.name.lower() not in nomes]
    if erro or faltam:
        temp.unlink()
        raise SystemExit(f"Zip de registros não confere (erro={erro}, faltam={len(faltam)}). Nada foi apagado.")
    os.replace(temp, destino)
    return destino


# ---------------------------------------------------------------------------
# 4. Manifesto
# ---------------------------------------------------------------------------
def gerar_manifesto(backup, dropbox, verificar_crc):
    linhas, nomes_backup = [], set()
    for p in sorted(backup.rglob("*")):
        if p.name.lower() in IGNORAR or p.suffix.lower() == ".tmp":
            continue
        rel = p.relative_to(backup).as_posix()
        if p.is_dir():
            linhas.append(dict(caminho_backup=str(p), nivel="pasta", arquivo=p.name, tamanho_MB="",
                               modificado="", **info("Pasta"), destino_relativo=""))
            continue
        a = classificar(rel)
        nomes_backup.add(p.name.lower())
        nomes_backup.add(p.stem.lower())
        linhas.append(dict(caminho_backup=str(p), nivel="arquivo", arquivo=p.name,
                           tamanho_MB=round(p.stat().st_size / 1024**2, 2), modificado=mtime(p), **a,
                           destino_relativo=destino_rel(rel, a["caminho_no_codigo"], a["grupo"])))
        if p.suffix.lower() != ".zip":
            continue
        try:
            with zipfile.ZipFile(p) as z:
                if verificar_crc:
                    ruim = z.testzip()
                    if ruim:
                        linhas[-1]["observacao"] += f" | CRC ruim em {ruim}"
                    else:
                        linhas[-1]["observacao"] += " | CRC ok"
                for i in z.infolist():
                    if i.is_dir():
                        continue
                    nomes_backup.add(PurePosixPath(i.filename).name.lower())
                    b = dict(a)
                    if a["grupo"] != "Registro":
                        base = a["caminho_no_codigo"]
                        if p.stem == "VS-Cadastro_Ambiental_Rural_UF":   # zips aninhados, um por versão da VS
                            sub = "_veg_2024_qualificada_uf" if "2024" in i.filename else "_veg_qualificada_uf"
                            base = rf"{G}\CAR_Maio2026_Imoveis_Selecionados\{sub}\ "
                            if i.filename.lower().endswith(".zip"):
                                b["observacao"] = "Zip aninhado: os GeoPackages por UF estão dentro dele"
                        b["caminho_no_codigo"] = membro_codigo(base, i.filename)
                    linhas.append(dict(caminho_backup=f"{p}::{i.filename}", nivel="conteudo_zip",
                                       arquivo=PurePosixPath(i.filename).name,
                                       tamanho_MB=round(i.file_size / 1024**2, 2),
                                       modificado="%04d-%02d-%02d %02d:%02d" % i.date_time[:5], **b,
                                       destino_relativo=destino_rel(rel, b["caminho_no_codigo"], b["grupo"],
                                                                    i.filename)))
        except (zipfile.BadZipFile, OSError) as e:
            linhas[-1]["observacao"] += f" | NÃO FOI POSSÍVEL LISTAR O ZIP: {e}"

    so_dropbox = []
    if dropbox.exists():
        for p in sorted(dropbox.rglob("*")):
            if not p.is_file() or p.name.lower() in IGNORAR or p.name == "Registros_Processamento.zip":
                continue
            if p.name.lower() in nomes_backup or p.stem.lower() in nomes_backup:
                continue
            so_dropbox.append(p)
            linhas.append(dict(caminho_backup="", nivel="somente_dropbox", arquivo=p.name,
                               tamanho_MB=round(p.stat().st_size / 1024**2, 2), modificado=mtime(p),
                               **info("Não está no backup", obs=f"Só existe em {p}"), destino_relativo=""))

    with open(backup / MANIFESTO, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    return linhas, so_dropbox


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--so-manifesto", action="store_true")
    ap.add_argument("--verificar-crc", action="store_true")
    ap.add_argument("--backup", default=str(BACKUP))
    ap.add_argument("--dropbox", default=str(DROPBOX))
    a = ap.parse_args()
    backup, dropbox = Path(a.backup), Path(a.dropbox)
    if not backup.exists():
        raise SystemExit(f"Backup não encontrado: {backup}")

    if not (a.so_manifesto or a.verificar_crc):
        logs, descartes = planejar(backup)
        dz = dropbox / "Registros_Processamento.zip"
        print(f"Backup: {backup}\n")
        print(f"1. Para {REGISTROS}: {len(logs)} arquivos"
              + (f" + conteúdo de {dz.name} do Dropbox" if dz.exists() else ""))
        for p in logs:
            print(f"     {p.relative_to(backup)}")
        print(f"2-3. Apagar: {len(descartes)} arquivos")
        for p in descartes:
            print(f"     {p.relative_to(backup)}  ({p.stat().st_size / 1024**2:.1f} MB)")
        if not a.executar:
            print("\nSIMULAÇÃO: nada foi alterado. Rode com --executar para aplicar e gravar o manifesto.")
            return
        consolidar(backup, logs, dz)
        for p in logs + descartes:
            p.unlink()
        print(f"\n{REGISTROS} conferido; {len(logs) + len(descartes)} arquivos apagados.")

    print("\nGerando o manifesto (lê o índice de todos os zips; pode levar alguns minutos)...")
    linhas, so_dropbox = gerar_manifesto(backup, dropbox, a.verificar_crc)
    resumo = {}
    for l in linhas:
        if l["nivel"] == "arquivo":
            g = resumo.setdefault(l["grupo"], [0, 0.0])
            g[0] += 1
            g[1] += float(l["tamanho_MB"] or 0)
    print(f"\n{MANIFESTO}: {len(linhas):,} linhas")
    for g, (n, mb) in sorted(resumo.items()):
        print(f"   {g:28s} {n:4d} arquivos  {mb / 1024:8.2f} GB")
    problemas = [l for l in linhas if "NÃO FOI POSSÍVEL" in l["observacao"] or "CRC ruim" in l["observacao"]]
    for l in problemas:
        print(f"   ATENÇÃO: {l['arquivo']}: {l['observacao']}")
    if so_dropbox:
        print(f"\n{len(so_dropbox)} arquivo(s) só no Dropbox (não estão no backup):")
        for p in so_dropbox:
            print(f"   {p}")


if __name__ == "__main__":
    main()
