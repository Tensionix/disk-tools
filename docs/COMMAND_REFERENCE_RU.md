# Audion Disk Tools - справочник команд и параметров

Этот документ описывает фактические команды GUI/CLI текущего проекта. GUI-узлы могут выглядеть компактно, но каждый из них собирает конкретные параметры и передаёт их в сервисный слой или CLI.

## Общие термины

`Источник` (`source`) - папка, откуда читаются файлы.

`Назначение` (`target`) - папка, куда пишутся файлы, архивы или результаты download.

`mode=safe` - штатный режим сравнения для реальной работы.

`mode=quick` - более быстрый режим, сильнее опирается на метаданные.

`mode=strict` - CLI-only вариант для более строгой проверки там, где он доступен.

`dry_run` или `--dry-run` - построить план и отчёт без записи, удаления или карантина.

`copy_update` - копировать и обновлять, target-only файлы не трогать.

`mirror_safe` - target-only файлы переносить в `_audion_quarantine`.

`mirror_hard` - target-only файлы удалять после успешных ранних фаз.

## GUI ROOT-команды

### ПАПКА В ПАПКУ

GUI id: `manual_backup_apply`.

CLI: `backup` / `sync` / `sync2` / `compare` — команду задаёт выбранная операция.

Назначение: прогон самого аудитора по паре источник → приёмник. Сверка BLAKE3, политика карантина и отчёт о расхождениях — то, чего сборщик трансфера не делает. Список машин, облака и сервер — в разделе `ТРАНСФЕР ДАННЫХ`.

Раньше это были три раздела — `BACKUP-MIRROR`, `One-Way sync`, `Two-Way sync`. Они звали один и тот же сервис через одни и те же поля и отличались единственным словом, поэтому стали одним разделом с кнопками операций.

| Операция | CLI | Удаляет в приёмнике |
| --- | --- | --- |
| Зеркало | `backup` | да, target-only файлы по политике mirror |
| Односторонняя | `sync` | нет |
| Двусторонняя | `sync2` | нет, обмен в обе стороны |
| Сверить | `compare` | ничего не пишется |

Параметры:

| Поле | Тип | Значение | Что делает |
| --- | --- | --- | --- |
| `source_dir` | path history | путь | Явный источник. Можно ввести вручную, выбрать picker-ом или взять из history/pin. |
| `target_dir` | path history | путь | Явная цель. |
| `mode` | radio | `safe`, `quick` | Режим сравнения. По умолчанию `safe`. |
| `manual_extensions` | checkboxes | glob-группы и точечные расширения | Runtime include/exclude override. Пусто = без ручного override. |

Пробный прогон и карантин — переключатели над операцией, а не отдельные команды.

Риск: destructive для зеркала. Оно и означает, что приёмник станет копией источника.

### Маски

GUI id: `ui_mask_copy`.

Назначение: ручной конструктор glob-масок и одноразовый запуск по выбранной операции.

Параметры:

| Поле | Тип | Значение | Что делает |
| --- | --- | --- | --- |
| `mask_operation_mode` | mode buttons | `backup_mirror`, `one_way`, `two_way` | Переключает CLI-команду: `backup`, `sync`, `sync2`. |
| `manual_mask_text` | text area | `*.pdf, *.docx` | Ручные маски через запятую, `;` или переносы. Нормализуются в glob. |
| `manual_extensions` | checkboxes | группы/расширения | Добавляет выбранные расширения в `manual_mask_text`. |

Особенность: `backup_mirror` в этом конструкторе ставит `operation_policy=mirror_safe`, поэтому target-only файлы уходят в карантин, а не в hard-delete.

### Сохранённые профили

GUI id: `saved_profiles`.

Источник данных: `config\sync_pairs.json`; если он пуст, GUI показывает `config\sync_pairs.example.json`.

Текущие bundled профили:

