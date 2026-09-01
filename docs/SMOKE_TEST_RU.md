# Smoke test checklist

Чеклист нужен после крупных изменений GUI, CLI, installer scripts, RClone/network/archive слоя или документации с изменением команд.

## Быстрый обязательный набор

```bat
runtime\python.exe -m py_compile system_core\main.py system_core\auditor_core.py system_core\services\disk_auditor_service.py system_core\ui_nicegui\app.py system_core\ui_nicegui\window.py system_core\services\rclone_service.py
```

```bat
runtime\python.exe system_core\ui_nicegui\app.py --smoke
```

Security guard должен отказать non-loopback host:

```bat
runtime\python.exe system_core\ui_nicegui\app.py --host 0.0.0.0 --smoke
```

Ожидаемый результат: non-zero exit code и сообщение `Refusing non-loopback host`.

```bat
runtime\python.exe system_core\main.py pairs
```

```bat
runtime\python.exe system_core\main.py info
```

```bat
install\Check-CmdEncoding.cmd
```

Если в portable runtime нет `pytest`, ставьте его во временную папку, не в проектный runtime:

```bat
runtime\python.exe -m pip install --target tmp\pytest-deps pytest
runtime\python.exe -c "import sys; sys.path.insert(0, r'tmp\pytest-deps'); import pytest; raise SystemExit(pytest.main(['tests','-q']))"
```

После проверки `tmp\pytest-deps` можно удалить.

## Текущий baseline полного smoke

После крупных GUI/RClone/network изменений baseline считается зелёным, если прошли:

- `py_compile` по `main.py`, auditor/service, GUI app/window и `rclone_service.py`;
- `app.py --smoke`;
- non-loopback guard через `app.py --host 0.0.0.0 --smoke` с ожидаемым отказом;
- `main.py info` и `main.py pairs`;
- `launcher_project.cmd` и `launcher_profiles.cmd` с `AUDION_AUTO_EXIT=1`;
- `window.py --help`, где видны `--elevate` и `--no-elevate`;
- disposable CLI smoke: `manifest`, `verify`, `compare-safe`, `sync-dry-run`, `sync-apply`, `backup-quarantine`, `backup-hard` только на disposable target, `sync2-dry-run`, `sync2-apply`, `sync-mask`;
- disposable service smoke: archive ZIP/7Z, Robocopy safe/fast/large/update/scan/mirror, pack stage, direct archive to share, verify/extract archive, SMB `show_paths`, RClone command preview для всех GUI modes;
- `Tools\rclone\rclone.exe version`;
- `rclone listremotes` через active portable config/cache, даже если remotes ещё не настроены;
- `install\Build-Docs-PDF.cmd --dry-run`.

Режимы с внешними side effects проверяются вручную: реальное SMB share create/remove и открытие PeaZip GUI.

## PDF-документация

Проверить план:

```bat
install\Build-Docs-PDF.cmd --dry-run
```

Полная пересборка generated PDF:

```bat
install\Build-Docs-PDF.cmd --clean
```

После генерации проверить, что `docs\PDF` содержит `.dark.pdf` и `.light-sand.pdf`, а `report\dev_markdown_pdf_manifest.json` обновился.

## RClone

Если установлен:

```bat
Tools\rclone\rclone.exe version
```

```bat
Tools\rclone\rclone.exe --config config\rclone\rclone.conf --cache-dir tmp\rclone-cache listremotes
```

В GUI проверить:

