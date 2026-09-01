# PDF export для документации

Проект умеет собирать Markdown-гайды и инструкции в PDF под `docs\PDF`.

## Команда

```bat
install\Build-Docs-PDF.cmd
```

По умолчанию команда:

- берёт основной набор документации проекта;
- использует движок `E:\TOOLS\Audion Office OCR AI\system_core\dev_markdown_pdf_engine.py`;
- сохраняет настройки layout/тем движка по умолчанию;
- рендерит обе темы: `dark` и `light-sand`;
- пишет PDF в `docs\PDF`;
- пишет source-list в `workspace\docs_pdf_sources.json`;
- пишет manifest движка в `report\dev_markdown_pdf_manifest.json`.

## Runtime

Если локальный `runtime\python.exe` Disk Tools не содержит `playwright` и `markdown-it-py`, wrapper автоматически переисполнит себя через:

```text
E:\TOOLS\Audion Office OCR AI\runtime\python.exe
```

и использует его Playwright browser payload:

```text
E:\TOOLS\Audion Office OCR AI\runtime\.playwright
```

Пути можно переопределить переменными:

```bat
set AUDION_MARKDOWN_PDF_ENGINE=E:\path\to\dev_markdown_pdf_engine.py
set AUDION_MARKDOWN_PDF_PYTHON=E:\path\to\python.exe
set PLAYWRIGHT_BROWSERS_PATH=E:\path\to\.playwright
```

## Основные опции

План без генерации:

```bat
install\Build-Docs-PDF.cmd --dry-run
```

Очистить старые PDF и пересобрать:

```bat
install\Build-Docs-PDF.cmd --clean
```

Собрать только тёмную тему:

```bat
install\Build-Docs-PDF.cmd --theme dark
```

Собрать только светлую тему:

```bat
install\Build-Docs-PDF.cmd --theme light-sand
```

Собрать конкретный файл:

```bat
install\Build-Docs-PDF.cmd --source USER_GUIDE_RU.md
```

Собрать конкретную папку:

```bat
install\Build-Docs-PDF.cmd --source docs
```

## Имена файлов

Для каждой Markdown-инструкции создаётся PDF с suffix темы:

```text
USER_GUIDE_RU.dark.pdf
USER_GUIDE_RU.light-sand.pdf
COMMAND_REFERENCE_RU.dark.pdf
COMMAND_REFERENCE_RU.light-sand.pdf
```

Файлы из `docs\*.md` кладутся прямо в `docs\PDF`.

Файлы из других подпапок сохраняют относительную структуру, например:

```text
docs\PDF\install\README_INSTALL.dark.pdf
```

## Что входит в default-набор

- `docs\USER_GUIDE_RU.md`
- `docs\USER_GUIDE_EN.md`
- `docs\README_RU.md`
- `docs\README_EN.md`
- `install\README_INSTALL.md`
- все `docs\*.md`, кроме содержимого `docs\PDF`

## Проверка результата

Минимум:

```bat
install\Build-Docs-PDF.cmd --dry-run
install\Build-Docs-PDF.cmd --clean
```

После генерации проверьте:

- PDF открываются из `docs\PDF`;
- у длинных таблиц не обрезан текст;
- кириллица читается;
- страницы имеют footer с номером;
- `report\dev_markdown_pdf_manifest.json` содержит ожидаемые source/output пары.