| Профиль | CLI | Поведение | Пресеты |
| --- | --- | --- | --- |
| `copy_by_mask` | `sync --pair copy_by_mask` | One-way copy, требует маски или группы | runtime mask, exclude `TEMP` |
| `dev_backup` | `backup --pair dev_backup` | BACKUP-MIRROR | `DEV`, `DOCS`, exclude `TEMP` |
| `docs_backup` | `backup --pair docs_backup` | BACKUP-MIRROR | `DOCS`, exclude `TEMP` |
| `graphics_backup` | `backup --pair graphics_backup` | BACKUP-MIRROR | `GRAPHICS`, exclude `TEMP` |
| `video_backup` | `backup --pair video_backup` | BACKUP-MIRROR | `VIDEO`, exclude `TEMP` |
| `audio_backup` | `backup --pair audio_backup` | BACKUP-MIRROR | `AUDIO`, exclude `TEMP` |
| `arch_backup` | `backup --pair arch_backup` | BACKUP-MIRROR | `ARCH`, exclude `TEMP` |
| `apps_backup` | `backup --pair apps_backup` | BACKUP-MIRROR | `APPS`, exclude `TEMP` |

Каждый профиль имеет поле `profile_extensions__<profile_name>`. Пустое значение сохраняет фильтры профиля как в config. Выбор расширений добавляет runtime mask override только на текущий запуск.

### Архивация

GUI id: `ui_archive_input_folders`.

Назначение: создать архивы из выбранного источника в выбранную цель.

Параметры:

| Поле | Тип | Значение | Что делает |
| --- | --- | --- | --- |
| `archive_formats` | checkboxes | `zip`, `7z`, `sfx`, `lz4`, `tar`, `gz`, `zstd` | Один или несколько форматов. Недоступные backend-ы скрываются/блокируются. |
| `archive_level` | select | `0`, `1`, `3`, `5`, `7`, `9` | Уровень сжатия. `0` быстрее, `9` плотнее. |
| `archive_encryption` | select | `none`, `password`, `names` | Без шифрования, шифровать данные, или шифровать имена. |
| `archive_password` | secret | строка | Маскированный пароль для ZIP/7Z/SFX, где поддерживается. В GUI log `-p...` редактируется как `-p[REDACTED]`. |
| `archive_layout` | toggle buttons | `flat`, `per_folder` | Класть в `TARGET` или `TARGET\<name>`. |
| `archive_name_prefix` | text | строка | Добавляется перед именем исходного элемента. `N.` или `N_` включает нумерацию. |
| `archive_name_suffix` | text | строка | Добавляется перед расширением. `_N` включает нумерацию. |
| `sfx_extract_path` | env path | `{name}` или путь | Путь автоэкстракции SFX. `{name}` заменяется именем исходного элемента. |
| `sfx_wrappers` | checkboxes | `zip`, `7z`, `zstd`, `tar`, `gz` | После создания SFX упаковать `.exe` в транспортный контейнер. |
| `archive_verify_after_create` | checkbox | true/false | Проверить каждый созданный архив после сжатия. ZIP/7Z/TAR/GZ через `7z t`, ZSTD через `zstd -t`. |
| `archive_delete_source` | checkbox | true/false | Удалить исходные файлы и папки после успешной архивации и, если включена, успешной проверки. |

### ТРАНСФЕР ДАННЫХ

GUI id: `ui_rclone_operations`.

Раньше это были два раздела — `ОПЕРАЦИИ ПО СЕТИ` (Robocopy, SMB, UNC) и `ОБЛАЧНЫЕ ОПЕРАЦИИ` (rclone). Чтобы выбрать кнопку, надо было заранее знать, какой инструмент куда дотягивается. Теперь раздел один, и папка, шара, сервер и облако в нём равноправны: человек выбирает операцию и назначение, движок следует из пары и назван в окне.

Группы: `Перенос`, `Хранилище`, `Подключения`, `Диагностика`.

Параметры трансфера:

