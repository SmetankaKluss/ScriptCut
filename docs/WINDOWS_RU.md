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
[ScriptCut 0.1.1 Windows alpha](https://github.com/SmetankaKluss/ScriptCut/releases/tag/windows-alpha-v0.1.1).

- `ScriptCut-Setup-0.1.1-x64.exe` — установщик, 253 212 520 байт,
  SHA-256 `60e9a0c2889ad4e641c554eea55ae700825f742405d751dd889a4657339d5bb8`;
- `ScriptCut-0.1.1-portable-x64.exe` — portable, 252 997 916 байт,
  SHA-256 `7699d0ad2cac3c49ced31b60c2daedbddc92bef5ffef7e860447be82a838f566`.

Рядом с `.exe` опубликованы `SHA256SUMS-windows-x64.txt` и
`release-manifest-windows-x64.json`.

Версия 0.1.1 исправляет ошибку `Requested float16 compute type` на
несовместимых GPU и строит waveform длинного стрима через FFmpeg, не загружая
весь видеофайл в память интерфейса. Whisper читает MP4 напрямую и больше не
создаёт многогигабайтный временный WAV.

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

Сборка `windows-alpha-v0.1.1` прошла все эти шаги в нативном
[CI run 30336680566](https://github.com/SmetankaKluss/ScriptCut/actions/runs/30336680566).
[Promotion workflow](https://github.com/SmetankaKluss/ScriptCut/actions/runs/30337024041)
повторно проверил SHA-256 перед публикацией файлов в GitHub Release.

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
