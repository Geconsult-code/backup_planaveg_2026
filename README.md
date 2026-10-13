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
| `complementar_backup.py` | Acrescenta ao backup os insumos e a pasta de trabalho da conformidade SICAR x INCRA |
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
| `Cadastro_Ambiental_Rural` | SICAR bruto nacional em GeoPackage (maio e junho/2026; referência) | `_SICAR_bruto` |
| `Cadastro_Ambiental_Rural\BASE_CAR_ESTADOS_05_2026` | SICAR bruto de maio/2026 por estado: `<ESTADO>.zip` com os 9 zips por plano | `Analise_Conformidade_CAR-INCRA\SICAR_BASE_CAR_ESTADOS_05_2026\<ESTADO>` |
| `Cadastro_INCRA` | SIGEF e SNCI nacionais de 10/06/2026 (Brasil, Privado, Público) e o INCRA privado por UF | `Analise_Conformidade_CAR-INCRA\INCRA` (`\SIGEF`, `\SNCI`) |
| `Analise_Conformidade_CAR-INCRA` | Pasta de trabalho da conformidade: `dados_saida_<UF>.zip` (sem `<UF>_shapefile`), relatório de áreas, registros e projetos QGIS | `Analise_Conformidade_CAR-INCRA\Resultados_Analise_Conformidade` |
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
| `--manter-aninhados` | Não expande zips que estão dentro de outros zips (VS recortada por UF, downloads do INCRA) |

Exemplos:

```powershell
# só o necessário para refazer a visualização
python restaurar_backup.py --destino D:\PLANAVEG_DADOS --repo visualizacao --executar
# insumos e pasta de trabalho da conformidade SICAR x INCRA
python restaurar_backup.py --destino D:\PLANAVEG_DADOS --repo conformidade --executar
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

Com isso, nenhum script precisa ser editado: os quatro repositórios leem a mesma estrutura
de pastas da restauração.

| Repositório | Como lê a pasta de dados |
|---|---|
| `computo_hierarquia-planaveg` | `PLANAVEG_RAIZ` (`config_computo.py`) |
| `visualizacao_categoria-fundiaria` | `PLANAVEG_GEO` (`viz_comum.py`) |
| `cruzamento_vegetacao-secundaria` | `PLANAVEG_RAIZ` (constante `RAIZ` no topo de cada script) |
| `analise_conformidade_sicar-incra` | `PLANAVEG_RAIZ`, via `conformidade/caminhos.py`: usa `<dados>\Analise_Conformidade_CAR-INCRA` se essa pasta existir; senão, as pastas originais no Dropbox |

Sem `PLANAVEG_RAIZ`, os scripts usam `GEODATABASE\GEOPACKAGE` no Dropbox, e a conformidade usa
as pastas originais do SICAR, do INCRA e `GEODATABASE\Analise_Conformidade_CAR-INCRA`. A cópia reduzida do
Dropbox não tem os intermediários (cruzamentos, imóveis selecionados por UF etc.); para
reprocessar é preciso restaurar o backup.

Os scripts do `cruzamento_vegetacao-secundaria` sem qualificação (`1_processar_dados_VS.py`,
`2_cruzamento_espacial_VS.py`, `3_*`, `4_*`, `cruzar_projetos_vegsec.py`, `agregar_areas_uc.py`)
foram substituídos pelas versões qualificadas e não precisam ser rodados.

Os scripts 4 a 6 retomam do ponto em que pararam usando os `_progresso_*.json`. Esses
arquivos ficam em `Registros_Resultados_Conformidade.zip` e **não** são restaurados, para
que uma nova rodada não pule etapas.

## Limitações

- **`dissolver_car_total.py`** (agora no `analise_conformidade_sicar-incra`) é a última versão
  versionada (ago/2026) e lê a estrutura de pastas daquela época. Os CARs dissolvidos de maio/2026
  do backup saíram de uma adaptação que não foi versionada; o CONFIG traz a estrutura atual
  comentada, a validar com um estado antes do lote.
- **GeoPackages nacionais `CAR_Nao_Analisado_*_Maio2026`** (cerca de 39 GB, não lidos pelos scripts)
  só entram no backup com `complementar_backup.py --incluir-nacionais`.
- **Arquivos acima de 2 GB.** Vários GeoPackages restaurados passam de 2 GB; o ArcGIS pode não
  abri-los (o QGIS abre).
- **Zips aninhados.** A VS recortada por UF está em zips dentro de outro zip; a restauração os
  expande (a não ser com `--manter-aninhados`) e os extrai de novo a cada rodada.

## Manutenção do backup

### Complementar com a conformidade SICAR x INCRA

`complementar_backup.py` copia para o backup o SICAR por estado, o INCRA e a pasta de trabalho da
conformidade, um zip por estado ou UF, conferindo cada um. Parte desses arquivos está no Dropbox
como "somente online": ao lê-los, o Dropbox os baixa para o disco C:. A simulação mostra quanto
será baixado e o espaço livre; o script para antes de um item que não caiba no C:.

```powershell
python complementar_backup.py                  # simulação
python complementar_backup.py --executar       # grava (rodar de novo só grava o que falta)
python organizar_backup.py --so-manifesto      # depois, regere o manifesto
```

### Manifesto

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