| Поле | Тип | Значение | Что делает |
| --- | --- | --- | --- |
| `transfer_operation` | кнопки | `one_way`, `mirror`, `move`, `two_way`, `verify` | Что сделать. Команда rclone и команда аудитора следуют отсюда. |
| `transfer_targets` | список | машины | Назначений может быть несколько: один эталон — список реплик — один запуск. Вся раскладка собирается до старта. |
| `transfer_route` | display | маршрут | Куда пойдут данные, каким движком и почему; отказ виден до запуска. |
| `transfer_pack` | переключатель | `none`, `before` | `before` собирает источник в архивы в `workspace\transfer_pack\<имя>` и отправляет их. Единственное, что помогает на россыпи мелких файлов по сети. |
| `transfer_dry_run` | checkbox | true/false | Пробный прогон: `--dry-run` у rclone, `/L /BYTES /FP` у Robocopy. Ничего не пишется. |
| `transfer_delete_ceiling` | число | пусто или N | `--max-delete`. По умолчанию выключен: значение по умолчанию было бы догадкой о том, как человек работает. |
| `rclone_mode` | плитки | см. ниже | Выбор режима внутри раздела. |
| `rclone_config_manager` | display | compact row | Появляется только в `Настройки -> Настройка`: `Installer RClone` (`System`, `Portable`) + `Configuration` scope (`Portable`, `System`, `Custom path`) + `Import`, `Export`, `Doctor`. |
| `rclone_config_scope` | state | `portable`, `system`, `custom` | Какой `rclone.conf` использовать. Управляется из `Configuration`, не из installer-а. `portable` добавляет `--config config\rclone\rclone.conf` и `--cache-dir tmp\rclone-cache`. |
| `rclone_custom_config` | text | path | Явный путь к `rclone.conf`, если в `Configuration` выбран `Custom path`. Это не install target. |
| `rclone_remote_name` | text | `drive` | Имя remote без двоеточия. |
| `rclone_remote_path` | text | `Folder/Subfolder` | Путь внутри remote. Пусто = root. |
| `rclone_endpoint_workbench` | display | toggle-панели | Парный builder `SOURCE ENDPOINT` / `TARGET ENDPOINT`. |
| `rclone_source_kind` | select | `workbench_source`, `workbench_target`, `saved_remote` | Тип source endpoint для route-mode. |
| `rclone_source_remote_name` | text | `drive`, `server` | Remote source без двоеточия. |
| `rclone_source_remote_path` | text | `Audion` | Путь внутри source remote. |
| `rclone_target_kind` | select | `workbench_source`, `workbench_target`, `saved_remote` | Тип target endpoint для route-mode. |
| `rclone_target_remote_name` | text | `server`, `drive` | Remote target без двоеточия. |
| `rclone_target_remote_path` | text | `/home/user/backups` | Путь внутри target remote. |
| `rclone_auth_manager` | display | toggle-панель | Builder авторизации remote. |
| `rclone_auth_remote_name` | text | `server`, `drive` | Имя создаваемого/обновляемого remote. |
| `rclone_auth_backend` | select | `yandex`, `drive`, `onedrive`, `dropbox`, `box`, `mega` | Провайдер для OAuth wizard. |
| `rclone_sftp_user` | history input | `audion` | SFTP user; dropdown последних успешных операций. |
| `rclone_sftp_host` | history input | `203.0.113.10` | SFTP host/IP; dropdown последних успешных операций. |
| `rclone_sftp_port` | text | `22` | SFTP port. |
| `rclone_sftp_remote_path` | text | `/home/user/backups` | Preview path и подсказка для маршрута. |
| `rclone_sftp_auth_method` | select | `agent`, `password`, `key_file` | Метод авторизации SFTP. |
| `rclone_sftp_password` | password | masked | Не сохраняется в cache/history; передаётся в `rclone obscure -` через stdin. |
| `rclone_sftp_key_file` | text | путь | Private key file для SFTP. |
| `rclone_sftp_known_hosts_file` | text | путь | known_hosts для проверки host key. |
| `rclone_flag_profile` | select | `safe_yandex_upload`, `unstable_mobile`, `balanced`, `fast_lan_to_cloud` | Контролируемый набор transfer-флагов. |
| `rclone_bwlimit` | speed builder | `10M`, `1M`, пусто | Optional `--bwlimit`: `Без лимита`, `Выбор скорости` или `Своя скорость` со спиннерами. |
| `rclone_log_level` | select | `INFO`, `DEBUG` | Уровень rclone log file. `DEBUG` только для локальной диагностики: raw log может содержать чувствительные remote/request details. |
| `rclone_command_preview` | display | команда | Визуализация EXE, ROUTE, SOURCE/TARGET, LOG и command line. |

