# backup_planaveg_2026

Instruções e scripts para **restaurar o backup de dados do Planaveg 2026** e apontar os
scripts de processamento para a pasta restaurada, em qualquer computador ou caminho.

O backup guarda os dados de entrada, os intermediários e os produtos finais dos quatro
repositórios de processamento:

| # | Repositório | O que produz |
|---|---|---|
| 1 | [analise_conformidade_sicar-incra](https://github.com/Geconsult-code/analise_conformidade_sicar-incra) | Imóveis do CAR selecionados (Habilitados, Analisados, Não Analisados) e APP/RL/AUR |
| 2 | [cruzamento_vegetacao-secundaria](https://github.com/Geconsult-code/cruzamento_vegetacao-secundaria) | Cruzamentos da vegetação secundária (VS) com CAR, TI, UC, manguezais, projetos e embargos |
| 3 | [computo_hierarquia-planaveg](https://github.com/Geconsult-code/computo_hierarquia-planaveg) | Cômputo 2026 pela hierarquia de sobreposições (`Reporte_Final`) |
| 4 | [visualizacao_categoria-fundiaria](https://github.com/Geconsult-code/visualizacao_categoria-fundiaria) | Cômputo fragmentado com atributos de filtro (`Visualizacao`) |

## Conteúdo deste repositório

| Arquivo | Função |
|---|---|
| `restaurar_backup.py` | Restaura o backup na estrutura de pastas que os scripts esperam, numa pasta à escolha |
| `organizar_backup.py` | Mantém o backup: consolida registros e gera o `_manifesto_backup.csv` |
| `manifesto/_manifesto_backup.csv` | Cópia do manifesto (o original fica na raiz do backup) |

Os scripts usam só a biblioteca padrão do Python (3.10 ou mais recente); não precisam do
ambiente `geo`.

## Organização do backup

Backup de referência: `F:\BKP_PLANAVEG` (cerca de 113 GB compactados, em outubro/2026).
Quase tudo está em `.zip`; cada zip guarda os arquivos de uma pasta de trabalho.

| Pasta do backup | Conteúdo | Pasta de trabalho (após restaurar) |
|---|---|---|
| `Dados_originais_Planaveg_2026` | Insumos: IBGE, CNUC, FUNAI, INCRA, Recooperar, ICMBio, ORR, Pró-Manguezal, PANGIA, CAR regularização, SIGEF público em APA | raiz |
| `Vegetacao_Secundaria` | VS 2022 (Brasil) e VS 2024 (Amazônia, Cerrado), bruta e qualificada | `Vegetacao_Secundaria_INPE` |
| `Cadastro_Ambiental_Rural` | SICAR bruto nacional (maio e junho/2026) | `_SICAR_bruto` (ver limitações) |
| `Cadastro_Ambiental_Rural_UF` | Imóveis selecionados por UF e categoria, com APP/RL/AUR | `CAR_Maio2026_Imoveis_Selecionados` |
| `Analise_Territorial_CAR-INCRA_dissolvido` | CAR e INCRA dissolvidos por UF | `Analise_Territorial_CAR-INCRA_dissolvido` |
| `Cruzamento_Espacial` | Cruzamentos VS x CAR, TI, UC, manguezal, projetos e embargos; projetos com atributos de VS; VS recortada por UF | `Cruzamento_Espacial_Vegetacao_Secundaria`, `Projetos_com_VegSec`, `CAR_Maio2026_Imoveis_Selecionados\_veg_*` |
| `Computo_Planaveg_2026\Insumos` | Passo 1 do cômputo | `Computo_Planaveg_2026\Insumos` |
| `Computo_Planaveg_2026\Hierarquia\TierN_*` | Classes 1 a 11 do cômputo; `TierN_*_por_uf.zip` = arquivos por UF das classes do CAR | `Computo_Planaveg_2026\TierN_*` |
| `Computo_Planaveg_2026\Reporte_Final` | Reporte final (Total e uma camada por classe, duas versões da VS) | `Computo_Planaveg_2026\Reporte_Final` |
| `Computo_Planaveg_2026\Visualizacao` | Produto de visualização (Brasil, por UF e logs) | `Computo_Planaveg_2026\Visualizacao` |
| `Computo_Planaveg_2025` | Reporte do cômputo 2025 (referência) | `Computo_Planaveg_2025` |
| `_Registros_Processamento.zip` | Logs e progresso das rodadas de processamento | copiado sem extrair |
| `_manifesto_backup.csv` | Inventário do backup (ver abaixo) | — |

### Manifesto

O `_manifesto_backup.csv` (separador `;`, abre direto no Excel) tem uma linha por pasta, por
arquivo do backup e por arquivo dentro de cada zip:

| Coluna | Conteúdo |
|---|---|
| `caminho_backup` | Arquivo no backup (`zip::arquivo interno` para conteúdo de zip) |
| `nivel` | `pasta`, `arquivo`, `conteudo_zip` ou `somente_dropbox` |
| `grupo`, `etapa` | Dado original, produto intermediário, produto final, relatório, registro |
| `repositorio`, `script_produtor`, `scripts_consumidores` | Quem gera e quem lê o dado |
| `caminho_no_codigo` | Caminho que o código usava na máquina original |
| `necessario_reprocessar` | `sim` se alguma etapa depende do item |
| `destino_relativo` | Onde o item é restaurado, relativo à pasta de dados |

## Como restaurar

1. Escolha a pasta de dados (ex.: `D:\PLANAVEG_DADOS`). Ela substitui a antiga
   `GEODATABASE\GEOPACKAGE`.
2. Simule, para ver o volume por pasta e o espaço necessário:

   ```powershell
   python restaurar_backup.py --backup F:\BKP_PLANAVEG --destino D:\PLANAVEG_DADOS
   ```

3. Restaure:

   ```powershell
   python restaurar_backup.py --backup F:\BKP_PLANAVEG --destino D:\PLANAVEG_DADOS --executar
   ```

Opções:

| Opção | Efeito |
|---|---|
| `--escopo minimo` (padrão) | Só o que alguma etapa precisa para reprocessar (`necessario_reprocessar = sim`) |
| `--escopo completo` | Tudo, inclusive produtos finais, referências, relatórios e registros |
| `--repo computo visualizacao ...` | Só o que esses repositórios produzem ou leem (`conformidade`, `cruzamento`, `computo`, `visualizacao`) |
| `--sobrescrever` | Substitui arquivos existentes (por padrão, pula os que já têm o mesmo tamanho) |
| `--manter-aninhados` | Não expande zips que estão dentro de outros zips (VS recortada por UF) |

Exemplos:

```powershell
# só o necessário para refazer a visualização
python restaurar_backup.py --destino D:\PLANAVEG_DADOS --repo visualizacao --executar
# tudo
python restaurar_backup.py --destino D:\PLANAVEG_DADOS --escopo completo --executar
```

A restauração pode ser interrompida e retomada: arquivos já restaurados são pulados. Cada
rodada grava `_restauracao_<data>.csv` na pasta de destino. O backup pode estar em outro
caminho (outro disco, outra letra): basta informar `--backup`.

## Apontar os scripts para a pasta restaurada

Defina as variáveis de ambiente uma vez (abra um terminal novo depois do `setx`):

```powershell
setx PLANAVEG_RAIZ "D:\PLANAVEG_DADOS"
setx PLANAVEG_GEO  "D:\PLANAVEG_DADOS"
```

Não defina `PLANAVEG_SAIDA` de forma permanente: o `computo_hierarquia-planaveg` usa esse nome
para a pasta `Computo_Planaveg_2026`, e o `incorporar_vegsec_projetos.py` para
`Projetos_com_VegSec`. Use-a só na sessão do terminal, se precisar.

| Repositório | Como lê a pasta de dados |
|---|---|
| `computo_hierarquia-planaveg` | `PLANAVEG_RAIZ` (`config_computo.py`); nada a editar |
| `visualizacao_categoria-fundiaria` | `PLANAVEG_GEO` (`viz_comum.py`); nada a editar |
| `cruzamento_vegetacao-secundaria` | `PLANAVEG_RAIZ` em `cruzar_embargos_vegsec.py` e `incorporar_vegsec_projetos.py`; caminhos fixos nos demais (tabela abaixo) |
| `analise_conformidade_sicar-incra` | Caminhos fixos (tabela abaixo) |

### Caminhos fixos a editar (estado em outubro/2026)

Esses scripts ainda trazem caminhos absolutos e, em parte, nomes de pasta anteriores à
organização do backup. Antes de rodá-los, troque o valor pela pasta restaurada:

**cruzamento_vegetacao-secundaria**

| Script | Constante | Usar |
|---|---|---|
| `1_processar_dados_VS_qualificada.py`, `1_processar_dados_VS_2024_qualificada.py` | `VEG_GPKG` / `VS_DIR` | `<dados>\Vegetacao_Secundaria_INPE` |
| idem | `CAR_DIR` | `<dados>\CAR_Maio2026_Imoveis_Selecionados` |
| `2_cruzamento_espacial_VS_qualificado.py`, `2_cruzamento_espacial_VS_2024.py` | `CAR_DIR` | `<dados>\CAR_Maio2026_Imoveis_Selecionados` |
| idem | `CRUZ_DIR` | `<dados>\Cruzamento_Espacial_Vegetacao_Secundaria\VS-Cadastro_Ambiental_Rural` |
| `cruzar_projetos_vegsec_qualificado.py`, `cruzar_projetos_vegsec_qualificado_2022_2024.py` | `PASTA_PROJETOS` | `<dados>` |
| idem | `PASTA_VEGSEC_INPE` | `<dados>\Vegetacao_Secundaria_INPE` |
| idem | `PASTA_SAIDA` | `<dados>\Cruzamento_Espacial_Vegetacao_Secundaria` (os resultados ficam em `VS-<tema>`) |
| `agregar_areas_uc*.py` | `PASTA` | `<dados>\Cruzamento_Espacial_Vegetacao_Secundaria\VS-Unidades_Conservacao` |
| `analisar_vegsec_*.py` | `PASTA` | `<dados>\Vegetacao_Secundaria_INPE` |
| `0_incorporar_app_rl_aur_analisados.py` | `NEW_DIR` | `<dados>\CAR_Maio2026_Imoveis_Selecionados` |

`1_processar_dados_VS.py`, `2_cruzamento_espacial_VS.py`, `3_analise_consistencia_VS.py`,
`4_validacao_resultados_VS.py` e `cruzar_projetos_vegsec.py` são do fluxo com VS sem
qualificação, substituído pelas versões qualificadas; não precisam ser rodados.

**analise_conformidade_sicar-incra**

| Script | Constante | Conteúdo esperado |
|---|---|---|
| `1_processar_dados_incra.py` | `PASTA_SAIDA` | INCRA (SIGEF e SNCI) separado por UF |
| `2_processar_dados_sicar.py`, `5_extracao_APP_RL_AUR.py` | `PASTA_SICAR` | SICAR bruto: uma pasta por estado, um `.zip` por plano |
| `2_` a `6_` | `PASTA_ANALISE` / `BASE_ROOT` | Pasta de trabalho da conformidade (`dados_saída_<UF>`) |
| `4_analise_conformidade.py` | `PASTA_INCRA` | INCRA por UF (saída do script 1) |

## Limitações

- **Conformidade SICAR x INCRA.** O backup guarda o resultado (imóveis selecionados por UF),
  não as bases que o geram: o INCRA por UF e a pasta de trabalho `dados_saída_<UF>` não estão
  no backup. O SICAR bruto está como GeoPackage nacional, e o script 2 lê pastas por estado.
  Para refazer a conformidade do zero, baixe de novo SICAR e INCRA (ou adapte o script 2 para
  ler o GeoPackage nacional).
- **`dissolver_car_total.py`**, que gerou os CARs dissolvidos por UF, não está em nenhum dos
  quatro repositórios.
- **Arquivos acima de 2 GB.** Vários GeoPackages restaurados passam de 2 GB; o ArcGIS pode não
  abri-los (o QGIS abre).
- **Zips aninhados.** A VS recortada por UF está em zips dentro de outro zip; a restauração os
  expande (a não ser com `--manter-aninhados`) e os extrai de novo a cada rodada.

## Manutenção do backup

Depois de acrescentar ou trocar arquivos no backup, regere o manifesto e copie-o para
`manifesto/`:

```powershell
python organizar_backup.py --so-manifesto      # só relê o índice dos zips
python organizar_backup.py --verificar-crc     # idem + confere a integridade de todos os zips (lento)
```

Sem opções, `organizar_backup.py` simula a consolidação de registros soltos em
`_Registros_Processamento.zip`; `--executar` a aplica. As regras de classificação (repositório,
scripts, caminho no código) ficam em `classificar()`, no próprio script; atualize-as quando os
repositórios de processamento mudarem.