- root-раздел `ТРАНСФЕР ДАННЫХ` виден и стоит первым;
- раздел открывается: было падение `Invalid value: cloud`, когда слой переименовали, а имя осталось вписанным строкой;
- группы `Перенос`, `Хранилище`, `Подключения`, `Диагностика` переключаются;
- в `Перенос` видны `Операция`, `Машины`, `Наполнение`, `Что произойдёт`;
- операции: `Односторонняя`, `Зеркало`, `Перенести`, `Двусторонняя`, `Сверить`; строка движка называет Robocopy или RClone и объясняет почему;
- назначений можно добавить несколько, и отказ по невозможной паре виден до запуска;
- `Сначала упаковать` действительно упаковывает: в журнале появляется `PACK`, и на приёмник приезжают архивы, а не россыпь;
- при удалённом источнике упаковка не молчит, а говорит, что упаковывать нечего;
- `Стоп, если удалений больше` появляется только у зеркала и добавляет `--max-delete` в команду;
- у ключа и `known_hosts` есть кнопка «в проект»: файл ложится в `config\ssh`, путь в поле становится относительным, чужой `id_rsa` не затирает свой;
- блок `RClone config` появляется только в mode `Config`, а в `Версия`, `Список remote`, `GUI`, OAuth и SFTP не занимает высоту;
- компактная линейка `Installer RClone` в `Настройка` показывает кнопки `System` и `Portable`;
- линейка `Configuration` в `Настройка` показывает scope `Portable`, `System`, `Custom path`, кнопки `Import`, `Export`, `Doctor`, а поле custom path появляется только при выборе `Custom path`;
- default scope `Portable` добавляет в preview `--config config\rclone\rclone.conf` и `--cache-dir tmp\rclone-cache`;
- активная команда во вкладке подсвечена приглушённым success-цветом;
- constructor preview показывает EXE, ROUTE, CONFIG, CACHE, LOG и команду;
- endpoint-панели показывают `SOURCE ENDPOINT` и `TARGET ENDPOINT`;
- auth-mode показывает панель `REMOTE`, SFTP inline `user@host:port` и masked password поле;
- SFTP user/host имеют history dropdown, пример host использует `203.0.113.10`, а кнопка очистки удаляет `config\rclone_endpoint_history.json`;
- tooltip на `ЗАПУСТИТЬ` в `Провайдеры OAuth` объясняет отдельное окно, blank `Client ID`/`Client Secret`, default/No для advanced config и Yes/browser для auto config;
- tooltip на `ЗАПУСТИТЬ` в `Create/update SFTP remote` объясняет, что интерактивного ввода не будет, а remote создаётся/обновляется через `config create/update`;
- SFTP auth-панель умеет записать собранный remote в `SOURCE ENDPOINT` или `TARGET ENDPOINT`;
- `Remote` вводится без `:`;
- превью переноса строит команду выбранной операции: `copy`, `sync`, `move`, `bisync` или `check`;
- `Сверить` ничего не пишет;
- `Убрать недозалитое` в `Хранилище` объясняет, что убирает брошенные части многочастных заливок, а не корзину.
- `rclone_log_level=DEBUG` показывает предупреждение о чувствительном raw log.
- `Ограничение скорости` занимает отдельную строку под flags и переключает `Без лимита` / `Выбор скорости` / `Своя скорость` без дублирования `--bwlimit`.
- режимы `Config` и `GUI` открываются в отдельной консоли без промежуточного `cmd /k`.

## GUI

Проверить:

- `launcher_gui.cmd` стартует;
- wrapper не запрашивает UAC сам, а `--help` показывает opt-in `--elevate`;
- если порт 8080 занят, выбирается другой порт;
- source/target history работает;
- `Pin`, `Unpin`, open folder работают;
- правый терминал показывает кириллицу и перенос длинных строк;
- команда с `Authorization: Bearer ...` или `7z a -pSecret ...` не сохраняется в history/pins;
- tooltip появляется после задержки около `1500 ms`;
- tooltip уходит быстро, около `100 ms`;
- нативный browser `title` не появляется вторым слоем; доступность остаётся через `aria-label`;
- общий tooltip скруглённый, с фоном `RGB(23, 33, 43)`, тонкой рамкой и компактным текстом;
- extension cards: три плитки в ряду имеют одинаковую ширину, две плитки делят строку пополам, одиночная/длинная группа занимает всю строку;
- внутри extension card 1-3 чекбокса идут вертикально, а 4+ чекбокса разбиваются на две внутренние колонки;
- тема `code_dark` не ломает читабельность;
- отчёт `Последний` открывается.

## Sync

На маленьких test folders:

1. `compare` показывает diff.
2. `Односторонняя` с пробным прогоном ничего не пишет.
3. `Односторонняя` копирует новое и не трогает лишнее в приёмнике.
4. `Двусторонняя` с пробным прогоном показывает направления.
5. `Зеркало` с пробным прогоном показывает планируемые удаления.
6. `Зеркало` с карантином переносит target-only в `_audion_quarantine`.

Hard delete mirror проверять только на disposable target.

## Profiles

Проверить:

- `pairs` не падает;
- если `sync_pairs.json` пустой, GUI показывает example profiles;
- `copy_by_mask` требует маски;
- `dev_backup` и другие backup profiles отображаются как BACKUP-MIRROR;
- runtime extension override не переписывает JSON config.

## Archive

Проверить на маленькой папке:

- ZIP создаётся;
- 7Z создаётся, если backend найден;
- SFX создаётся, если backend найден;
- password mode не предлагает formats, где оно не поддерживается;
- SFX wrapper создаётся только после SFX;
- `archive_delete_source` не использовать на реальных данных в smoke.

## Docs

Проверить:

- новые docs доступны из `USER_GUIDE_RU.md`;
- README RU/EN ссылаются на guides;
- имена команд в docs совпадают с GUI;
- `.cmd` кодировка не изменилась.