SFTP endpoint history хранится в `config\rclone_endpoint_history.json` и содержит только последние `user` и `host/IP`. Пароли, порты и remote path туда не попадают; очистка доступна из RClone auth-панели и через cleanup script. Каноническая кнопка Workbench `Сбросить` очищает историю путей Workbench, но не RClone endpoint history. Portable `rclone.conf` хранится в `config\rclone\rclone.conf`, исключён из Git и не удаляется cleanup-скриптом.

RClone modes:

| Mode | Команда | Назначение |
| --- | --- | --- |
| `version` | `rclone version` | Проверка установки. |
| `config` | `rclone config` | Интерактивная настройка remote напрямую в отдельной консоли. |
| `gui` | `rclone gui` | Официальный локальный rclone GUI напрямую в отдельной консоли. |
| `list_remotes` | `rclone listremotes` | Список configured remotes. |
| `about_remote` | `rclone about remote:path` | Квота и занятое место remote. |
| `list_remote_path` | `rclone lsf remote:path` | Быстрый список папки remote. |
| `mkdir_remote` | `rclone mkdir remote:path` | Создать папку remote. |
| `remote_test` | `rclone lsf remote:path --max-depth 1` | Быстро проверить доступ к remote/path. |
| `remote_auth_wizard` | `rclone config create <remote> <backend>` | Открыть `Провайдеры OAuth` для Yandex/Drive/OneDrive/Dropbox/Box/Mega. |
| `remote_create_sftp` | `rclone config create/update <remote> sftp ...` | Создать или обновить SFTP remote из GUI-полей. |
| `remote_create_s3` | `rclone config create <remote> s3 provider <...> env_auth true ...` | Cloudflare R2, Wasabi, Selectel и другие S3-совместимые. Ключи в программу не вводятся: пишется ссылка на файл с ними и имя секции внутри. |
| `transfer_run` | `rclone copy/sync/move/bisync/check` либо `robocopy` | Перенос: один эталон, список машин, одна из пяти операций. Команда следует из операции, движок — из пары. |
| `storage_size` | `rclone size <path>` | Общий объём и число объектов по пути. |
| `storage_dedupe` | `rclone dedupe list <path>` | Показать объекты с одинаковыми именами. Только список: удаление дубликатов — это решение, а решение не принимается кнопкой «найти». |
| `storage_cleanup` | `rclone cleanup <path> -v` | Убрать брошенные части многочастных заливок: в списке файлов их не видно, а платят за них. |
| `storage_hashsum` | `rclone hashsum <алгоритм> <path>` | Файл контрольных сумм — чтобы выложить рядом с релизом. |
| `storage_link` | `rclone link <path>` | Публичная ссылка на объект, если хранилище это умеет. |
| `config_encryption_check` | `rclone config encryption check` | Сообщить, зашифрован ли конфиг. |
| `config_encrypt` | `rclone config encryption set` | Поставить фразу на `rclone.conf`. Фраза идёт в `RCLONE_CONFIG_PASS`, а не в командную строку: аргумент виден в списке процессов и в каждой строке лога, которая повторяет команду. |
| `config_decrypt` | `rclone config encryption remove` | Снять фразу. Файл станет читаемым для всего, что сможет его открыть. |

Transfer-профили RClone:

| Profile | Назначение |
| --- | --- |
| `safe_yandex_upload` | Максимально спокойный cloud-профиль; в GUI отображается как `safe_cloud_upload`. Значение id сохранено для совместимости. |
| `unstable_mobile` | Для медленных/рвущихся каналов: больше retry и sleep. |
| `balanced` | Умеренная параллельность для нормального канала. |
| `fast_lan_to_cloud` | Больше transfers/checkers для стабильной быстрой сети. |

### Manifest / Diff

GUI id: `manifest_tools`.

Назначение: построить Diff по текущей паре Workbench `Источник -> Назначение` и применить его как One-Way или BACKUP-MIRROR. Одиночные `__CHECKSUMS__.b3` для источника/цели доступны как служебные команды, но не обязательны для Diff + One-Way.

Поля:

| Поле | Значение | Что делает |
| --- | --- | --- |
| `mode` | `safe`, `quick`, `strict` | Режим сравнения Source/Target. |
| `manifest_extensions` | список масок/групп | Необязательный фильтр расширений. Пустой выбор = считать всё. |
| `diff_file` | путь или пусто | Optional path-list для применения diff. Пусто = latest diff-list из `report`. |

Команды:

| GUI id | CLI | Что делает |
| --- | --- | --- |
| `diff_then_sync_manifest` | `compare`, затем `sync --include-path-list <fresh>` | Пересчитать Diff и сразу выполнить One-Way copy/update. |
| `diff_then_backup_manifest` | `compare`, затем `backup --include-path-list <fresh>` | Пересчитать Diff и сразу выполнить BACKUP-MIRROR внутри fresh mirror-list. |
| `diff_source_target_manifest` | `compare --source <source> --target <target>` | Создать JSON/tree diff и списки относительных путей в `report`. |
| `sync_from_manifest_diff` | `sync --include-path-list <latest>` | One-Way copy/update только по последнему diff-списку. |
| `backup_from_manifest_diff` | `backup --include-path-list <latest>` | BACKUP-MIRROR только внутри последнего mirror diff-списка. |
| `create_source_manifest` | `manifest --root <source>` | Создать `__CHECKSUMS__.b3` для текущего Workbench источника. |
| `create_target_manifest` | `manifest --root <target>` | Создать `__CHECKSUMS__.b3` для текущей Workbench цели. |
| `verify_source_manifest` | `verify --root <source>` | Проверить источник по его `__CHECKSUMS__.b3`. |
| `verify_target_manifest` | `verify --root <target>` | Проверить цель по её `__CHECKSUMS__.b3`. |

### ПОДГОТОВКА

GUI id: `preparation`.

Содержит safe/preview команды:

- `manual_backup_dry` - dry-run для BACKUP-MIRROR.
- `manual_sync_dry` - dry-run для One-Way.
- `manual_sync2_dry` - dry-run для Two-Way.
- `manual_compare` - compare-only.
- `manual_backup_quarantine` - mirror с переносом target-only в `_audion_quarantine`.
- `<profile>_compare` - compare для сохранённого профиля.
- `<profile>_dry_run` - dry-run profile apply.
- `<profile>_quarantine` - quarantine mirror для backup-профиля.
- `copy_by_mask_compare` и `copy_by_mask_dry_run` - безопасные варианты masked copy.

### Обслуживание

GUI id: `maintenance`.

| Команда | Что делает |
| --- | --- |
| `diag_info` | CLI `info`, runtime и пути. |
| `diag_pairs` | CLI `pairs`, список профилей. |
| `cleanup_workspace` | Очистить только managed `workspace`. |

Дополнительные maintenance operations существуют в manifest: `cleanup_input_output`, `clear_path_history`, `cleanup_workspace`. Очистки должны оставаться в пределах project root.

## CLI subcommands

### `info`

```bat
runtime\python.exe system_core\main.py info
```

Печатает project root, Python executable, версию Python и пути дефолтных config.

### `pairs`

```bat
runtime\python.exe system_core\main.py pairs
```

Флаги:

| Флаг | Что делает |
| --- | --- |
| `--pairs-config <path>` | Использовать другой JSON профилей. |
| `--preset-config <path>` | Использовать другой JSON пресетов. |
| `--names-only` | Печатать только имена профилей. |

Каждый профиль в выводе несёт `anchor` и `note`: требуется ли якорь и свободный комментарий автора профиля.

### `anchor`

```bat
runtime\python.exe system_core\main.py anchor N:\Projects
```

Записывает файл-якорь `.audion-anchor` в указанную папку. Якорь доказывает, что корень действительно смонтирован,
а не подставлен пустой директорией отключившегося peer-а. Профили с `"anchor": true` отказываются строить план,
пока якоря нет в обоих корнях.

Аргумент один и позиционный - путь к папке. Во время обычного прогона якорь никогда не создаётся сам: это всегда
отдельное осознанное действие. Повторный запуск на уже заякоренной папке безопасен и возвращает `"created": false`.

### `manifest`

```bat
runtime\python.exe system_core\main.py manifest --root D:\DATA
```

Флаги:

