# Known pitfalls

## Перепутан source и target

Для `BACKUP-MIRROR` это главная опасность. Source - сторона истины. Target будет приведён к source и target-only файлы могут быть удалены.

Привычка: перед mirror запускать compare или dry-run и смотреть planned deletes/quarantine.

## `sync_pairs.json` пустой

Это не поломка. GUI показывает bundled examples из `sync_pairs.example.json`. Рабочие профили можно импортировать, экспортировать или записать в `sync_pairs.json`.

## `copy_by_mask` запущен без маски

`copy_by_mask` требует mask override. Выберите группы или введите glob masks.

## Hard mirror на отфильтрованном scope

Отфильтрованный mirror может удалить target-only файлы вне ожидаемого набора, если policy применён неверно. CLI имеет guard `--yes-filtered-hard`; используйте его только осознанно.

## Большой delete ratio

Если план собирается удалить большую долю target, CLI может заблокировать apply до `--yes-delete-ratio`.

## Отключившийся сетевой корень выглядит как пустая папка

Это не то же самое, что пустой источник. Смонтированный удалённый корень, чей peer уснул или отключился, остаётся
существующей директорией: `path.exists()` истинно, `path.is_dir()` истинно, а внутри ноль файлов. Сканирование
честно возвращает пустой список, и план читается как "удалить в приёмнике всё".

Существующие защиты этот случай не ловят:

- `mirror_hard` на цели меньше `DELETE_COUNT_FLOOR` (50 файлов) - ratio-guard не срабатывает. Для локальных дисков
  это сделано намеренно, для сетевого источника это неверно.
- `mirror_safe` ratio-guard не проверяет вообще. Ничего не удаляется, но всё дерево приёмника переезжает в
  `_audion_quarantine` по сети.

Привычка: для пар, где хотя бы один корень приходит из сети, ставить `"anchor": true` и один раз создавать якорь:

```bat
runtime\python.exe system_core\main.py anchor N:\Projects
```

После этого недоступный корень отличается от пустого до построения плана: вместо тихого нуля файлов поднимается
`SourceUnreachable`. Подробно в [SYNC_PROFILES_RU.md](SYNC_PROFILES_RU.md).

## Запуск по устаревшему просмотру

Карточка `ПРОВЕРКА ПЕРЕД ЗАПУСКОМ` показывает токен подтверждения вида `DELETE 53289F2276BC`. Он привязан к
маршруту, политике и плановым цифрам. Если между просмотром и запуском что-то изменилось, apply откажется
работать с `PreviewConfirmationMismatch`. Это не сбой: постройте просмотр заново и посмотрите на новые цифры.

## Медленный RClone без прогресса

Выбирайте transfer profile с `--stats 1s --progress`. Все текущие GUI profiles уже делают это. Если канал рвётся, используйте `unstable_mobile` и задайте `--bwlimit`.

## RClone remote name с двоеточием

В поле `Remote` вводится имя без двоеточия: например `drive` или `yandex`, не `drive:`/`yandex:`. Двоеточие добавляет builder команды.

## Видимое окно RClone wizard

Это нормально для OAuth/provider auth, полного `Config` и официального `rclone gui`. GUI открывает отдельную видимую консоль без `cmd /k`, чтобы пользователь понимал назначение окна и не терял контроль над интерактивной авторизацией.

## SFTP password-auth

Пароль вводится только в masked поле auth builder-а. Он не сохраняется в command cache/history и перед записью в `rclone.conf` проходит через `rclone obscure -` по stdin. Для долгоживущих серверных маршрутов предпочтительнее `ssh-agent` или `key_file` плюс `known_hosts`.

## OAuth tokens в логах

Не запускайте `rclone config show` через GUI command bar, если не готовы вручную контролировать вывод. GUI RClone modes не используют эту команду и редактируют очевидные token/password поля.

## GUI не на localhost

Не запускайте GUI с правым терминалом на `0.0.0.0`, LAN/VPN IP или публичном интерфейсе. По умолчанию приложение откажется стартовать на non-loopback host. Override `AUDION_ALLOW_REMOTE_GUI=1` оставлен только для осознанных локально защищённых сценариев, потому что такая панель является remote command execution surface.

## История терминала и секреты

Terminal command history не сохраняет и не закрепляет команды с очевидными секретными маркерами (`token`, `secret`, `password`, `Authorization`, `Bearer`, `-p...`). Но лучше не вводить OAuth tokens, app passwords и архивные пароли в command bar: используйте профильные UI-поля или отдельные консоли, где вывод контролируется вручную.

## DEBUG rclone log

`rclone_log_level=DEBUG` включайте только временно для локальной диагностики. Raw rclone log может содержать детали remote/request, которые не стоит прикладывать к публичным issue или release-архивам.

## Direct archive to share

`pack_direct` пишет архив сразу на share. При обрыве сети archive может оказаться неполным. Для слабой сети лучше `pack_stage`.

## SFX и антивирус/почта

SFX `.exe` может блокироваться почтой, браузером или antivirus policy. Используйте SFX wrapper archive, если нужно передать файл.

## Кодировка CMD

Все `.cmd` должны оставаться UTF-8 without BOM и CRLF. После изменения `.cmd` запускать:

```bat
install\Check-CmdEncoding.cmd
```

## Очистки

Очистка `input/output` и `workspace` не должна применяться к внешним source/target. Если нужно удалить внешний каталог, это не задача cleanup-кнопки проекта.

## Пустой remote path

Пустой `rclone_remote_path` означает root remote. Для первого upload лучше явно создать подпапку через `mkdir_remote`.
