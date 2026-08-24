# Manifest / Diff reference

В GUI раздел `Manifest / Diff` работает от текущих путей Workbench: `Источник` -> `Назначение`.

Обычный сценарий для копирования новых и изменённых файлов:

1. Выбрать `Источник` и `Назначение` в Workbench.
2. В `Manifest / Diff` выбрать группы расширений, если нужно сузить расчёт. Пустой выбор = все файлы.
3. Нажать `DIFF + ONE-WAY SYNC`.

Эта команда сначала строит свежий Diff `Источник -> Назначение`, затем запускает One-Way copy/update только по найденным относительным путям. Лишние файлы в цели не удаляются.

## Действия GUI

| GUI id | Что делает |
| --- | --- |
| `diff_then_sync_manifest` | Пересчитать Diff и сразу выполнить One-Way copy/update по свежему списку. |
| `diff_then_backup_manifest` | Пересчитать Diff и выполнить BACKUP-MIRROR только внутри свежего mirror-списка. Target-only пути внутри Diff могут удаляться. |
| `diff_source_target_manifest` | Только построить Diff и списки путей, без изменения файлов. |
| `sync_from_manifest_diff` | Выполнить One-Way по последнему `manifest_diff_latest_one_way_paths.txt` или по указанному `diff_file`. |
| `backup_from_manifest_diff` | Выполнить BACKUP-MIRROR по последнему `manifest_diff_latest_mirror_paths.txt` или по указанному `diff_file`. |
| `create_source_manifest` | Создать отдельный `__CHECKSUMS__.b3` внутри текущего источника. Для Diff + One-Way не обязателен. |
| `create_target_manifest` | Создать отдельный `__CHECKSUMS__.b3` внутри текущей цели. Для Diff + One-Way не обязателен. |
| `verify_source_manifest` | Проверить текущий источник по его `__CHECKSUMS__.b3`. |
| `verify_target_manifest` | Проверить текущую цель по её `__CHECKSUMS__.b3`. |

## Поля GUI

| Поле | Что делает |
| --- | --- |
| `mode` | Режим сравнения: `safe`, `quick`, `strict`. Для обычной работы используйте `safe`. |
| `manifest_extensions` | Комбайн групп и отдельных расширений. Пустой выбор = все файлы. |
| `diff_file` | Необязательный готовый список относительных путей. Если пусто, команды применения берут последний список из `report`. |

`Источник` и `Назначение` берутся из Workbench автоматически и не дублируются отдельными полями в этом экране.

## Что создаёт Diff

`diff_source_target_manifest` и комбинированные команды создают в `report`:

- `manifest_diff_latest.json` - полный JSON с summary и исходным compare payload;
- `manifest_diff_latest_tree.txt` - человекочитаемое дерево относительных путей по действиям;
- `manifest_diff_latest_one_way_paths.txt` - список путей для One-Way copy/update;
- `manifest_diff_latest_mirror_paths.txt` - список путей для BACKUP-MIRROR.

Также сохраняются timestamp-копии этих файлов.

## Что такое root

`root` - это CLI-термин для одиночного checksum-manifest: папка, относительно которой записываются пути в `__CHECKSUMS__.b3`.

В GUI-пайплайне копирования `root` не нужен: текущие Workbench `Источник` и `Назначение` уже являются двумя корнями сравнения.

CLI-пример одиночного checksum-manifest:

```bat
runtime\python.exe system_core\main.py manifest --root D:\DATA
```

CLI-пример проверки одиночного checksum-manifest:

```bat
runtime\python.exe system_core\main.py verify --root D:\DATA
```