| Флаг | Что делает |
| --- | --- |
| `--root <path>` | Обязательный root для сканирования. |
| `--manifest <path>` | Custom manifest path. |
| `--exclude-cloud-roots` | Пропустить известные cloud roots. |
| `--project-root <path>` | Автоисключить project root. GUI передаёт его при создании manifest. |
| `--mask-globs`, `--exclude-globs` | Сузить manifest по glob-маскам расширений. Если не переданы, manifest считается по всем файлам. |
| `--include-path-list <path>` | Считать только относительные пути из UTF-8 списка. Используется diff/apply workflow. |

### `verify`

```bat
runtime\python.exe system_core\main.py verify --root D:\DATA
```

Флаги: `--root <path>`, `--manifest <path>`.

### `compare`, `sync`, `backup`

Общие флаги:

| Флаг | Что делает |
| --- | --- |
| `--source <path>` | Явный source. |
| `--target <path>` | Явный target. |
| `--pair <name>` | Использовать профиль из config. |
| `--include-path-list <path>` | Ограничить compare/sync/backup точным списком относительных путей. |
| `--pairs-config <path>` | Custom profile config. |
| `--mode quick|safe|strict` | Режим сравнения. |
| `--mirror` | Mirror target-only по operation policy. |
| `--operation-policy copy_update|mirror_safe|mirror_hard` | Явная политика apply. |
| `--include-globs <csv>` | Include patterns. Можно повторять. |
| `--mask-globs <csv>` | Runtime mask override. |
| `--exclude-globs <csv>` | Exclude patterns. |
| `--include-dirs <csv>` | Include dirs. |
| `--exclude-dirs <csv>` | Exclude dirs. |
| `--include-presets <csv>` | Include preset names. |
| `--exclude-presets <csv>` | Exclude preset names. |
| `--exclude-if-size-gt <bytes>` | Исключить файлы больше размера. |
| `--exclude-if-size-lt <bytes>` | Исключить файлы меньше размера. |
| `--exclude-hidden` | Исключить dot-prefixed hidden paths. |
| `--anchor` | Требовать `.audion-anchor` в обоих корнях до сканирования. Для профилей то же самое включается ключом `anchor`. |
| `--preset-config <path>` | Custom preset config. |

Apply-флаги для `sync` и `backup`:

| Флаг | Что делает |
| --- | --- |
| `--dry-run` | Ничего не менять. |
| `--preview` | Alias для `--dry-run`. |
| `--yes-delete-ratio` | Подтвердить apply с большим delete ratio. |
| `--yes-filtered-hard` | Подтвердить `mirror_hard` на отфильтрованном scope. |
| `--allow-hard-delete` | Compatibility no-op, hard mirror определяется command/policy. |
| `--expect-confirmation <token>` | Привязать apply к просмотру. Токен берётся из `preflight.confirmation.token` в выводе `compare`. Если план изменился, apply падает с `PreviewConfirmationMismatch`. |

### `sync2`

```bat
runtime\python.exe system_core\main.py sync2 --source D:\A --target E:\B --mode safe
```

Флаги: `--source`, `--target`, `--pair`, `--pairs-config`, `--mode quick|safe|strict`, `--anchor`, `--dry-run`, `--preview`, `--expect-confirmation <token>` и все filter CSV-флаги.

## Кэш и pin/delete конструкторы

Path history, mask cache, extension selection cache, terminal command history и RClone command cache имеют одинаковую UX-идею:

- `Pin` закрепляет запись.
- `Unpin` снимает закрепление.
- `Delete` удаляет запись из кэша.
- `Clear` очищает текущее поле или незакреплённую историю, в зависимости от панели.

RClone constructor хранит до 120 вариантов в `config\rclone_command_cache.json`.

Terminal command history не сохраняет и не закрепляет команды, похожие на содержащие секреты (`token`, `secret`, `password`, `Authorization`, `Bearer`, `-p...` и похожие маркеры).

## Tooltip

Все NiceGUI `.tooltip(...)` в проекте проходят через общий patch: появление через `1500 ms`, скрытие через `100 ms`, `transition-duration=100 ms`. Это сделано централизованно в `system_core\ui_nicegui\app.py`, чтобы подсказки в старых и новых кнопках вели себя одинаково.
