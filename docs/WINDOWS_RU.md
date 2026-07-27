# Windows-сборка ScriptCut

## Что получает пользователь

Windows-релиз создаёт два варианта:

- `ScriptCut Setup ... .exe` — обычный установщик с выбором папки, ярлыком на
  рабочем столе и пунктом в меню «Пуск»;
- portable `.exe` — запуск без установки.

Оба варианта содержат:

- Electron-интерфейс;
- автономный FastAPI/backend runtime;
- `faster-whisper` и CTranslate2;
- статические `ffmpeg.exe` и `ffprobe.exe` с поддержкой ASS-субтитров;
- тематический AI-монтаж, цензуру и экспорт Shorts.

Python, Node.js и отдельный FFmpeg друзьям устанавливать не нужно.

## Скачать проверенную alpha-сборку

Текущий Windows 10/11 x64 prerelease:
[ScriptCut 0.1.0 Windows alpha](https://github.com/SmetankaKluss/ScriptCut/releases/tag/windows-alpha-v0.1.0).

- `ScriptCut-Setup-0.1.0-x64.exe` — установщик, 260 880 334 байта,
  SHA-256 `d7a194bbcb532f0267f6a7489cdc9721b7b2eb0b2b9f6b73671147240954b057`;
- `ScriptCut-0.1.0-portable-x64.exe` — portable, 260 665 729 байт,
  SHA-256 `02acfe0b4da7353f5b917666501a7b453b2f321c39d578127b45f307d0e364a8`.

Рядом с `.exe` опубликованы `SHA256SUMS-windows-x64.txt` и
`release-manifest-windows-x64.json`.

## Первая установка

Сборка пока не подписана коммерческим Windows-сертификатом. SmartScreen может
показать предупреждение:

1. Нажмите **Подробнее**.
2. Сверьте SHA-256 файла с `SHA256SUMS-windows-x64.txt`.
3. Нажмите **Выполнить в любом случае**, только если файл получен от вас.

При первой расшифровке приложение скачивает модель Faster Whisper `base`.
Для этого один раз нужен интернет; затем модель остаётся в пользовательском
кэше.

## Нативная автоматическая проверка

Workflow `.github/workflows/ci.yml` использует настоящий
`windows-latest` runner и проверяет:

1. установку Python-зависимостей на Windows;
2. SHA-256 архива FFmpeg из BtbN FFmpeg Builds;
3. наличие фильтра `ass` для стилизованных субтитров;
4. сборку PyInstaller backend `.exe`;
5. сборку NSIS и portable Electron-приложений;
6. запуск backend из `win-unpacked`;
7. доступность Faster Whisper;
8. настоящий экспорт вертикального MP4 с субтитрами и цензурным бипом;
9. чтение результата встроенным `ffprobe.exe`;
10. запуск самого `ScriptCut.exe` и его защищённого локального backend.

Сборка `windows-alpha-v0.1.0` прошла все эти шаги в нативном
[CI run 30275216207](https://github.com/SmetankaKluss/ScriptCut/actions/runs/30275216207).
Promotion workflow повторно проверил SHA-256 перед публикацией файлов в
GitHub Release.

## Локальная сборка на Windows 10/11 x64

Нужны Node.js 18+ и Python 3.11 только на компьютере разработчика:

```powershell
npm ci
npm ci --prefix frontend
npm run setup:backend
npm run release:windows
```

Результаты появятся в `dist/`, а контрольные суммы и manifest — в
`dist/release-windows/`.

Скрипт разрешает плавающий релиз `latest` в конкретные GitHub release/asset ID,
а затем скачивает архив и соответствующий `checksums.sha256` через GitHub API.
При несовпадении контрольной суммы сборка немедленно останавливается.
